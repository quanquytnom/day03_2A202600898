"""Tool registry for TripWise Agent v1 and v2."""
from typing import Any, Callable, Dict, List

from src.tools import travel_tools as t


def _spec(name: str, description: str, func: Callable, example: str) -> Dict[str, Any]:
    return {"name": name, "description": description, "func": func, "example": example}


def get_tools_v1() -> List[Dict[str, Any]]:
    """Agent v1 — Basic Travel Planner (3 core tools)."""
    return [
        _spec(
            "get_weather",
            'Thời tiết điểm đến. Args: destination (str), date (str, optional). Example: get_weather("Đà Nẵng", "today")',
            t.get_weather,
            'get_weather("Đà Nẵng", "today")',
        ),
        _spec(
            "search_attractions",
            'Danh sách địa điểm. Args: destination (str), travel_style (str). Example: search_attractions("Đà Nẵng", "biển")',
            t.search_attractions,
            'search_attractions("Đà Nẵng", "biển")',
        ),
        _spec(
            "estimate_trip_cost",
            'Ước lượng chi phí JSON. Args: destination (str), days (int), people (int). Example: estimate_trip_cost("Đà Nẵng", 3, 2)',
            t.estimate_trip_cost,
            'estimate_trip_cost("Đà Nẵng", 3, 2)',
        ),
        _spec(
            "create_itinerary",
            'Khung lịch trình markdown. Args: destination, days (int), budget (int), style (str). Example: create_itinerary("Đà Nẵng", 3, 5000000, "biển")',
            t.create_itinerary,
            'create_itinerary("Đà Nẵng", 3, 5000000, "biển")',
        ),
    ]


def get_tools_v2() -> List[Dict[str, Any]]:
    """Agent v2 — Smart Travel Planner (v1 + route, restaurants, budget, risk)."""
    tools = get_tools_v1()
    tools.extend(
        [
            _spec(
                "calculate_route_time",
                'Thời gian di chuyển. Args: start (str), end (str). Example: calculate_route_time("Mỹ Khê", "Bà Nà Hills")',
                t.calculate_route_time,
                'calculate_route_time("Mỹ Khê", "Bà Nà Hills")',
            ),
            _spec(
                "suggest_restaurants",
                'Gợi ý quán ăn JSON. Args: destination (str), cuisine (str). Example: suggest_restaurants("Đà Nẵng", "hải sản")',
                t.suggest_restaurants,
                'suggest_restaurants("Đà Nẵng", "hải sản")',
            ),
            _spec(
                "check_budget_fit",
                'So sánh ngân sách. Args: estimated_total (int), budget (int). Example: check_budget_fit(4800000, 5000000)',
                t.check_budget_fit,
                4800000,
            ),
            _spec(
                "weather_risk_warning",
                'Cảnh báo rủi ro thời tiết JSON. Args: destination (str). Example: weather_risk_warning("Đà Nẵng")',
                t.weather_risk_warning,
                'weather_risk_warning("Đà Nẵng")',
            ),
        ]
    )
    # fix check_budget_fit example
    for tool in tools:
        if tool["name"] == "check_budget_fit":
            tool["example"] = "check_budget_fit(4800000, 5000000)"
    return tools
