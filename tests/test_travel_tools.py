"""
Offline tests — KHÔNG cần API key, KHÔNG gọi mạng.

Mặc định tắt live tools (USE_LIVE_TOOLS=false) để test tất định và chạy được offline,
qua đó kiểm chứng cơ chế FALLBACK về mock. Có thêm test ép lỗi mạng để chắc chắn
fallback hoạt động kể cả khi live đang bật.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    """Tắt live cho phần lớn test -> dùng fallback mock, tất định."""
    monkeypatch.setenv("USE_LIVE_TOOLS", "false")


from src.tools.travel_tools import (
    estimate_trip_cost,
    get_weather,
    search_attractions,
    suggest_restaurants,
    check_budget_fit,
    last_data_source,
)
from src.tools.tool_specs import get_tools_v1, get_tools_v2


def test_weather_fallback():
    out = get_weather("Đà Nẵng")
    assert "Đà Nẵng" in out
    assert last_data_source() == "mock"


def test_attractions_fallback():
    data = json.loads(search_attractions("Đà Nẵng", "biển"))
    assert "Mỹ Khê" in " ".join(data["places"])
    assert data["data_source"] == "mock"


def test_cost_is_heuristic():
    data = json.loads(estimate_trip_cost("Đà Nẵng", 3, 2))
    assert data["total"] > 0
    assert data["data_source"] == "heuristic"


def test_restaurants_uses_cuisine_param():
    """Bug cũ: cuisine bị lờ. Giờ cuisine phải xuất hiện trong output."""
    data = json.loads(suggest_restaurants("Đà Nẵng", "hải sản"))
    assert data["cuisine"] == "hải sản"


def test_budget_fit():
    ok = json.loads(check_budget_fit(4_000_000, 5_000_000))
    assert ok["fits_budget"] is True


def test_tool_registry():
    assert len(get_tools_v1()) >= 4
    assert len(get_tools_v2()) > len(get_tools_v1())


def test_fallback_when_network_raises(monkeypatch):
    """Bật live nhưng ép mọi HTTP raise -> tool vẫn trả mock, không crash."""
    monkeypatch.setenv("USE_LIVE_TOOLS", "true")
    from src.tools import live_clients

    def boom(*args, **kwargs):
        raise live_clients.LiveDataError("forced offline")

    monkeypatch.setattr(live_clients, "geocode", boom)
    out = get_weather("Nha Trang")
    assert "Nha Trang" in out
    assert last_data_source() == "mock"


def test_parser_tolerates_backticks_and_multiline():
    """Parser mới phải nuốt được Action có backticks / code-fence / xuống dòng."""
    from src.agent.agent import ReActAgent

    tools = get_tools_v1()
    agent = ReActAgent(llm=None, tools=tools, prompt_version="v1")

    cases = [
        'Thought: ok\nAction: get_weather("Đà Nẵng", "today")',
        '`Action: get_weather("Đà Nẵng")`',
        "```\nAction: estimate_trip_cost(\"Đà Nẵng\", 3, 2)\n```",
        'Action: get_weather(\n  "Đà Nẵng",\n  "today"\n)',
    ]
    for c in cases:
        parsed = agent._extract_action(c)
        assert parsed is not None, f"Không parse được: {c!r}"
        assert parsed[0] in {"get_weather", "estimate_trip_cost"}


def test_parser_ignores_action_inside_final_answer():
    from src.agent.agent import ReActAgent

    agent = ReActAgent(llm=None, tools=get_tools_v1(), prompt_version="v1")
    content = 'Final Answer: Gợi ý dùng Action: get_weather(...) nếu cần.'
    assert agent._extract_action(content) is None
