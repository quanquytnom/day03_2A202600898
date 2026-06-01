import os
from typing import Optional

from src.core.openai_provider import OpenAIProvider

# OpenAI-compatible endpoint (see Xiaomi Mimo token plan docs)
DEFAULT_MIMO_BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"
DEFAULT_MIMO_MODEL = "mimo-v2.5-pro"


class MimoProvider(OpenAIProvider):
    """Xiaomi Mimo — OpenAI-compatible chat API."""

    def __init__(
        self,
        model_name: str = DEFAULT_MIMO_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            model_name=model_name or os.getenv("MIMO_MODEL", DEFAULT_MIMO_MODEL),
            api_key=api_key or os.getenv("MIMO_API_KEY"),
            base_url=base_url or os.getenv("MIMO_BASE_URL", DEFAULT_MIMO_BASE_URL),
            provider_name="mimo",
        )
