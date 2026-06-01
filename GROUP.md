# KẾ HOẠCH PHÂN CHIA CÔNG VIỆC DỰ ÁN: TRIPWISE AGENT

Chào cả nhà, đây là kế hoạch phân chia công việc chi tiết cho 9 thành viên trong dự án **TripWise Agent** (Hệ thống trợ lý AI lên kế hoạch du lịch thông minh dựa trên kiến trúc ReAct). 

Mọi người chủ động xem đúng số thứ tự (**Người 1 đến Người 9**), vai trò và các tệp tin (*Deliverable*) mình cần phải hoàn thành và bàn giao lên hệ thống chung.

---

## I. CẤU TRÚC CHIA NHÓM TỔNG QUAN

Dự án được chia làm 3 nhóm chuyên trách để đảm bảo tiến độ chạy song song:
- **TEAM 1: Problem + Product + Demo** (Định hình bài toán, thiết kế prompt và kịch bản demo).
- **TEAM 2: Tool/API Development** (Xây dựng các công cụ, hàm Python lấy dữ liệu thực tế cho Agent gọi).
- **TEAM 3: Agent + Evaluation + Report** (Lập trình vòng lặp ReAct, đo đạc hiệu năng và đóng gói báo cáo).
---

## II. PHÂN CHIA VIỆC CHI TIẾT THEO TỪNG THÀNH VIÊN

### ─── TEAM 1: PRODUCT, UX PROMPT & DEMO ───

#### 📌 Người 1 — Product Owner (PO)
* **Nhiệm vụ:** Định hình bài toán, xác định các nỗi đau của người dùng (User pain points), xác định phạm vi của bản MVP (Minimum Viable Product). Viết phần lập luận cốt lõi: *"Tại sao phải dùng AI Agent thay vì một Chatbot thông thường?"*.
* **Tệp tin cần bàn giao:** `report/problem_statement.md`

#### 📌 Người 2 — UX/Prompt Designer
* **Nhiệm vụ:** Thiết kế cấu trúc câu lệnh hệ thống (System Prompt). Bao gồm: prompt cho chatbot baseline (để làm đối chứng) và prompt nghiêm ngặt cho ReAct Agent (ép mô hình suy nghĩ theo dạng `Thought -> Action -> Action Input`). Thiết kế format đầu ra của lịch trình (đảm bảo hiển thị dạng bảng đẹp, có thời tiết, chi tiết chi phí).
* **Tệp tin cần bàn giao:** `prompts/baseline_prompt.txt` và `prompts/react_agent_prompt.txt`

#### 📌 Người 3 — Demo & Test Case Owner
* **Nhiệm vụ:** Chuẩn bị sẵn ít nhất 5 kịch bản thử nghiệm (Test cases) đa dạng từ dễ đến khó (Ví dụ: Đà Nẵng biển 3N2Đ - 5 triệu; Đà Lạt nghỉ dưỡng 4N3Đ - 6 triệu; Nha Trang tiết kiệm; Hà Giang trải nghiệm; Phú Quốc gia đình có trẻ nhỏ). Chạy thử nghiệm để so sánh kết quả trực quan giữa Chatbot thuần và Agent xem Agent có gọi đúng tool không, kết quả có thực tế hơn không.
* **Tệp tin cần bàn giao:** `demo/test_cases.md` và `demo/demo_script.md`

---

### ─── TEAM 2: TOOL/API DEVELOPMENT ───

#### 📌 Người 4 — Weather Tool Developer
* **Nhiệm vụ:** Viết hàm Python xử lý dữ liệu thời tiết. Bản MVP đầu tiên sẽ làm dạng dữ liệu giả định (Mock data) trả về thời tiết, nhiệt độ và lời khuyên trang phục dựa theo điểm đến. Bản nâng cấp sẽ tích hợp gọi API thực tế (như OpenWeatherMap hoặc WeatherAPI).
* **Tệp tin cần bàn giao:** `src/tools/weather_tool.py`

