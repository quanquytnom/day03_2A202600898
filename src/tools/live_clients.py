"""
TripWise — lớp client gọi dữ liệu thật, KHÔNG cần API key.

Tất cả nguồn ở đây đều free + keyless:
- Open-Meteo Geocoding/Forecast  (thời tiết, toạ độ)        https://open-meteo.com
- OpenStreetMap Overpass API     (địa điểm / quán ăn POI)   https://overpass-api.de
- OSRM demo server               (thời gian di chuyển thật) https://router.project-osrm.org

Nguyên tắc:
- Mỗi hàm raise gọn (LiveDataError) khi lỗi/timeout để tầng tool (travel_tools.py)
  bắt và fallback về mock — nhờ vậy lab vẫn chạy được khi offline.
- Có cache TTL (in-memory) + User-Agent mô tả để tôn trọng rate limit của
  Overpass/Nominatim (các endpoint cộng đồng).
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# --- Cấu hình (đọc từ env, có default an toàn) ---
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "6"))
# Overpass chậm hơn nhiều API khác -> timeout riêng dài hơn.
OVERPASS_TIMEOUT_SEC = float(os.getenv("OVERPASS_TIMEOUT_SEC", "25"))
POI_RADIUS_M = int(os.getenv("POI_RADIUS_M", "5000"))
CACHE_TTL_SEC = float(os.getenv("LIVE_CACHE_TTL_SEC", "900"))  # 15 phút
# LƯU Ý: overpass-api.de chặn (HTTP 406) các User-Agent có dấu ngoặc đơn '()'.
# Giữ UA gọn, không ký tự đặc biệt.
USER_AGENT = "TripWise-Lab3-Agent/1.0"

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


class LiveDataError(Exception):
    """Lỗi khi gọi dữ liệu thật — tầng tool sẽ bắt để fallback về mock."""


# --- Cache TTL đơn giản (in-memory) ---
_CACHE: Dict[str, Tuple[float, Any]] = {}


def _cache_get(key: str) -> Optional[Any]:
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > CACHE_TTL_SEC:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def last_call_from_cache() -> bool:
    """Cho tầng tool biết observation vừa rồi lấy từ cache hay gọi mạng thật."""
    return _LAST_FROM_CACHE


_LAST_FROM_CACHE = False


# --- HTTP helpers (chuẩn lib, không cần `requests`) ---
def _http_request(
    url: str, *, data: Optional[bytes] = None, retries: int = 2, timeout: Optional[float] = None
) -> Dict[str, Any]:
    """GET (data=None) hoặc POST (data=bytes). Trả JSON đã parse. Raise LiveDataError khi hỏng."""
    global _LAST_FROM_CACHE
    timeout = timeout or HTTP_TIMEOUT_SEC
    cache_key = url + (("|" + data.decode("utf-8", "ignore")) if data else "")
    cached = _cache_get(cache_key)
    if cached is not None:
        _LAST_FROM_CACHE = True
        return cached

    _LAST_FROM_CACHE = False
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            _cache_set(cache_key, payload)
            return payload
        except Exception as e:  # noqa: BLE001 — gom mọi lỗi mạng/timeout/parse
            last_err = e
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))  # backoff nhẹ
    raise LiveDataError(f"HTTP failed for {url[:80]}...: {last_err}")


def _http_get(base: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return _http_request(f"{base}?{urllib.parse.urlencode(params)}")


# --- Geocoding: tên địa điểm -> toạ độ ---
def geocode(place: str) -> Dict[str, Any]:
    """Trả {'lat', 'lon', 'name'} từ Open-Meteo Geocoding. Raise LiveDataError nếu không thấy."""
    data = _http_get(OPEN_METEO_GEO, {"name": place, "count": 1, "language": "vi", "format": "json"})
    results = data.get("results") or []
    if not results:
        raise LiveDataError(f"Không geocode được '{place}'")
    top = results[0]
    return {
        "lat": top["latitude"],
        "lon": top["longitude"],
        "name": top.get("name", place),
        "country": top.get("country", ""),
    }


# --- Thời tiết thật (Open-Meteo Forecast) ---
def fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Dự báo 1 ngày tới: nhiệt độ max/min + xác suất mưa. Raise LiveDataError nếu hỏng."""
    data = _http_get(
        OPEN_METEO_FORECAST,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    daily = data.get("daily") or {}
    try:
        return {
            "temp_max": daily["temperature_2m_max"][0],
            "temp_min": daily["temperature_2m_min"][0],
            "precip_prob": daily["precipitation_probability_max"][0],
        }
    except (KeyError, IndexError, TypeError) as e:
        raise LiveDataError(f"Forecast thiếu dữ liệu: {e}")


# --- POI thật (OpenStreetMap Overpass) ---
def fetch_pois(lat: float, lon: float, kind: str, cuisine: Optional[str] = None, limit: int = 8) -> List[str]:
    """
    Lấy danh sách POI quanh toạ độ.
    kind='attraction' -> tourism=attraction; kind='restaurant' -> amenity=restaurant (lọc cuisine nếu có).
    """
    server_timeout = int(OVERPASS_TIMEOUT_SEC)
    if kind == "restaurant":
        cuisine_filter = f'["cuisine"~"{cuisine}",i]' if cuisine else ""
        # Bán kính nhỏ hơn cho nhà hàng (mật độ dày) -> truy vấn nhanh hơn.
        radius = min(POI_RADIUS_M, 3000)
        selector = f'node["amenity"="restaurant"]{cuisine_filter}(around:{radius},{lat},{lon});'
    else:
        # Dùng tag chính xác tourism=attraction (nhẹ hơn regex nhiều giá trị).
        selector = f'node["tourism"="attraction"](around:{POI_RADIUS_M},{lat},{lon});'
    query = f"[out:json][timeout:{server_timeout}];{selector}out body {limit * 3};"
    payload = _http_request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        timeout=OVERPASS_TIMEOUT_SEC,
    )

    names: List[str] = []
    for el in payload.get("elements", []):
        name = (el.get("tags") or {}).get("name")
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    if not names:
        raise LiveDataError(f"Overpass không trả POI cho ({lat},{lon}) kind={kind}")
    return names


# --- Thời gian di chuyển thật (OSRM) ---
def route(start_latlon: Tuple[float, float], end_latlon: Tuple[float, float]) -> Dict[str, Any]:
    """Trả {'minutes', 'km'} bằng OSRM driving. Raise LiveDataError nếu hỏng."""
    (lat1, lon1), (lat2, lon2) = start_latlon, end_latlon
    url = f"{OSRM_URL}/{lon1},{lat1};{lon2},{lat2}"
    data = _http_get(url, {"overview": "false"})
    routes = data.get("routes") or []
    if not routes:
        raise LiveDataError("OSRM không tìm được tuyến đường")
    r = routes[0]
    return {
        "minutes": round(r["duration"] / 60),
        "km": round(r["distance"] / 1000, 1),
    }
