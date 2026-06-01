"""
TripWise ReAct Agent — interactive CLI.
Usage:
  python tripwise_agent.py          # agent v1
  python tripwise_agent.py --v2     # agent v2 (extra tools)
"""
import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.core.factory import get_llm_provider
from src.tools.tool_specs import get_tools_v1, get_tools_v2


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="TripWise ReAct Agent")
    parser.add_argument("--v2", action="store_true", help="Use Agent v2 (smart planner)")
    parser.add_argument("--query", type=str, help="Single query (non-interactive)")
    args = parser.parse_args()

    version = "v2" if args.v2 else "v1"
    tools = get_tools_v2() if args.v2 else get_tools_v1()
    llm = get_llm_provider()
    agent = ReActAgent(llm=llm, tools=tools, max_steps=8, prompt_version=version)

    print(f"TripWise Agent {version} | model={llm.model_name}")
    print("Nhập 'quit' để thoát.\n")

    def run_one(q: str):
        print(f"\n--- Đang xử lý ---\n{q}\n")
        answer = agent.run(q)
        print(f"\n=== Final Answer ===\n{answer}\n")

    if args.query:
        run_one(args.query)
        return

    while True:
        q = input("Bạn: ").strip()
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue
        run_one(q)


if __name__ == "__main__":
    main()
