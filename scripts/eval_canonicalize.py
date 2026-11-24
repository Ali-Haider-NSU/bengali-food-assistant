"""Do Bengali, Banglish and English phrasings of one request give the same intent and dish?"""
import time
from food_assistant.input_layer.canonicalize import canonicalize

GROUPS = [
    ["সরষে ইলিশের রেসিপি দাও", "shorshe ilish er recipe dao", "Give me the recipe for shorshe ilish"],
    ["কষা মাংসের ভিডিও দেখাও", "kosha mangsho er video dekhao", "Show me a video of kosha mangsho"],
    ["মিষ্টি দই বানাতে কি কি লাগে?", "mishti doi banate ki ki lage", "What ingredients do I need for mishti doi?"],
    ["এটা কী খাবার?", "eta ki khabar?", "What dish is this?"],
    ["চিংড়ি মালাইকারিতে নারকেলের দুধের বদলে কী দেওয়া যায়?",
     "chingri malaikari te narkel dudh er bodole ki dewa jay",
     "What can I use instead of coconut milk in chingri malai curry?"],
    ["৬ জনের জন্য কষা মাংসে কতটা মাংস লাগবে?", "6 joner jonno kosha mangsho te koto mangsho lagbe",
     "How much meat do I need for kosha mangsho for 6 people?"],
    ["আজকে আবহাওয়া কেমন?", "ajke weather kemon", "How is the weather today?"],
]

consistent = 0
for group in GROUPS:
    results = []
    for text in group:
        q, model = canonicalize(text)
        results.append(q)
        print(f"{q.intent:15s} {str(q.dish):22s} {q.reply_lang}  | {text}")
        print(f"{'':41s}-> {q.standard_bn}")
        time.sleep(1)                       # stay gentle with free-tier rate limits
    same = len({(q.intent, q.dish) for q in results}) == 1
    consistent += same
    print("  ✓ consistent\n" if same else "  ✗ INCONSISTENT\n")

print(f"Consistent groups: {consistent}/{len(GROUPS)}")
