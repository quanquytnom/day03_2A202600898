# Individual Report: Lab 3 — Chatbot vs ReAct Agent

- **Student Name**: Trương Hải Quân
- **Student ID**: 2A202600898
- **Date**: 2026-06-01
- **Chủ đề đóng góp**: Nâng cấp TripWise từ POC fake-data → agent gọi **dữ liệu thật keyless** + observability để debug.

---

## I. Technical Contribution (15 Points)

### Bối cảnh & vấn đề phát hiện
Bản gốc TripWise là **POC chạy 100% mock data**: mọi tool chỉ tra cứu dict hardcode
(`WEATHER_DB`, `ATTRACTIONS_DB`, `RESTAURANTS_DB`, `COST_BASE_PER_DAY`) — không hề gọi
ra ngoài. Docstring gốc tự thừa nhận: *"mock travel tools… Replace with real Weather /
Places / Maps APIs in production."* Ngoài ra còn 3 lỗi thiết kế: `suggest_restaurants`
**bỏ qua tham số `cuisine`**, `calculate_route_time` **luôn trả hằng số** "20–35 phút",
`create_itinerary` **lờ địa điểm thật**; và `.env`/`.env.example` **lộ OPENAI_API_KEY thật**.

### Các module đã triển khai

| Module | Loại | Nội dung |
| :-- | :-- | :-- |
| [`src/tools/live_clients.py`](../../src/tools/live_clients.py) | **MỚI** | Lớp client gọi dữ liệu thật **keyless**: Open-Meteo (thời tiết), OpenStreetMap Overpass (POI), OSRM (định tuyến). Có timeout/retry, cache TTL, User-Agent. |
| [`src/tools/travel_tools.py`](../../src/tools/travel_tools.py) | SỬA lớn | Mỗi tool gọi API thật + **fallback mock** khi lỗi; sửa bug `cuisine`/route hằng số; gắn `data_source` (live/cache/mock/heuristic). |
| [`src/agent/agent.py`](../../src/agent/agent.py) | SỬA | Parser bền (nuốt backticks/multiline), đồng bộ EXAMPLE từ registry, **loop-guard**, **ép check_budget_fit (v2)**, `run_id` xuyên suốt, ghi `runs.jsonl`. |
| [`src/telemetry/logger.py`](../../src/telemetry/logger.py) | SỬA | Thêm `set_context()` → chèn `run_id`/`prompt_version` vào **mọi** event; ép UTF-8 cho console Windows. |
| [`src/telemetry/metrics.py`](../../src/telemetry/metrics.py) | SỬA | **Cost USD thật** theo bảng giá per-model (thay hằng số giả); `track_tool()`; `summary()`; `write_run_summary()` → `logs/runs.jsonl`. |
| [`scripts/check_live_tools.py`](../../scripts/check_live_tools.py) | **MỚI** | Kiểm chứng dữ liệu thật **không cần LLM**. |
| [`scripts/demo_offline_agent.py`](../../scripts/demo_offline_agent.py) | **MỚI** | Chạy vòng lặp ReAct bằng FakeLLM (test double cho model) khi LLM ngoài bị 429. |
| [`scripts/parse_logs.py`](../../scripts/parse_logs.py) | SỬA | Đọc `runs.jsonl` → **bảng so sánh** chatbot vs v1 vs v2. |
| [`tests/test_travel_tools.py`](../../tests/test_travel_tools.py) | SỬA | Test fallback offline + parser nuốt backticks/multiline (9 test pass). |
| `.env.example` / `README.md` | SỬA | Xoá key lộ → placeholder; cảnh báo **rotate key**; hướng dẫn live tools. |

### Code Highlights

**1) Tool gọi thật + fallback (travel_tools.py) — đồng thời sửa bug bỏ qua `cuisine`:**
```python
def suggest_restaurants(destination, cuisine="địa phương"):
    if _live_enabled():
        try:
            geo = live.geocode(destination)
            osm_cuisine = _CUISINE_MAP.get((cuisine or "").strip().lower())  # "hải sản" -> "seafood"
            places = live.fetch_pois(geo["lat"], geo["lon"], kind="restaurant", cuisine=osm_cuisine)
            _set_source(_live_or_cache())
            return json.dumps({..., "restaurants": places, "data_source": _LAST_SOURCE})
        except live.LiveDataError:
            pass               # -> fallback mock, không crash
    _set_source("mock"); ...
```

