"""
Demo/verify vòng lặp ReAct + telemetry mà KHÔNG phụ thuộc LLM ngoài.

Vì sao cần: nhà cung cấp LLM (Mimo) đang bị rate-limit (HTTP 429), không chạy
end-to-end thật được. Script này dùng FakeLLM — một "test double" cho MÔ HÌNH
(không phải fake data!). Các TOOL vẫn gọi dữ liệu THẬT (Open-Meteo/Overpass/OSRM).

Mục đích:
- Kiểm chứng: parser nuốt backticks, guardrail, run_id, ghi logs/runs.jsonl.
- Tạo trace thật cho report.

Usage:
  python scripts/demo_offline_agent.py
"""
import os
import sys
from typing import Any, Dict, Generator, Optional

# Ép UTF-8 cho console Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.llm_provider import LLMProvider
from src.agent.agent import ReActAgent
from src.tools.tool_specs import get_tools_v2


class FakeLLM(LLMProvider):
    """Phát lần lượt các bước ReAct kịch bản sẵn (test double cho model)."""

    def __init__(self, scripted):
        super().__init__(model_name="demo-gpt-4o-mini")
        self._scripted = scripted
        self._i = 0

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        content = self._scripted[min(self._i, len(self._scripted) - 1)]
        self._i += 1
        # token giả định để cost_usd ra số (theo bảng giá gpt-4o-mini).
        return {
            "content": content,
            "usage": {"prompt_tokens": 800 + 200 * self._i, "completion_tokens": 120, "total_tokens": 920 + 200 * self._i},
            "latency_ms": 350,
            "provider": "fake",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt)["content"]


def main():
    # Kịch bản v2: chú ý bước 2 cố tình bọc backticks để test parser mới.
    scripted = [
        'Thought: Cần xem thời tiết trước.\nAction: get_weather("Đà Nẵng")',
        '`Action: search_attractions("Đà Nẵng", "biển")`',
        'Thought: Ước lượng chi phí.\nAction: estimate_trip_cost("Đà Nẵng", 3, 2)',
        'Thought: Kiểm tra ngân sách.\nAction: check_budget_fit(9600000, 8000000)',
        'Thought: Lên lịch trình.\nAction: create_itinerary("Đà Nẵng", 3, 8000000, "biển")',
        "Final Answer: Lịch trình 3 ngày Đà Nẵng (xem chi tiết ở các Observation phía trên), "
        "đã kiểm tra thời tiết, chi phí và ngân sách.",
    ]
    agent = ReActAgent(llm=FakeLLM(scripted), tools=get_tools_v2(), max_steps=8, prompt_version="v2")
    answer = agent.run("Đà Nẵng biển 3 ngày 2 người ngân sách 8 triệu")
    print("\n=== FINAL ANSWER ===")
    print(answer)
    print("\nXem logs/runs.jsonl để thấy bản ghi tổng hợp run này.")


if __name__ == "__main__":
    main()
