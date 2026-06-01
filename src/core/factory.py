import os
from typing import Optional

from src.core.gemini_provider import GeminiProvider
from src.core.llm_provider import LLMProvider
from src.core.local_provider import LocalProvider
from src.core.mimo_provider import MimoProvider
from src.core.openai_provider import OpenAIProvider


def get_llm_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """Build LLM provider from environment variables."""
    provider = (provider or os.getenv("DEFAULT_PROVIDER", "openai")).lower()
    model = model or os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider == "openai":
        return OpenAIProvider(model_name=model, api_key=os.getenv("OPENAI_API_KEY"))
    if provider == "mimo":
        return MimoProvider(
            model_name=model or os.getenv("MIMO_MODEL", "mimo-v2.5-pro"),
            api_key=os.getenv("MIMO_API_KEY"),
        )
    if provider in ("google", "gemini"):
        if not model or model.startswith("gpt") or "1.5-flash" in model:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        return GeminiProvider(model_name=model, api_key=os.getenv("GEMINI_API_KEY"))
    if provider == "local":
        path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=path)

    raise ValueError(f"Unknown provider: {provider}. Use openai | mimo | google | local")
