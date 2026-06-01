"""Kiểm tra GEMINI_API_KEY — không in full key."""
import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
print("=== Gemini key diagnostic ===\n")
print(f"Prefix: {key[:10]}..." if key else "EMPTY")
print(f"Length: {len(key)}")
print(f"DEFAULT_MODEL: {os.getenv('DEFAULT_MODEL')}")

if not key:
    print("\n❌ Thiếu GEMINI_API_KEY trong .env")
    sys.exit(1)

url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"
body = json.dumps({"contents": [{"parts": [{"text": "Say OK"}]}]}).encode()
req = urllib.request.Request(
    url,
    data=body,
    method="POST",
    headers={"Content-Type": "application/json", "x-goog-api-key": key},
)
print("\n1) REST API (x-goog-api-key)...")
try:
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"   ✅ OK — {text[:60]}")
except urllib.error.HTTPError as e:
    print(f"   ❌ HTTP {e.code}")
    err = json.loads(e.read().decode()) if e.fp else {}
    print(f"   Message: {err.get('error', {}).get('message', e.reason)[:200]}")
except Exception as e:
    print(f"   ❌ {e}")

print("\n2) google-genai SDK...")
try:
    from google import genai

    client = genai.Client(api_key=key)
    r = client.models.generate_content(model="gemini-2.0-flash-lite", contents="Say OK")
    print(f"   ✅ OK — {(r.text or '')[:60]}")
except ImportError:
    print("   ⚠️  Chưa cài: pip install google-genai")
except Exception as e:
    print(f"   ❌ {type(e).__name__}: {str(e)[:200]}")

print("\n=== Kết luận ===")
print("Nếu cả 2 đều 401 → key bị Google từ chối (không phải lỗi code lab).")
print("Làm trên https://aistudio.google.com/apikey :")
print("  • Bấm 'Restrict to Gemini API only' trên key")
print("  • Hoặc xóa key → tạo key mới → cập nhật .env")
print("Hoặc dùng local: DEFAULT_PROVIDER=local (xem README)")
