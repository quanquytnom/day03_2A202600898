"""Quick LLM connectivity check — uses DEFAULT_PROVIDER from .env."""
import argparse
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from src.core.factory import get_llm_provider


def _check_env(provider: str) -> bool:
    provider = provider.lower()
    if provider == "mimo":
        key = (os.getenv("MIMO_API_KEY", "") or "").strip().strip('"').strip("'")
        if not key or key.startswith("your_"):
            print("❌ Thiếu MIMO_API_KEY trong .env")
            print("   → MIMO_API_KEY=tp-...")
            print("   → MIMO_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1")
            return False
        base = os.getenv("MIMO_BASE_URL", "")
        print(f"   Base URL: {base or '(default token-plan-sgp)'}")
        return True
    if provider == "openai":
        key = (os.getenv("OPENAI_API_KEY", "") or "").strip().strip('"').strip("'")
        if not key or key.startswith("your_"):
            print("❌ Thiếu OPENAI_API_KEY trong .env")
            print("   → https://platform.openai.com/api-keys")
            return False
        return True
    if provider in ("google", "gemini"):
        key = (os.getenv("GEMINI_API_KEY", "") or "").strip().strip('"').strip("'")
        if not key or key.startswith("your_"):
            print("❌ Thiếu GEMINI_API_KEY trong .env")
            return False
        return True
    if provider == "local":
        path = os.getenv("LOCAL_MODEL_PATH", "")
        if not path or not os.path.exists(path):
            print(f"❌ Không thấy model tại LOCAL_MODEL_PATH={path}")
            return False
        return True
    print(f"❌ DEFAULT_PROVIDER không hợp lệ: {provider}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Test LLM connection")
    parser.add_argument(
        "--provider",
        choices=["openai", "mimo", "google", "gemini", "local"],
        help="Override DEFAULT_PROVIDER from .env",
    )
    parser.add_argument("--model", help="Override DEFAULT_MODEL")
    args = parser.parse_args()

    provider = (args.provider or os.getenv("DEFAULT_PROVIDER", "openai")).lower()
    print(f"Using provider = {provider}")

    if not _check_env(provider):
        if provider == "mimo":
            print("\nMẫu .env:")
            print("  DEFAULT_PROVIDER=mimo")
            print("  DEFAULT_MODEL=mimo-v2.5-pro")
            print("  MIMO_API_KEY=tp-...")
            print("  MIMO_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1")
        elif provider == "openai":
            print("\nMẫu .env:")
            print("  DEFAULT_PROVIDER=openai")
            print("  OPENAI_API_KEY=sk-proj-...")
        sys.exit(1)

    llm = get_llm_provider(provider=provider, model=args.model)
    print(f"Model: {llm.model_name}")
    try:
        r = llm.generate("Nói 'TripWise OK' trong một câu ngắn.")
        print("✅", (r.get("content") or "")[:300])
        print("Latency ms:", r.get("latency_ms"))
        print("Tokens:", r.get("usage"))
    except Exception as e:
        err = str(e)
        if provider == "openai" and ("429" in err or "insufficient_quota" in err.lower()):
            print("❌ OpenAI: hết quota / chưa nạp credit.")
            print("   → https://platform.openai.com/settings/organization/billing")
            print("   → Hoặc đổi DEFAULT_MODEL=gpt-4o-mini (rẻ hơn)")
        elif provider in ("google", "gemini") and "401" in err:
            print("❌ Gemini từ chối key — xem scripts/diagnose_gemini.py")
        elif "429" in err or "quota" in err.lower():
            print("❌ Rate limit — đợi ~30s rồi chạy lại.")
        else:
            print("❌", type(e).__name__, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
