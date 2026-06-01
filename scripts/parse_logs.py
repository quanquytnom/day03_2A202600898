"""
Phân tích telemetry TripWise.

NÂNG CẤP: đọc logs/runs.jsonl (1 dòng/run) và in BẢNG SO SÁNH theo prompt_version
(chatbot vs v1 vs v2): success rate, avg steps, tokens, cost_usd THẬT, latency,
tool-source mix, error rate. Vẫn giữ tổng hợp theo file .log như cũ làm phụ.

Usage:
  python scripts/parse_logs.py
"""
import json
import os
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _avg(xs):
    return sum(xs) / len(xs) if xs else 0


def summarize_runs(path: str):
    """Đọc runs.jsonl -> bảng so sánh theo prompt_version."""
    groups = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            groups[rec.get("prompt_version", "?")].append(rec)

    if not groups:
        print("runs.jsonl rỗng — hãy chạy agent/chatbot trước.")
        return

    print("\n=== SO SÁNH THEO PHIÊN BẢN (runs.jsonl) ===")
    header = f"{'version':<10}{'#runs':>6}{'success%':>10}{'avg_steps':>11}{'avg_tok':>9}{'avg_cost$':>11}{'avg_lat_ms':>12}{'tool_err':>9}"
    print(header)
    print("-" * len(header))
    for version, runs in sorted(groups.items()):
        n = len(runs)
        success = sum(1 for r in runs if r.get("success")) / n * 100
        avg_steps = _avg([r.get("steps_used", 0) for r in runs])
        avg_tok = _avg([r.get("total_tokens", 0) for r in runs])
        avg_cost = _avg([r.get("total_cost_usd", 0) for r in runs])
        avg_lat = _avg([r.get("total_llm_latency_ms", 0) for r in runs])
        tool_err = sum(r.get("n_tool_errors", 0) for r in runs)
        print(
            f"{version:<10}{n:>6}{success:>9.0f}%{avg_steps:>11.1f}{avg_tok:>9.0f}"
            f"{avg_cost:>11.5f}{avg_lat:>12.0f}{tool_err:>9}"
        )

    # Tool-source mix tổng hợp
    print("\n=== NGUỒN DỮ LIỆU TOOL (live vs cache vs mock) ===")
    for version, runs in sorted(groups.items()):
        mix = defaultdict(int)
        for r in runs:
            for src, cnt in (r.get("tool_source_breakdown") or {}).items():
                mix[src] += cnt
        if mix:
            print(f"  {version}: {dict(mix)}")


def parse_log_file(path: str):
    """Tổng hợp nhanh theo file .log (phụ)."""
    metrics, tools, errors = [], defaultdict(int), defaultdict(int)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "{" not in line:
                continue
            try:
                payload = json.loads(line[line.index("{"):])
            except (json.JSONDecodeError, ValueError):
                continue
            event, data = payload.get("event"), payload.get("data", {})
            if event == "LLM_METRIC":
                metrics.append(data)
            elif event == "TOOL_CALL":
                tools[data.get("tool", "?")] += 1
            elif event in ("PARSE_ERROR", "TOOL_ERROR", "PARSE_WARNING"):
                errors[event] += 1
    if not metrics:
        return
    print(f"\n=== {os.path.basename(path)} ===")
    print(f"LLM calls: {len(metrics)} | avg latency {_avg([m.get('latency_ms', 0) for m in metrics]):.0f}ms "
          f"| avg tokens {_avg([m.get('total_tokens', 0) for m in metrics]):.0f} "
          f"| total cost ${sum(m.get('cost_usd', m.get('cost_estimate', 0)) for m in metrics):.5f}")
    if tools:
        print("Tool calls:", dict(tools))
    if errors:
        print("Errors:", dict(errors))


def main():
    log_dir = os.path.join(ROOT, "logs")
    runs_path = os.path.join(log_dir, "runs.jsonl")
    if os.path.isfile(runs_path):
        summarize_runs(runs_path)
    else:
        print("Chưa có logs/runs.jsonl.")

    if os.path.isdir(log_dir):
        for name in sorted(f for f in os.listdir(log_dir) if f.endswith(".log")):
            parse_log_file(os.path.join(log_dir, name))


if __name__ == "__main__":
    main()
