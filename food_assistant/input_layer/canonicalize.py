"""Step 6: normalise any Bengali / Banglish / English request into standard Bengali."""
from typing import Optional
from pydantic import BaseModel
from google.genai import types
from food_assistant.gemini import generate

INTENTS = {"identify", "get_recipe", "show_image", "show_video", "ingredients",
           "substitute", "scale_servings", "cooking_help", "ingredient_info", "other"}


class CanonicalQuery(BaseModel):
    standard_bn: str              # the VLM's input: faithful, standard Bengali
    intent: str                   # routing
    dish: Optional[str] = None    # routing: romanised dish id, e.g. "shorshe ilish"
    ingredient: Optional[str] = None
    servings: Optional[int] = None
    reply_lang: str               # language the user wrote in


SYSTEM_PROMPT = """You are the input normaliser of a Bengali cooking assistant.
The user writes or speaks in Bengali, Banglish (Bengali in Latin letters) or English,
often with spelling mistakes. Rewrite the request as standard Bengali and extract its fields.
NEVER answer the question.

Rules for standard_bn:
- Faithful: keep the user's full meaning and wording, including politeness words,
  numbers, ingredients and negations. Do not shorten or summarise.
- Standard spoken Bengali (চলিত ভাষা), correct spelling, Bengali script only.
- Banglish -> Bengali script. English -> natural Bengali translation.
- Dish names in their standard Bengali spelling (সরষে ইলিশ, চিংড়ি মালাইকারি, কষা মাংস, মিষ্টি দই).
- Numbers in Bengali digits (৬).
- A reference to a photo ("this", "eta") becomes "এটা" / "এই খাবারটা".

Rules for the other fields:
- intent is exactly one of: identify, get_recipe, show_image, show_video, ingredients,
  substitute, scale_servings, cooking_help, ingredient_info, other.
- dish: romanised lowercase dish id (shorshe ilish, kosha mangsho), or null.
- ingredient: English lowercase name (cumin, coconut milk), or null.
- reply_lang: "en" if the user wrote in English, otherwise "bn".
- Not about food or cooking: intent "other".

Examples:
"Amake shorshe ilisher recipe dao."
-> {"standard_bn": "আমাকে সরষে ইলিশের রেসিপি দাও।", "intent": "get_recipe", "dish": "shorshe ilish", "ingredient": null, "servings": null, "reply_lang": "bn"}
"eta ki khabar?"
-> {"standard_bn": "এটা কী খাবার?", "intent": "identify", "dish": null, "ingredient": null, "servings": null, "reply_lang": "bn"}
"6 joner jonno kosha mangsho te koto mangsho lagbe"
-> {"standard_bn": "৬ জনের জন্য কষা মাংসে কতটা মাংস লাগবে?", "intent": "scale_servings", "dish": "kosha mangsho", "ingredient": "meat", "servings": 6, "reply_lang": "bn"}
"Can I use yogurt instead of cream in chingri malai curry?"
-> {"standard_bn": "চিংড়ি মালাইকারিতে ক্রিমের বদলে কি দই ব্যবহার করা যায়?", "intent": "substitute", "dish": "chingri malai curry", "ingredient": "cream", "servings": null, "reply_lang": "en"}
"জিরা দেখতে কেমন?"
-> {"standard_bn": "জিরা দেখতে কেমন?", "intent": "ingredient_info", "dish": null, "ingredient": "cumin", "servings": null, "reply_lang": "bn"}
"""

_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    response_mime_type="application/json",
    response_schema=CanonicalQuery,
    temperature=0,
)


def canonicalize(text: str) -> tuple[CanonicalQuery, str]:
    """Returns (normalised query, model used)."""
    r, model = generate(text, config=_CONFIG)
    q = r.parsed if isinstance(r.parsed, CanonicalQuery) else CanonicalQuery.model_validate_json(r.text)
    if q.intent not in INTENTS:
        q.intent = "other"
    if q.reply_lang not in ("bn", "en"):
        q.reply_lang = "bn"
    return q, model
