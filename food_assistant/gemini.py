"""Shared Gemini client with retries and model fallbacks."""
import time
from google import genai
from google.genai import types
from food_assistant.config import (get_gemini_key, GEMINI_TEXT_FALLBACKS,
                                   GEMINI_TRANSCRIBE_MODEL)

TEMPORARY = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
_client = None


def client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_gemini_key(),
                               http_options=types.HttpOptions(api_version="v1beta"))
    return _client


def generate(contents, config=None, models=None, attempts=2):
    """Try each model in turn; retry busy models. Returns (response, model_name)."""
    errors = []
    for model in models or GEMINI_TEXT_FALLBACKS:
        for attempt in range(attempts):
            try:
                r = client().models.generate_content(model=model, contents=contents, config=config)
                return r, model
            except Exception as e:
                msg = str(e)
                if any(k in msg for k in TEMPORARY) and attempt < attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                errors.append(f"{model}: {msg[:120]}")
                break
    raise RuntimeError("All Gemini models failed:\n" + "\n".join(errors))


def extract_text(r):
    """The transcribe model may put its text outside r.text, so search the response."""
    if getattr(r, "text", None):
        return r.text
    found = []
    def walk(x, key=""):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and x.strip() and key in ("text", "transcript", "transcription"):
            found.append(x.strip())
    walk(r.model_dump(exclude_none=True))
    return " ".join(dict.fromkeys(found))


def transcribe(audio_path):
    """Speech file -> text with Gemini Transcribe."""
    f = client().files.upload(file=audio_path)
    try:
        r, _ = generate([f], models=[GEMINI_TRANSCRIBE_MODEL], attempts=3)
        return extract_text(r).strip()
    finally:
        try:
            client().files.delete(name=f.name)
        except Exception:
            pass
