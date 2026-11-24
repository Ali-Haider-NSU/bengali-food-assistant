import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_TRANSCRIBE_MODEL = "gemini-3.5-transcribe"
GEMINI_TEXT_MODEL = "gemini-3.5-flash-lite"


def get_gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            from google.colab import userdata
            key = userdata.get("GEMINI_API_KEY")
        except Exception:
            pass
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set: use .env locally or Colab Secrets.")
    return key

# Tried in this order; a busy (503/429) or unavailable (404) model is skipped
GEMINI_TEXT_FALLBACKS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]
