"""
Telemetry / observability cho TripWise.

NÂNG CẤP so với bản gốc (cost giả, chỉ track LLM in-memory):
- (C) Cost THẬT theo bảng giá per-model (USD / 1M token), tách input/output.
- (B) Track tool-call: latency, ok/fail, data_source (live|cache|mock|...).
- (E) summary(): tổng hợp KPI của 1 run để debug & so sánh.
- (D) write_run_summary(): ghi 1 dòng/run vào logs/runs.jsonl (key values để keep-track).
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.telemetry.logger import logger

# --- Bảng giá xấp xỉ (USD / 1 TRIỆU token) — input, output ---
# Nguồn giá công khai tại thời điểm viết; chỉ để ước lượng, dễ chỉnh.
PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"in": 2.5, "out": 10.0},
    "gpt-4o-mini": {"in": 0.15, "out": 0.6},
    "gpt-4.1": {"in": 2.0, "out": 8.0},
    "gemini-2.0-flash": {"in": 0.075, "out": 0.30},
    "gemini-1.5-flash": {"in": 0.075, "out": 0.30},
    "mimo": {"in": 0.0, "out": 0.0},
    "local": {"in": 0.0, "out": 0.0},
}
_DEFAULT_PRICE = {"in": 0.5, "out": 1.5}


def _price_for(model: str) -> Dict[str, float]:
    m = (model or "").lower()
    for key, price in PRICING_PER_1M.items():
        if key in m:
            return price
    return _DEFAULT_PRICE


class PerformanceTracker:
    """Track KPI theo từng run (LLM calls + tool calls) để estimate & keep-track."""

    def __init__(self):
        self.run_id: Optional[str] = None
        self.prompt_version: Optional[str] = None
        self.llm_events: List[Dict[str, Any]] = []
        self.tool_events: List[Dict[str, Any]] = []

    def start_run(self, run_id: str, prompt_version: str = "") -> None:
        """Bắt đầu một run mới — reset buffer để summary chỉ tính run này."""
        self.run_id = run_id
        self.prompt_version = prompt_version
        self.llm_events = []
        self.tool_events = []

    def track_request(
        self,
        provider: str,
        model: str,
        usage: Dict[str, int],
        latency_ms: int,
        prompt_version: Optional[str] = None,
    ):
        """Ghi metric 1 LLM-call với cost_usd THẬT."""
        cost = self._calculate_cost(model, usage)
        metric = {
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version or self.prompt_version,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_usd": cost,
        }
        self.llm_events.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def track_tool(self, tool: str, latency_ms: int, ok: bool, source: str):
        """Ghi metric 1 tool-call: latency, thành/bại, nguồn dữ liệu."""
        self.tool_events.append(
            {"tool": tool, "latency_ms": latency_ms, "ok": ok, "source": source}
        )

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        price = _price_for(model)
        cost = (
            usage.get("prompt_tokens", 0) / 1_000_000 * price["in"]
            + usage.get("completion_tokens", 0) / 1_000_000 * price["out"]
        )
        return round(cost, 6)

    def summary(self) -> Dict[str, Any]:
        """Tổng hợp KPI của run hiện tại."""
        source_breakdown: Dict[str, int] = {}
        for e in self.tool_events:
            source_breakdown[e["source"]] = source_breakdown.get(e["source"], 0) + 1
        tool_latencies = [e["latency_ms"] for e in self.tool_events]
        return {
            "n_llm_calls": len(self.llm_events),
            "prompt_tokens": sum(e["prompt_tokens"] for e in self.llm_events),
            "completion_tokens": sum(e["completion_tokens"] for e in self.llm_events),
            "total_tokens": sum(e["total_tokens"] for e in self.llm_events),
            "total_cost_usd": round(sum(e["cost_usd"] for e in self.llm_events), 6),
            "total_llm_latency_ms": sum(e["latency_ms"] for e in self.llm_events),
            "n_tool_calls": len(self.tool_events),
            "n_tool_errors": sum(1 for e in self.tool_events if not e["ok"]),
            "tool_source_breakdown": source_breakdown,
            "avg_tool_latency_ms": round(sum(tool_latencies) / len(tool_latencies)) if tool_latencies else 0,
        }

    def write_run_summary(self, extra: Dict[str, Any], log_dir: str = "logs") -> Dict[str, Any]:
        """Gộp summary KPI + thông tin run (extra) -> ghi 1 dòng JSON vào runs.jsonl."""
        record = {
            "run_id": self.run_id,
            "ts": datetime.utcnow().isoformat(),
            "prompt_version": self.prompt_version,
            **extra,
            **self.summary(),
        }
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        with open(os.path.join(log_dir, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.log_event("RUN_SUMMARY", record)
        return record


# Global tracker instance
tracker = PerformanceTracker()
