# Lab 3: Chatbot vs ReAct Agent (Industry Edition)

Welcome to Phase 3 of the Agentic AI course! This lab focuses on moving from a simple LLM Chatbot to a sophisticated **ReAct Agent** with industry-standard monitoring.

## 🚀 Getting Started

### 1. Setup Environment
Copy the `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Directory Structure
- `src/tools/live_clients.py`: **Keyless live-data layer** (Open-Meteo / OpenStreetMap Overpass / OSRM)
- `src/tools/travel_tools.py`: TripWise travel tools — **gọi API thật + fallback mock**
- `chatbot.py`: Baseline chatbot (no tools)
- `tripwise_agent.py`: ReAct agent CLI (v1 / v2)
- `scripts/check_live_tools.py`: **Kiểm chứng dữ liệu thật (không cần LLM)**
- `scripts/run_eval.py`: Compare chatbot vs agent
- `scripts/parse_logs.py`: **Bảng so sánh telemetry (đọc `logs/runs.jsonl`)**
- `report/group_report/GROUP_REPORT_TRIPWISE.md`: Group submission template (filled)

> ⚠️ **Security**: bản gốc lỡ commit `OPENAI_API_KEY` thật trong `.env`/`.env.example`.
> Hãy **rotate (thu hồi) key đó ngay** trên dashboard nhà cung cấp; `.env.example` nay chỉ còn placeholder.
> Không bao giờ commit `.env` thật (kiểm tra `.gitignore`).

### 3.1. Dữ liệu thật (realtime) & fallback
Các tool giờ "chọc ra ngoài" lấy dữ liệu thật **miễn phí, không cần key**:
- Thời tiết & rủi ro mưa → **Open-Meteo**
- Địa điểm / quán ăn (POI) → **OpenStreetMap Overpass**
- Thời gian di chuyển → **OSRM**

Mỗi tool tự **fallback về mock** khi offline/lỗi (gắn nhãn `data_source = live | cache | mock`).
Tắt gọi mạng để chạy hoàn toàn offline: đặt `USE_LIVE_TOOLS=false` trong `.env`.
Kiểm chứng nhanh không cần LLM:
```bash
python scripts/check_live_tools.py "Đà Nẵng"
```

### 4. TripWise Quick Start (Mimo / OpenAI)

**Mimo (OpenAI-compatible):**
```bash
cp .env.example .env   # điền MIMO_API_KEY (tp-...)
# DEFAULT_PROVIDER=mimo  MIMO_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
python scripts/smoke_test.py
python tripwise_agent.py --v2
```

**OpenAI:** set `DEFAULT_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`

```bash
pytest tests/test_travel_tools.py -q          # offline, no API
python chatbot.py                           # baseline
python scripts/run_eval.py --limit 2        # evaluation
```

## 🏠 Running with Local Models (CPU)

If you don't want to use OpenAI or Gemini, you can run open-source models (like Phi-3) directly on your CPU using `llama-cpp-python`.

### 1. Download the Model
Download the **Phi-3-mini-4k-instruct-q4.gguf** (approx 2.2GB) from Hugging Face:
- [Phi-3-mini-4k-instruct-GGUF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)
- Direct Download: [phi-3-mini-4k-instruct-q4.gguf](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf)

### 2. Place Model in Project
Create a `models/` folder in the root and move the downloaded `.gguf` file there.

### 3. Update `.env`
Change your `DEFAULT_PROVIDER` and set the path:
```env
DEFAULT_PROVIDER=local
LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
```

## 🎯 Lab Objectives

1.  **Baseline Chatbot**: Observe the limitations of a standard LLM when faced with multi-step reasoning.
2.  **ReAct Loop**: Implement the `Thought-Action-Observation` cycle in `src/agent/agent.py`.
3.  **Provider Switching**: Swap between OpenAI and Gemini seamlessly using the `LLMProvider` interface.
4.  **Failure Analysis**: Use the structured logs in `logs/` to identify why the agent fails (hallucinations, parsing errors).
5.  **Grading & Bonus**: Follow the [SCORING.md](file:///Users/tindt/personal/ai-thuc-chien/day03-lab-agent/SCORING.md) to maximize your points and explore bonus metrics.

## 🛠️ How to Use This Baseline
The code is designed as a **Production Prototype**. It includes:
- **Telemetry**: Every action is logged in JSON format for later analysis.
- **Robust Provider Pattern**: Easily extendable to any LLM API.
- **Clean Skeletons**: Focus on the logic that matters—the agent's reasoning process.

---

*Happy Coding! Let's build agents that actually work.*