**2) Parser bền hơn (agent.py) — bỏ code-fence/backtick, không bắt nhầm trong Final Answer:**
```python
@staticmethod
def _clean(content): return content.replace("```", " ").replace("`", "")
def _extract_action(self, content):
    cut = re.split(r"Final Answer:", self._clean(content), flags=re.IGNORECASE)[0]
    for regex in (self.ACTION_RE, self.ACTION_RE_GREEDY):  # non-greedy -> greedy
        ...
```

**3) Observability — ghi 1 dòng/run vào `runs.jsonl` để keep-track & debug (metrics.py):**
```python
def write_run_summary(self, extra, log_dir="logs"):
    record = {"run_id": self.run_id, "ts": ..., "prompt_version": self.prompt_version,
              **extra, **self.summary()}   # success, steps, tokens, cost_usd, tool_source_breakdown...
    open(os.path.join(log_dir, "runs.jsonl"), "a").write(json.dumps(record) + "\n")
```

### Bằng chứng dữ liệu thật (chạy `check_live_tools.py "Đà Nẵng"`)
```
[get_weather]  (nguồn: live)   27–35°C, khả năng mưa ~4%.
[search_attractions] (live)    Cầu Sông Hàn, Cầu Trần Thị Lý, Chợ đêm Helio, ...
[suggest_restaurants] (live)   Nhà hàng hải sản Bé Anh, NĂM RẢNH HẢI SẢN, Cua Biển, ...
[calculate_route_time] (live)  Đà Nẵng → Hà Nội: ~624 phút (773.2 km, ô tô)
```

---

## II. Debugging Case Study (10 Points)

### Problem Description
Sau khi nối API thật, `get_weather` và `calculate_route_time` trả `data_source=live`,
nhưng `search_attractions` và `suggest_restaurants` **luôn rơi về `mock`** — tức tầng
live đang ném lỗi và bị fallback nuốt mất.

### Log Source
Quan sát event `TOOL_CALL` trong `logs/2026-06-01.log`:
```json
{"event": "TOOL_CALL", "data": {"tool": "search_attractions", "data_source": "mock", ...}}
```
Vì fallback che lỗi, tôi gọi thẳng tầng live để lấy lỗi gốc:
```text
ATTRACTION ERROR -> LiveDataError('HTTP failed ... overpass-api.de ...: HTTP Error 406: Not Acceptable')
```

### Diagnosis (chẩn đoán theo phương pháp loại trừ)
Thử đổi **User-Agent** thấy hành vi đổi theo, chứng tỏ nguyên nhân nằm ở header:

| User-Agent gửi lên | Kết quả | Suy luận |
| :-- | :-- | :-- |
| `...Agent/1.0 (educational; contact: ...)` | **406 Not Acceptable** | WAF của overpass-api.de **chặn UA có dấu ngoặc `()`** |
| `Mozilla/5.0`, `curl/8.0`, rỗng | 406 | Chặn cả UA generic/blank |
| `TripWise-Lab3-Agent/1.0` (gọn) | **504 Gateway Timeout** | Đã **qua WAF**, server xử lý nhưng **truy vấn quá nặng/chậm** |

→ **Hai nguyên nhân chồng nhau**: (1) UA chứa `()` → bị WAF trả 406; (2) sau khi sửa UA,
truy vấn Overpass mất **~24s** trong khi `HTTP_TIMEOUT_SEC` mặc định chỉ **6s** → timeout → fallback.
Đây đúng tinh thần *"Fail Early, Learn Fast"*: chính **lớp fallback** đã giữ agent không sập,
còn **log + data_source** giúp khoanh vùng lỗi nhanh.

### Solution
Trong [`live_clients.py`](../../src/tools/live_clients.py):
1. **UA gọn, không ký tự đặc biệt**: `USER_AGENT = "TripWise-Lab3-Agent/1.0"` + header `Accept: application/json`.
2. **Timeout riêng cho Overpass**: `OVERPASS_TIMEOUT_SEC = 25` (tách khỏi timeout 6s của các API nhanh).
3. **Nhẹ hoá truy vấn**: dùng tag chính xác `tourism=attraction` (thay regex nhiều giá trị); bán kính nhà hàng nhỏ hơn (3 km).

**Kết quả (sau fix):** `data_source=live` với POI thật:
```json
{"tool":"search_attractions","data_source":"live","tool_latency_ms":23375,
 "observation":"...Cầu Sông Hàn, Chợ đêm Helio..."}
```

