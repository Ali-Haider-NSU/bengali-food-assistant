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
