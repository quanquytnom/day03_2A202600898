import logging
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Windows console (cp1252) không in được tiếng Việt -> ép UTF-8 cho stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

class IndustryLogger:
    """
    Structured logger mô phỏng thực hành công nghiệp.
    Ghi JSON ra cả console và file logs/YYYY-MM-DD.log.

    NÂNG CẤP: hỗ trợ "context" (vd run_id) tự động chèn vào MỌI event,
    nhờ đó có thể lọc trọn vẹn 1 trace của một lần chạy agent để debug.
    """
    def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.log_dir = log_dir
        self._context: Dict[str, Any] = {}

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Tránh add handler trùng nếu logger được khởi tạo lại
        if not self.logger.handlers:
            log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            console_handler = logging.StreamHandler()
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def set_context(self, **kwargs: Any) -> None:
        """Gắn các trường (vd run_id, prompt_version) vào mọi event tiếp theo."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        self._context = {}

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Ghi một event kèm timestamp, loại, và context hiện tại (run_id...)."""
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            **self._context,
            "data": data,
        }
        self.logger.info(json.dumps(payload, ensure_ascii=False))

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str, exc_info=True):
        self.logger.error(msg, exc_info=exc_info)

# Global logger instance
logger = IndustryLogger()
