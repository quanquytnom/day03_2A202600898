import ast
import inspect
import json
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools import travel_tools


class ReActAgent:
    """
    TripWise ReAct Agent — Thought → Action → Observation → Final Answer.

    NÂNG CẤP (Targeted upgrade):
    - Parser bền hơn: nuốt được backticks / code-fence / xuống dòng trong ().
    - EXAMPLE trong system prompt sinh từ registry (hết lệch khi đổi tool).
    - Guardrail: chống gọi trùng (vòng lặp), v2 ép check_budget_fit trước Final Answer.
    - Observability: run_id xuyên suốt, log data_source + tool latency, ghi runs.jsonl.
    """

    FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)
    THOUGHT_RE = re.compile(r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:)|\Z)", re.IGNORECASE | re.DOTALL)
    # Nới lỏng: cho phép xuống dòng trong (), không bắt buộc anchor cuối dòng.
    ACTION_RE = re.compile(r"Action:\s*([A-Za-z_]\w*)\s*\((.*?)\)", re.IGNORECASE | re.DOTALL)
    ACTION_RE_GREEDY = re.compile(r"Action:\s*([A-Za-z_]\w*)\s*\((.*)\)", re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 8,
        prompt_version: str = "v1",
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.prompt_version = prompt_version
        self.history: List[Dict[str, str]] = []
        self._tool_map: Dict[str, Callable] = {t["name"]: t["func"] for t in tools}

    def get_system_prompt(self) -> str:
        tool_lines = "\n".join(
            [f"- {t['name']}: {t['description']}\n  Example: {t.get('example', '')}" for t in self.tools]
        )
        # EXAMPLE sinh động từ chính registry -> luôn khớp tool đang bật (v1/v2).
        example_lines = "\n".join([f"Action: {t.get('example', '')}" for t in self.tools if t.get("example")])
        base_rules = """
You are TripWise — an AI travel planning agent for Vietnam destinations.

RULES:
1. Respond in Vietnamese unless the user writes in English.
2. Use ONLY the tools listed below. Never invent tool names.
3. One Action per step. Wait for Observation before the next Action.
4. Action format (no markdown, no backticks): Action: tool_name(arg1, arg2)
   - Strings in double quotes. Numbers without quotes.
5. After gathering enough data, output exactly one line starting with: Final Answer:
6. Do NOT write "Observation:" yourself — the system injects it after each tool call.
7. Do NOT repeat the same Action with the same arguments — reuse the Observation you already got.

Recommended flow:
Thought → Action (get_weather) → [Observation]
Thought → Action (search_attractions) → [Observation]
Thought → Action (estimate_trip_cost) → [Observation]
Thought → Action (create_itinerary) → [Observation]
Thought → Final Answer: (full day-by-day plan with cost & weather notes)
"""
        v2_extra = """
AGENT v2 — also use when helpful:
- calculate_route_time between two places in your plan
- suggest_restaurants for food preferences
- check_budget_fit(estimated_total, budget) after estimate_trip_cost
- weather_risk_warning before scheduling outdoor activities
Always verify budget with check_budget_fit before Final Answer.
"""
        prompt = f"""{base_rules}
{ v2_extra if self.prompt_version == "v2" else "" }

AVAILABLE TOOLS:
{tool_lines}

EXAMPLE Action lines:
{example_lines}
"""
        return prompt.strip()

    def run(self, user_input: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        logger.set_context(run_id=run_id, prompt_version=self.prompt_version)
        tracker.start_run(run_id, self.prompt_version)

        system_prompt = self.get_system_prompt()
        logger.log_event(
            "RUN_CONFIG",
            {
                "model": self.llm.model_name,
                "prompt_chars": len(system_prompt),
                "tools": list(self._tool_map.keys()),
                "max_steps": self.max_steps,
            },
        )
        logger.log_event(
            "AGENT_START",
            {"input": user_input, "model": self.llm.model_name, "version": self.prompt_version},
        )

        transcript = f"User request: {user_input}\n"
        steps = 0
        final_answer: Optional[str] = None
        n_parse_errors = 0
        seen_actions: Dict[str, int] = {}
        budget_checked = False
        budget_nudged = False

        llm_delay = float(os.getenv("LLM_CALL_DELAY_SEC", "0"))

        while steps < self.max_steps:
            if llm_delay > 0 and steps > 0:
                time.sleep(llm_delay)
            result = self.llm.generate(transcript, system_prompt=system_prompt)
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
                prompt_version=self.prompt_version,
            )

            content = (result.get("content") or "").strip()
            logger.log_event("AGENT_STEP", {"step": steps + 1, "raw": content[:2000]})

            action = self._extract_action(content)
            final_match = self.FINAL_ANSWER_RE.search(content)
            thought = self._extract_thought(content)

            if action:
                tool_name, args = action
                sig = f"{tool_name}{args!r}"

                # Guardrail: chống gọi trùng -> vòng lặp.
                if seen_actions.get(sig, 0) >= 1:
                    seen_actions[sig] += 1
                    logger.log_event("LOOP_GUARD", {"step": steps + 1, "tool": tool_name, "repeats": seen_actions[sig]})
                    if seen_actions[sig] >= 3:
                        logger.log_event("LOOP_BREAK", {"step": steps + 1, "tool": tool_name})
                        break
                    transcript += (
                        f"\n{content}\n"
                        f"Observation: Bạn đã gọi {tool_name} với tham số này rồi. "
                        f"Hãy dùng lại Observation cũ hoặc trả Final Answer.\n"
                    )
                    steps += 1
                    continue

                seen_actions[sig] = seen_actions.get(sig, 0) + 1
                if tool_name == "check_budget_fit":
                    budget_checked = True

                t0 = time.time()
                observation = self._execute_tool(tool_name, args)
                tool_latency_ms = int((time.time() - t0) * 1000)
                source = travel_tools.last_data_source()
                ok = not observation.startswith(("Tool error", "Tool '"))
                tracker.track_tool(tool_name, tool_latency_ms, ok, source)

                logger.log_event(
                    "TOOL_CALL",
                    {
                        "step": steps + 1,
                        "tool": tool_name,
                        "args": args,
                        "data_source": source,
                        "tool_latency_ms": tool_latency_ms,
                        "ok": ok,
                        "observation": observation[:500],
                    },
                )
                transcript += f"\n{content}\nObservation: {observation}\n"
                self.history.append({"thought": thought, "action": tool_name, "observation": observation})

            elif final_match:
                # v2: ép verify ngân sách trước khi chốt (tối đa nudge 1 lần).
                if self.prompt_version == "v2" and not budget_checked and not budget_nudged:
                    budget_nudged = True
                    logger.log_event("BUDGET_NUDGE", {"step": steps + 1})
                    transcript += (
                        f"\n{content}\n"
                        f"Observation: Chưa gọi check_budget_fit. Hãy gọi check_budget_fit(estimated_total, budget) "
                        f"để xác nhận ngân sách trước khi trả Final Answer.\n"
                    )
                    steps += 1
                    continue
                final_answer = final_match.group(1).strip()
                self.history.append({"role": "assistant", "content": content})
                break

            else:
                n_parse_errors += 1
                logger.log_event("PARSE_WARNING", {"step": steps + 1, "message": "No Action or Final Answer"})
                transcript += f"\n{content}\nObservation: Hãy gọi một tool hợp lệ hoặc trả Final Answer.\n"

            steps += 1

        success = final_answer is not None
        if not final_answer:
            final_answer = (
                "Không hoàn thành trong số bước cho phép. "
                "Vui lòng thử lại với yêu cầu rõ hơn (điểm đến, số ngày, ngân sách)."
            )

        # Ghi summary 1 dòng/run vào logs/runs.jsonl (key values để keep-track & debug).
        tracker.write_run_summary(
            {
                "query": user_input,
                "model": self.llm.model_name,
                "success": success,
                "steps_used": steps,
                "max_steps": self.max_steps,
                "n_parse_errors": n_parse_errors,
                "budget_verified": budget_checked,
                "final_answer_len": len(final_answer),
            }
        )
        logger.log_event("AGENT_END", {"steps": steps, "version": self.prompt_version, "success": success})
        logger.clear_context()
        return final_answer

    def _extract_thought(self, content: str) -> str:
        m = self.THOUGHT_RE.search(content)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _clean(content: str) -> str:
        """Bỏ code-fence ``` và backtick bao quanh để parser không gãy."""
        return content.replace("```", " ").replace("`", "")

    def _extract_action(self, content: str) -> Optional[Tuple[str, tuple]]:
        cleaned = self._clean(content)
        # Bỏ qua phần sau "Final Answer:" để không bắt nhầm ví dụ Action trong câu trả lời.
        cut = re.split(r"Final Answer:", cleaned, flags=re.IGNORECASE)[0]

        for regex in (self.ACTION_RE, self.ACTION_RE_GREEDY):
            m = regex.search(cut)
            if not m:
                continue
            name, args_str = m.group(1), m.group(2).strip()
            try:
                parsed = ast.literal_eval(f"({args_str})") if args_str else ()
                if not isinstance(parsed, tuple):
                    parsed = (parsed,)
                return name, parsed
            except (SyntaxError, ValueError) as e:
                logger.log_event("PARSE_ERROR", {"tool": name, "args": args_str, "error": str(e)})
                continue
        return None

    def _execute_tool(self, tool_name: str, args: tuple) -> str:
        func = self._tool_map.get(tool_name)
        if not func:
            return f"Tool '{tool_name}' not found. Available: {', '.join(self._tool_map)}"

        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if len(args) < len(params):
                kwargs = dict(zip(params, args))
                out = func(**kwargs)
            else:
                out = func(*args[: len(params)])
            return out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        except Exception as e:
            logger.log_event("TOOL_ERROR", {"tool": tool_name, "error": str(e)})
            return f"Tool error: {e}. Check argument types and count."
