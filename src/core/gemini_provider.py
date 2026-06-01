import os
import re
import time
import warnings
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.core.llm_provider import LLMProvider

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"
FALLBACK_MODELS: List[str] = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]


def _normalize_model_name(name: str) -> str:
    name = (name or DEFAULT_GEMINI_MODEL).strip()
    if name.startswith("models/"):
        name = name.split("/", 1)[1]
    legacy = {
        "gemini-1.5-flash": "gemini-2.0-flash-lite",
        "gemini-1.5-pro": "gemini-2.5-pro",
    }
    return legacy.get(name, name)


def _retry_delay_seconds(exc: Exception) -> int:
    m = re.search(r"retry in ([\d.]+)s", str(exc), re.IGNORECASE)
    if m:
        return int(float(m.group(1))) + 2
    return 35


def _is_rate_limit(exc: Exception) -> bool:
    err = str(exc).lower()
    return "429" in err or "resourceexhausted" in err or "quota" in err


def _get_genai_client(api_key: str):
    """google-genai SDK — supports AIza... and AQ.... keys from AI Studio."""
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = DEFAULT_GEMINI_MODEL, api_key: Optional[str] = None):
        model_name = _normalize_model_name(model_name)
        api_key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
        if not api_key:
            raise ValueError("Thiếu GEMINI_API_KEY trong .env")

        super().__init__(model_name, api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
        self._client = _get_genai_client(api_key)
        self._models_to_try = [model_name] + [m for m in FALLBACK_MODELS if m != model_name]
        self._max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))

    def _generate_with_fallback(self, full_prompt: str, system_prompt: Optional[str] = None):
        last_error = None
        config = None
        if system_prompt:
            from google.genai import types

            config = types.GenerateContentConfig(system_instruction=system_prompt)

        for name in self._models_to_try:
            for attempt in range(self._max_retries + 1):
                try:
                    kwargs = {"model": name, "contents": full_prompt}
                    if config:
                        kwargs["config"] = config
                    response = self._client.models.generate_content(**kwargs)
                    return response, name
                except Exception as e:
                    last_error = e
                    if _is_rate_limit(e) and attempt < self._max_retries:
                        time.sleep(_retry_delay_seconds(e))
                        continue
                    err = str(e).lower()
                    if "not found" in err or "404" in err:
                        break
                    raise
        raise last_error

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        response, used_model = self._generate_with_fallback(prompt, system_prompt)
        self.model_name = used_model

        content = getattr(response, "text", None) or ""
        usage_meta = getattr(response, "usage_metadata", None)
        usage = {
            "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
            "completion_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
            "total_tokens": getattr(usage_meta, "total_token_count", 0) or 0,
        }

        return {
            "content": content,
            "usage": usage,
            "latency_ms": int((time.time() - start_time) * 1000),
            "provider": "google",
            "model": used_model,
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"

        for chunk in self._client.models.generate_content_stream(
            model=self.model_name, contents=full_prompt
        ):
            if chunk.text:
                yield chunk.text