### Bonus bug: Windows console `UnicodeEncodeError`
`logs`/script in tiếng Việt làm console cp1252 ném `UnicodeEncodeError: 'Ể'`.
Khắc phục: ép `sys.stdout/stderr.reconfigure(encoding="utf-8")` trong `logger.py` và các script.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning — khối `Thought` giúp gì?
ReAct **chia bài toán thành chuỗi bước có kiểm chứng**:
`get_weather → search_attractions → estimate_trip_cost → check_budget_fit → create_itinerary`.
Chatbot baseline trả lời **một phát**, và system prompt của nó tự thừa nhận *"You do NOT have
access to live weather, prices, or maps"* — nên không thể đưa nhiệt độ thật hay xác minh ngân sách.
Quan trọng hơn: **khi tool còn là mock, "reasoning" chỉ là diễn** — agent suy luận trên số bịa.
Sau khi nối **dữ liệu thật**, vòng lặp mới thực sự có cơ sở (grounding).

### 2. Reliability — khi nào Agent *tệ hơn* Chatbot?
Số liệu thật từ `logs/runs.jsonl` (model **gpt-4o**, đo bằng `scripts/parse_logs.py`):

| version | steps | total_tokens | cost_usd | nguồn tool |
| :-- | --: | --: | --: | :-- |
| chatbot | 1 | 391 | $0.0033 | (không tool) |
| v1 | 1 | 1.413 | $0.0045 | live ×1 |
| v2 | 5 | 7.817 | $0.0228 | live ×2, heuristic, computed, cache |

- **Độ trễ & chi phí**: v2 tốn **~20× token** và **~7× chi phí** so với chatbot; riêng 1 bước Overpass
  mất **~24–30s** (trace thật `run_id=5d5d74c2855e`, step 2 = 29.805 ms).
- **Khuếch đại rate-limit**: agent gọi LLM nhiều lần/bước nên **đụng HTTP 429 nhanh hơn** — lần chạy
  end-to-end đầu (provider Mimo) đã bị 429; sau khi **đổi sang OpenAI gpt-4o** thì chạy trọn vẹn.
- **Mong manh định dạng**: nếu model lệch format `Action:` thì gãy parse (đã giảm thiểu bằng parser mới,
  nhưng chưa triệt để như native function-calling).
→ Với câu hỏi **mơ hồ/chung chung**, chatbot rẻ–nhanh–đủ dùng; ReAct chỉ thắng khi cần **nhiều bước + dữ liệu thật**.

### 3. Observation — phản hồi môi trường định hướng bước sau thế nào?
Observation thật **đổi quyết định**: `check_budget_fit(9.600.000, 8.000.000)` trả
`fits_budget=false, over_by=1.600.000` — đây là tín hiệu để agent **cắt giảm ngày/đổi khách sạn**
trước khi chốt. Tương tự, `weather_risk` suy từ **xác suất mưa thật 4% → "low"** thay vì đoán mò.
Cơ chế `data_source` cho thấy rõ observation đến từ `live` hay `mock` — minh bạch để tin hay nghi kết quả.

---

## IV. Future Improvements (5 Points)

- **Bỏ regex → Native Function/Tool Calling** (OpenAI tools / Anthropic tool use): chấm dứt lỗi parse,
  schema-validated arguments, song song nhiều tool.
- **Scalability — async + caching**: gọi tool song song (asyncio) và cache POI bằng Redis để giấu
  độ trễ ~23s của Overpass; thêm circuit-breaker khi nguồn live chậm.
- **Safety — Supervisor LLM + Secrets**: một LLM "giám sát" thẩm định plan trước khi trả; quản lý
  secret bằng vault và **rotate ngay key đã lộ** (phát hiện trong lab này).
- **Performance — RAG/Vector tool-retrieval**: khi số tool tăng, dùng vector DB để chọn đúng tool;
  RAG cho mô tả địa điểm chi tiết.
- **Dữ liệu giàu hơn (có phí)**: Google Places (rating/giờ mở cửa), API đặt phòng/vé để thay
  `estimate_trip_cost` heuristic bằng **giá thị trường thật**.

---

> [!NOTE]
> Toàn bộ thay đổi đã verify: `pytest` 9/9 pass; `check_live_tools.py` cho `data_source=live`;
> chạy **end-to-end thật với gpt-4o** thành công (`run_id=5d5d74c2855e`, success=true, budget_verified=true,
> cost $0.0228) và ghi `logs/runs.jsonl`; `parse_logs.py` in bảng so sánh chatbot/v1/v2.
> (`demo_offline_agent.py` + FakeLLM chỉ dùng dự phòng khi provider bị rate-limit.)
