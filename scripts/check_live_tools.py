"""
Kiểm chứng các tool gọi DỮ LIỆU THẬT — KHÔNG cần LLM, KHÔNG cần API key.

Dùng để:
- Chứng minh agent đã "chọc ra ngoài" lấy realtime data (không còn fake).
- Lấy bằng chứng cho report.
- Quan sát cơ chế fallback: chạy với `USE_LIVE_TOOLS=false` để thấy nguồn 'mock'.

Usage:
  python scripts/check_live_tools.py
  # ép offline để xem fallback:
  #   Windows PowerShell:  $env:USE_LIVE_TOOLS="false"; python scripts/check_live_tools.py
"""
import os
import sys

# Windows console (cp1252) không in được tiếng Việt -> ép UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.tools import travel_tools as t


def show(label: str, value: str):
    src = t.last_data_source()
    print(f"\n[{label}]  (nguồn: {src})")
    print(value)


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "Đà Nẵng"
    print("=" * 70)
    print(f"KIỂM CHỨNG TOOL DỮ LIỆU THẬT — điểm đến: {dest}")
    print(f"USE_LIVE_TOOLS = {os.getenv('USE_LIVE_TOOLS', 'true')}")
    print("=" * 70)

    show("get_weather", t.get_weather(dest))
    show("weather_risk_warning", t.weather_risk_warning(dest))
    show("search_attractions", t.search_attractions(dest, "biển"))
    show("suggest_restaurants", t.suggest_restaurants(dest, "hải sản"))
    show("calculate_route_time", t.calculate_route_time(dest, "Hà Nội"))
    show("estimate_trip_cost", t.estimate_trip_cost(dest, 3, 2))
    show("create_itinerary", t.create_itinerary(dest, 3, 5_000_000, "biển"))

    print("\n" + "=" * 70)
    print("Xong. Nếu nguồn = 'live'/'cache' => đã lấy dữ liệu thật.")
    print("Nếu nguồn = 'mock' => đang fallback (offline / API lỗi / tắt live).")


if __name__ == "__main__":
    main()
