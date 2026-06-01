"""
TripWise Chatbot Baseline — single LLM call, no tools.
Used to compare against ReAct Agent in Lab 3 evaluation.
"""
import os
import sys
import uuid

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.factory import get_llm_provider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

TRAVEL_CHATBOT_SYSTEM = """You are a friendly travel assistant. Answer in Vietnamese.
You do NOT have access to live weather, prices, or maps.
Give general suggestions only. If the user asks for a detailed budget or live weather,
say you can only provide general advice without real-time data."""


class TravelChatbot:
    def __init__(self, llm=None):
        self.llm = llm or get_llm_provider()

    def ask(self, user_input: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        logger.set_context(run_id=run_id, prompt_version="chatbot")
        tracker.start_run(run_id, "chatbot")
        logger.log_event("CHATBOT_START", {"input": user_input})
        result = self.llm.generate(user_input, system_prompt=TRAVEL_CHATBOT_SYSTEM)
        tracker.track_request(
            provider=result.get("provider", "unknown"),
            model=self.llm.model_name,
            usage=result.get("usage", {}),
            latency_ms=result.get("latency_ms", 0),
            prompt_version="chatbot",
        )
        content = result.get("content", "")
        # Chatbot không có tool/loop -> success nếu trả về nội dung.
        tracker.write_run_summary(
            {
                "query": user_input,
                "model": self.llm.model_name,
                "success": bool(content),
                "steps_used": 1,
                "max_steps": 1,
                "n_parse_errors": 0,
                "budget_verified": False,
                "final_answer_len": len(content),
            }
        )
        logger.log_event("CHATBOT_END", {"latency_ms": result.get("latency_ms")})
        logger.clear_context()
        return content


def main():
    load_dotenv()
    bot = TravelChatbot()
    print("TripWise Chatbot (baseline). Nhập 'quit' để thoát.\n")
    while True:
        q = input("Bạn: ").strip()
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue
        print(f"\nChatbot: {bot.ask(q)}\n")


if __name__ == "__main__":
    main()
