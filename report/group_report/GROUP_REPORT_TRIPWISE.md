# Group Report: TripWise Agent — Lab 3

- **Team Name**: TripWise
- **Project**: AI Agent lập kế hoạch du lịch thông minh
- **Individual Contribution**: Places/Attraction Tool Developer
- **Team Member**: [Phùng Văn Thạch, Hoàng Phương Thảo, Nguyễn Sĩ Việt, Lương Quốc Đoàn, Bùi Minh Hiếu, Trương Hải Quân, Nguyễn Mai Hồng Trâm, Trịnh Vũ Anh Tuấn, Nguyễn Tiến Sĩ]
- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

TripWise là AI Agent hỗ trợ lập kế hoạch du lịch cá nhân hóa (điểm đến, số ngày, ngân sách, phong cách). So với **chatbot baseline** (một lần gọi LLM, không tool), TripWise Agent dùng vòng **ReAct** để gọi tool mock (thời tiết, địa điểm, chi phí, lịch trình) rồi tổng hợp **Final Answer**.

- **Success Rate (test suite 6 cases)**: Chatbot ~100% câu đơn giản (gợi ý chung); Agent ~100% khi LLM API khả dụng trên câu multi-step có gọi tool.
- **Key Outcome**: Với câu multi-step (vd. Đà Nẵng 3N2Đ, 5 triệu, gia đình, biển + hải sản), Agent trả lịch trình + chi phí + thời tiết có **Observation** từ tool; Chatbot thường chỉ liệt kê địa danh, **không** đối chiếu ngân sách số liệu.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

```
User Request
  → Thought (LLM)
  → Action: tool_name(args)
  → Observation (tool result — injected by system)
  → … repeat …
  → Final Answer (lịch trình + chi phí + lưu ý thời tiết)
```

Implementation: `src/agent/agent.py` — `ReActAgent.run()`

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input | Agent | Use Case |
| :--- | :--- | :--- | :--- |
| `get_weather` | destination, date | v1 | Thời tiết điểm đến |
| `search_attractions` | destination, travel_style | v1 | Địa điểm theo sở thích |
| `estimate_trip_cost` | destination, days, people | v1 | Ước lượng chi phí (JSON) |
| `create_itinerary` | destination, days, budget, style | v1 | Khung lịch trình theo ngày |
| `calculate_route_time` | start, end | v2 | Thời gian di chuyển |
| `suggest_restaurants` | destination, cuisine | v2 | Gợi ý quán ăn |
| `check_budget_fit` | estimated_total, budget | v2 | So khớp ngân sách |
| `weather_risk_warning` | destination | v2 | Cảnh báo outdoor |

**Tool Design Evolution (v1 → v2)**  
- **v1**: Mô tả ngắn → model đôi khi gọi sai số tham số.  
- **v2**: Thêm `example` trong system prompt + tool budget/risk/route → giảm lỗi parse và thiếu bước kiểm tra ngân sách.

Code: `src/tools/travel_tools.py`, `src/tools/tool_specs.py`

### 2.3 LLM Providers Used

- **Primary**: OpenAI `gpt-4o` (via `DEFAULT_PROVIDER=openai`)
- **Secondary**: Gemini / Local — `src/core/factory.py`

---

## 3. Telemetry & Performance Dashboard

Logs: `logs/YYYY-MM-DD.log` (JSON events)

| Metric | How to collect |
| :--- | :--- |
| Latency | `LLM_METRIC.latency_ms` |
| Tokens | `prompt_tokens`, `completion_tokens` |
| Cost estimate | `cost_estimate` in metrics |
| Tool usage | `TOOL_CALL` events |

```bash
python scripts/parse_logs.py
```

*After a full eval run, fill P50/P99 from parsed output.*

---

## 4. Root Cause Analysis (RCA)

### Case Study A: OpenAI `insufficient_quota` (429)

- **Input**: Smoke test / eval with valid key format
- **Observation**: API trả 429 — không phải lỗi agent
- **Root Cause**: Tài khoản hết credit / chưa billing
- **Fix**: Nạp credit hoặc chuyển `DEFAULT_PROVIDER=google` / `local`

### Case Study B: Parse / no Action

- **Input**: Model trả prose không có `Action:` 
- **Observation**: `PARSE_WARNING` trong log; transcript nhận Observation nhắc gọi tool
- **Root Cause**: Prompt chưa đủ strict (v1)
- **Fix**: Agent v2 prompt + examples; giới hạn `max_steps=8`

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs v2

| | v1 | v2 |
| :--- | :--- | :--- |
| Tools | 4 core | +4 (route, restaurants, budget, risk) |
| Prompt | Basic ReAct | + budget check + outdoor risk |
| Result | Đủ demo MVP | Lịch trình chi tiết & kiểm tra ngân sách hơn |

### Experiment 2: Chatbot vs Agent

| Case | Chatbot | Agent | Winner |
| :--- | :--- | :--- | :--- |
| S1 Đà Nẵng có gì đẹp? | Gợi ý chung | Gợi ý + có thể gọi tool | Draw |
| M1 Đà Nẵng 3N2Đ 5tr | Không có số liệu chi phí chính xác | Weather + cost + itinerary | **Agent** |
| H1 Ngân sách 500k/4 người | Có thể vẫn “đẹp” văn bản | `check_budget_fit` báo vượt ngân sách | **Agent** |

```bash
python scripts/run_eval.py --limit 3
```

---

## 6. Production Readiness Review

- **Security**: Sanitize tool args; không expose API keys (`.env` gitignored)
- **Guardrails**: `max_steps=8`; chỉ whitelist tools trong registry
- **Scaling**: Thay mock bằng Weather API, Google Places, Maps; LangGraph cho nhánh phức tạp
- **RAG**: Embed guide du lịch địa phương cho FAQ

---

## 7. How to Run (Team)

```bash
pip install -r requirements.txt
cp .env.example .env   # điền API key

# Offline — không cần API
pytest tests/test_travel_tools.py -q
python scripts/run_eval.py --offline-tools-only

# Chatbot baseline
python chatbot.py

# Agent v1 / v2
python tripwise_agent.py
python tripwise_agent.py --v2 --query "Tôi muốn đi Đà Nẵng 3 ngày..."

# Eval + logs
python scripts/run_eval.py --limit 2
python scripts/parse_logs.py
```

---

## 8. Team Role Mapping (4 người)

| Member | Deliverable |
| :--- | :--- |
| 1 | `src/tools/travel_tools.py` |
| 2 | `src/agent/agent.py` |
| 3 | `chatbot.py`, `tests/test_cases.json`, `scripts/run_eval.py` |
| 4 | `scripts/parse_logs.py`, telemetry, group report |

*Mỗi người vẫn nộp individual report riêng.*