#### 📌 Người 5 — Places/Attraction Tool Developer
* **Nhiệm vụ:** Viết hàm Python tìm kiếm địa điểm. Trả về danh sách các điểm tham quan, quán ăn ngon, khách sạn phù hợp với bộ lọc sở thích (style) của người dùng (như: đi biển, nghỉ dưỡng, chụp ảnh, mạo hiểm). Bản nâng cấp có thể tích hợp Google Places API hoặc SerpAPI.
* **Tệp tin cần bàn giao:** `src/tools/places_tool.py`

#### 📌 Người 6 — Cost & Budget Tool Developer
* **Nhiệm vụ:** Viết hàm Python tính toán tài chính. Tiếp nhận số ngày đi, số người, tổng ngân sách để tự động nhân chuỗi chi phí (phòng khách sạn, ăn uống, vé tham quan, di chuyển). Hàm phải trả về được tổng tiền và trạng thái Boolean (`True/False`) xem có bị vượt ngân sách của người dùng hay không để Agent biết đường tự điều chỉnh.
* **Tệp tin cần bàn giao:** `src/tools/cost_tool.py`

---

### ─── TEAM 3: AGENTCORE, EVALUATION & REPORT ───

#### 📌 Người 7 — ReAct Agent Developer
* **Nhiệm vụ:** Đây là phần xương sống kỹ thuật của dự án. Chịu trách nhiệm kết nối với mô hình ngôn ngữ lớn (LLM API), nạp danh sách 3 công cụ của nhóm 2 vào hệ thống, và lập trình vòng lặp ReAct (`Thought -> Action -> Action Input -> Observation -> Final Answer`). Xử lý bóc tách chuỗi bằng Regex để Agent không bị gãy luồng khi gọi tool.
* **Tệp tin cần bàn giao:** `src/agent/agent.py` và `src/agent/prompts.py`

#### 📌 Người 8 — Evaluation & Logging Owner
* **Nhiệm vụ:** Thiết lập hệ thống ghi nhật ký (Log) và đo đạc hiệu năng của Agent. Cần thống kê các chỉ số (Metrics) quan trọng: Số lượt gọi tool (Number of tool calls), độ trễ (Latency), tỷ lệ lỗi định dạng (Parse error), lỗi công cụ (Tool error), độ chính xác của bài toán chi phí và chất lượng câu trả lời cuối cùng. Làm bảng so sánh Agent V1 vs Agent V2 vs Baseline.
* **Tệp tin cần bàn giao:** Toàn bộ thư mục `logs/` và file báo cáo đánh giá `evaluation/evaluation_result.md`

#### 📌 Người 9 — Report & Slide Owner
* **Nhiệm vụ:** Tổng hợp toàn bộ tài liệu từ các thành viên để hoàn thiện báo cáo nhóm (Group Report) theo cấu trúc chuẩn bài tập lớn. Thu thập phản hồi cá nhân (Individual reflection), vẽ sơ đồ kiến trúc (Architecture workflow) và thiết kế slide thuyết trình cuối cùng cho cả nhóm.
* **Tệp tin cần bàn giao:** `report/group_report.md` và `slides/presentation.pdf`

---

## III. QUY TRÌNH PHỐI HỢP VÀ CẤU TRÚC THƯ MỤC CHUẨN

Để tránh việc code đè lên nhau khi đẩy lên GitHub, dự án sẽ tuân thủ cấu trúc thư mục nghiêm ngặt sau. Mọi người lưu ý tạo đúng tên file và đặt đúng vị trí:

```text
tripwise-agent/
├── demo/
│   ├── demo_script.md
│   └── test_cases.md
├── evaluation/
│   └── evaluation_result.md
├── prompts/
│   ├── baseline_prompt.txt
│   └── react_agent_prompt.txt
├── report/
│   ├── group_report.md
│   └── problem_statement.md
├── slides/
│   └── presentation.pdf
└── src/
    ├── agent/
    │   ├── agent.py
    │   └── prompts.py
    └── tools/
        ├── cost_tool.py
        ├── places_tool.py
        └── weather_tool.py