from google import genai
from google.genai import types
from food_assistant.config import get_gemini_key, GEMINI_TEXT_MODEL

client = genai.Client(api_key=get_gemini_key(),
                      http_options=types.HttpOptions(api_version="v1beta"))
r = client.models.generate_content(model=GEMINI_TEXT_MODEL,
                                   contents="Reply with exactly: setup ok")
print(r.text)
