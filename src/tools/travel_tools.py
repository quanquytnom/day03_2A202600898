"""
TripWise — travel tools cho Lab 3.

NÂNG CẤP (Targeted upgrade): mỗi tool giờ gọi **dữ liệu thật keyless** qua
`live_clients.py` (Open-Meteo / OpenStreetMap Overpass / OSRM), và **fallback về
mock** khi offline/lỗi để lab vẫn chạy được mọi lúc.

- Bật/tắt gọi dữ liệu thật bằng env `USE_LIVE_TOOLS` (mặc định: true).
- Mỗi lần gọi tool cập nhật nguồn dữ liệu (`live` | `cache` | `mock` | `heuristic`)
  để tầng telemetry log lại — phục vụ debug & so sánh.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from src.tools import live_clients as live

# --- Dữ liệu fallback (mock) — chỉ dùng khi gọi API thật thất bại ---

WEATHER_FALLBACK: Dict[str, str] = {
    "đà nẵng": "Nắng đẹp, 28–32°C; buổi chiều có thể mưa rào ngắn.",
    "đà lạt": "Mát, 18–24°C; sương mù buổi sáng, mưa nhẹ buổi tối.",
    "hà nội": "Nóng ẩm, 30–35°C; chiều có mưa dông.",
    "phú quốc": "Nắng, biển êm; tối gió nhẹ.",
    "nha trang": "Nắng, phù hợp tắm biển; trưa nắng gắt.",
}

ATTRACTIONS_FALLBACK: Dict[str, Dict[str, List[str]]] = {
    "đà nẵng": {
        "biển": ["Bãi biển Mỹ Khê", "Cầu Rồng", "Ngũ Hành Sơn", "Chợ đêm Sơn Trà"],
        "gia đình": ["Bà Nà Hills", "Asia Park", "Bãi biển Mỹ Khê", "Cầu Rồng"],
        "ăn uống": ["Chợ Hàn", "Mỹ An seafood", "Cầu Rồng", "Hải sản Bé Mặn"],
        "chụp ảnh": ["Cầu Vàng Bà Nà", "Cầu Rồng", "Bãi biển Mỹ Khê", "Linh Ứng Sơn Trà"],
        "default": ["Bãi biển Mỹ Khê", "Bà Nà Hills", "Cầu Rồng", "Chợ đêm Sơn Trà"],
    },
    "đà lạt": {
        "default": ["Hồ Xuân Hương", "Langbiang", "Chợ đêm", "Dinh Bảo Đại"],
        "chụp ảnh": ["Đồi chè Cầu Đất", "Hồ Xuân Hương", "Ga Đà Lạt", "Thung lũng tình yêu"],
    },
}

COST_BASE_PER_DAY: Dict[str, int] = {
    "đà nẵng": 1_600_000,
    "đà lạt": 1_400_000,
    "hà nội": 1_800_000,
    "phú quốc": 2_000_000,
    "nha trang": 1_500_000,
}

RESTAURANTS_FALLBACK: Dict[str, List[str]] = {
    "đà nẵng": ["Hải sản Bé Mặn", "Bà Aê Restaurant", "Mì Quảng Bà Mua", "Nhà hàng Cơm Niêu"],
    "đà lạt": ["Quán Gỏi Đà Lạt", "Bánh căn Bà Tùng", "Lẩu gà lá é"],
}

# Map sở thích ẩm thực tiếng Việt -> OSM cuisine tag (tiếng Anh) để lọc Overpass.
_CUISINE_MAP = {
    "hải sản": "seafood",
    "chay": "vegetarian",
    "nướng": "barbecue",
    "lẩu": "hotpot",
    "việt": "vietnamese",
    "địa phương": "vietnamese",
    "nhật": "japanese",
    "hàn": "korean",
}

# --- Theo dõi nguồn dữ liệu của lần gọi tool gần nhất (cho telemetry) ---
_LAST_SOURCE = "mock"


def last_data_source() -> str:
    """Nguồn dữ liệu của observation vừa tạo: live | cache | mock | heuristic | computed."""
    return _LAST_SOURCE


def _set_source(source: str) -> None:
    global _LAST_SOURCE
    _LAST_SOURCE = source


def _live_enabled() -> bool:
    return os.getenv("USE_LIVE_TOOLS", "true").strip().lower() in ("1", "true", "yes")


def _live_or_cache() -> str:
    """Sau 1 call thật thành công: phân biệt cache vs live."""
    return "cache" if live.last_call_from_cache() else "live"


def _norm_destination(destination: str) -> str:
    return destination.strip().lower()


def get_weather(destination: str, date: str = "today") -> str:
    """Thời tiết điểm đến — gọi Open-Meteo thật, fallback mock khi lỗi."""
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            w = live.fetch_weather(geo["lat"], geo["lon"])
            _set_source(_live_or_cache())
            return (
                f"Thời tiết tại {destination} ({date}): "
                f"{round(w['temp_min'])}–{round(w['temp_max'])}°C, "
                f"khả năng mưa ~{w['precip_prob']}%. [nguồn: {_LAST_SOURCE}]"
            )
        except live.LiveDataError:
            pass
    _set_source("mock")
    key = _norm_destination(destination)
    detail = WEATHER_FALLBACK.get(key, "Thời tiết ổn định, nên mang áo mưa nhẹ phòng mưa rào.")
    return f"Thời tiết tại {destination} ({date}): {detail} [nguồn: mock]"


def search_attractions(destination: str, travel_style: str = "default") -> str:
    """Địa điểm tham quan — gọi OpenStreetMap Overpass thật, fallback mock khi lỗi."""
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            places = live.fetch_pois(geo["lat"], geo["lon"], kind="attraction")
            _set_source(_live_or_cache())
            return json.dumps(
                {"destination": destination, "style": travel_style, "places": places, "data_source": _LAST_SOURCE},
                ensure_ascii=False,
            )
        except live.LiveDataError:
            pass
    _set_source("mock")
    key = _norm_destination(destination)
    style_key = (travel_style or "default").strip().lower()
    by_dest = ATTRACTIONS_FALLBACK.get(key, {})
    places = by_dest.get(style_key) or by_dest.get("default") or [
        "Quảng trường trung tâm",
        "Chợ địa phương",
        "Bảo tàng địa phương",
    ]
    return json.dumps(
        {"destination": destination, "style": travel_style, "places": places, "data_source": "mock"},
        ensure_ascii=False,
    )


def estimate_trip_cost(destination: str, days: int, people: int = 1) -> str:
    """
    Ước lượng chi phí (heuristic). Lưu ý: giá khách sạn/ăn uống thật cần API trả phí,
    nên đây là ước lượng theo hệ số, KHÔNG phải giá thị trường realtime — ghi rõ để
    không gây hiểu nhầm (no fabrication).
    """
    _set_source("heuristic")
    key = _norm_destination(destination)
    base = COST_BASE_PER_DAY.get(key, 1_500_000)
    hotel = int(base * 0.35 * days * people)
    food = int(base * 0.30 * days * people)
    transport = int(base * 0.15 * days * people)
    tickets = int(base * 0.20 * days * people)
    total = hotel + food + transport + tickets
    payload = {
        "destination": destination,
        "days": days,
        "people": people,
        "hotel": hotel,
        "food": food,
        "transport": transport,
        "tickets": tickets,
        "total": total,
        "currency": "VND",
        "data_source": "heuristic",
        "note": "Ước lượng theo hệ số trung bình, không phải giá đặt phòng realtime.",
    }
    return json.dumps(payload, ensure_ascii=False)


def calculate_route_time(start: str, end: str) -> str:
    """Thời gian di chuyển — gọi OSRM thật (km + phút), fallback ước lượng khi lỗi."""
    if _live_enabled():
        try:
            a = live.geocode(start)
            b = live.geocode(end)
            r = live.route((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            _set_source(_live_or_cache())
            return (
                f"Thời gian di chuyển từ '{start}' đến '{end}': "
                f"~{r['minutes']} phút ({r['km']} km, ô tô). [nguồn: {_LAST_SOURCE}]"
            )
        except live.LiveDataError:
            pass
    _set_source("mock")
    return f"Thời gian di chuyển từ '{start}' đến '{end}': khoảng 20–35 phút (ô tô/grab). [nguồn: mock]"


def create_itinerary(destination: str, days: int, budget: int, style: str = "default") -> str:
    """
    Khung lịch trình theo ngày. NÂNG CẤP: rải các địa điểm THẬT (Overpass) vào từng
    ngày thay vì template rỗng; fallback template khi không có dữ liệu thật.
    """
    places: List[str] = []
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            places = live.fetch_pois(geo["lat"], geo["lon"], kind="attraction", limit=days * 2 + 2)
            _set_source(_live_or_cache())
        except live.LiveDataError:
            places = []
    if not places:
        _set_source("mock")
        key = _norm_destination(destination)
        by_dest = ATTRACTIONS_FALLBACK.get(key, {})
        places = by_dest.get((style or "default").strip().lower()) or by_dest.get("default") or []

    lines = [
        f"# Lịch trình {days} ngày tại {destination}",
        f"Phong cách: {style} | Ngân sách mục tiêu: {budget:,} VND/người | Nguồn địa điểm: {_LAST_SOURCE}",
        "",
    ]
    # Chia đều địa điểm thật cho các ngày
    per_day = max(1, len(places) // days) if places else 0
    for d in range(1, days + 1):
        chunk = places[(d - 1) * per_day: d * per_day] if places else []
        spots = ", ".join(chunk) if chunk else "điểm tham quan nổi bật địa phương"
        if d == 1:
            lines.append(f"## Ngày {d}: Check-in & khám phá gần trung tâm")
            lines.append(f"- Sáng: Di chuyển & nhận phòng")
            lines.append(f"- Chiều: {spots}")
            lines.append("- Tối: Chợ đêm / ẩm thực địa phương")
        elif d == days:
            lines.append(f"## Ngày {d}: Trả phòng & mua quà")
            lines.append(f"- Sáng: {spots}")
            lines.append("- Trưa: Check-out & về")
        else:
            lines.append(f"## Ngày {d}: Tham quan nổi bật")
            lines.append(f"- Cả ngày: {spots}")
            lines.append("- Tối: Show / phố đi bộ")
        lines.append("")
    return "\n".join(lines)


def suggest_restaurants(destination: str, cuisine: str = "địa phương") -> str:
    """Gợi ý quán ăn — gọi Overpass thật CÓ lọc theo `cuisine`, fallback mock khi lỗi."""
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            osm_cuisine = _CUISINE_MAP.get((cuisine or "").strip().lower())
            places = live.fetch_pois(geo["lat"], geo["lon"], kind="restaurant", cuisine=osm_cuisine)
            _set_source(_live_or_cache())
            return json.dumps(
                {"destination": destination, "cuisine": cuisine, "restaurants": places, "data_source": _LAST_SOURCE},
                ensure_ascii=False,
            )
        except live.LiveDataError:
            pass
    _set_source("mock")
    key = _norm_destination(destination)
    places = RESTAURANTS_FALLBACK.get(key, ["Quán địa phương được đánh giá cao trên Maps"])
    return json.dumps(
        {"destination": destination, "cuisine": cuisine, "restaurants": places, "data_source": "mock"},
        ensure_ascii=False,
    )


def check_budget_fit(estimated_total: int, budget: int) -> str:
    """So sánh chi phí ước tính với ngân sách người dùng (logic thuần, không gọi mạng)."""
    _set_source("computed")
    diff = budget - estimated_total
    if diff >= 0:
        return json.dumps(
            {"fits_budget": True, "remaining": diff, "message": f"Trong ngân sách, còn dư ~{diff:,} VND."},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "fits_budget": False,
            "over_by": abs(diff),
            "message": f"Vượt ngân sách ~{abs(diff):,} VND — nên giảm ngày chơi hoặc đổi khách sạn.",
        },
        ensure_ascii=False,
    )


def weather_risk_warning(destination: str) -> str:
    """Cảnh báo rủi ro thời tiết — suy từ xác suất mưa THẬT (Open-Meteo), fallback mock."""
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            w = live.fetch_weather(geo["lat"], geo["lon"])
            _set_source(_live_or_cache())
            prob = w["precip_prob"] or 0
            if prob >= 60:
                risk, warning = "high", f"Xác suất mưa ~{prob}% — hạn chế hoạt động ngoài trời, chuẩn bị áo mưa."
            elif prob >= 30:
                risk, warning = "medium", f"Xác suất mưa ~{prob}% — ưu tiên outdoor buổi sáng, tối chọn indoor."
            else:
                risk, warning = "low", f"Xác suất mưa ~{prob}% — thời tiết thuận lợi cho hoạt động ngoài trời."
            return json.dumps({"risk": risk, "warning": warning, "data_source": _LAST_SOURCE}, ensure_ascii=False)
        except live.LiveDataError:
            pass
    _set_source("mock")
    key = _norm_destination(destination)
    if key in ("đà lạt", "đà nẵng"):
        return json.dumps(
            {"risk": "medium", "warning": "Có thể mưa chiều — ưu tiên outdoor buổi sáng, tối chọn indoor.", "data_source": "mock"},
            ensure_ascii=False,
        )
    return json.dumps(
        {"risk": "low", "warning": "Thời tiết thuận lợi cho hoạt động ngoài trời.", "data_source": "mock"},
        ensure_ascii=False,
    )
