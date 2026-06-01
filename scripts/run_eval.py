"""
Run Chatbot vs TripWise Agent on test_cases.json.
Saves results to results/eval_results.json

Usage:
  python scripts/run_eval.py --offline-tools-only   # test tools without LLM
  python scripts/run_eval.py --limit 2            # first 2 cases with LLM
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from chatbot import TravelChatbot
from src.agent.agent import ReActAgent
from src.core.factory import get_llm_provider
from src.tools.tool_specs import get_tools_v1, get_tools_v2


def load_cases(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def offline_tool_smoke():
    """Verify mock tools without calling LLM."""
    from src.tools import travel_tools as t

    assert "Đà Nẵng" in t.get_weather("Đà Nẵng")
    attrs = json.loads(t.search_attractions("Đà Nẵng", "biển"))
    assert len(attrs["places"]) >= 3
    cost = json.loads(t.estimate_trip_cost("Đà Nẵng", 3, 2))
    assert cost["total"] > 0
    print("✅ Offline tool smoke passed")


def run_eval(limit: int | None, use_v2: bool):
    cases_path = os.path.join(ROOT, "tests", "test_cases.json")
    cases = load_cases(cases_path)
    if limit:
        cases = cases[:limit]

    llm = get_llm_provider()
    chatbot = TravelChatbot(llm=llm)
    tools = get_tools_v2() if use_v2 else get_tools_v1()
    version = "v2" if use_v2 else "v1"
    agent = ReActAgent(llm=llm, tools=tools, max_steps=8, prompt_version=version)

    results = []
    for case in cases:
        q = case["query"]
        row = {"id": case["id"], "type": case["type"], "query": q}

        t0 = time.time()
        try:
            row["chatbot_answer"] = chatbot.ask(q)[:1500]
            row["chatbot_ok"] = True
        except Exception as e:
            row["chatbot_answer"] = str(e)
            row["chatbot_ok"] = False
        row["chatbot_ms"] = int((time.time() - t0) * 1000)

        t1 = time.time()
        try:
            row["agent_answer"] = agent.run(q)[:2000]
            row["agent_ok"] = True
        except Exception as e:
            row["agent_answer"] = str(e)
            row["agent_ok"] = False
        row["agent_ms"] = int((time.time() - t1) * 1000)

        results.append(row)
        print(f"[{case['id']}] chatbot_ok={row['chatbot_ok']} agent_ok={row['agent_ok']}")

    out_dir = os.path.join(ROOT, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"eval_{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"version": version, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-tools-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--v2", action="store_true")
    args = parser.parse_args()

    if args.offline_tools_only:
        offline_tool_smoke()
        return

    run_eval(args.limit, args.v2)


if __name__ == "__main__":
    main()
