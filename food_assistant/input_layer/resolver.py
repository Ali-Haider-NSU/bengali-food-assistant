"""Map any spelling of a dish or ingredient name to a class id from data/labels.json.

Handles Bengali script, Banglish, English, typos and speech-recognition errors by comparing
everything in one coarse phonetic key (Latin letters). Also powers autosuggest while typing.

    r = Resolver()
    r.resolve("rosmalai er chobi dekhao")   # -> Match(id="roshmalai", zone="accept", ...)
    r.suggest("roshm")                      # -> [{"id": "roshmalai", "name_bn": "রসমালাই", ...}]
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

try:
    from rapidfuzz import fuzz

    def _ratio(a: str, b: str) -> float:
        return fuzz.ratio(a, b)
except ImportError:                                   # fallback so it runs anywhere
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return 100 * SequenceMatcher(None, a, b).ratio()

DATA = Path(__file__).resolve().parents[2] / "data"

ACCEPT = 80      # score >= ACCEPT: use the match
ASK = 68         # ASK <= score < ACCEPT: "Did you mean ...?"

# ---------------------------------------------------------------- phonetic key
# Bengali letters -> coarse Latin classes. Sounds that speakers and ASR confuse share a class:
# স শ ষ -> s, চ ছ -> c, ন ণ -> n, জ য -> j, ড় ঢ় র -> r, aspirated -> unaspirated.
_BN = {
    "ক": "k", "খ": "k", "গ": "g", "ঘ": "g", "ঙ": "ng", "চ": "c", "ছ": "c", "জ": "j", "ঝ": "j", "ঞ": "n",
    "ট": "t", "ঠ": "t", "ড": "d", "ঢ": "d", "ণ": "n", "ত": "t", "থ": "t", "দ": "d", "ধ": "d", "ন": "n",
    "প": "p", "ফ": "p", "ব": "b", "ভ": "b", "ম": "m", "য": "j", "র": "r", "ল": "l", "শ": "s", "ষ": "s",
    "স": "s", "হ": "h", "ড়": "r", "ঢ়": "r", "য়": "", "ৎ": "t", "ং": "ng", "ঃ": "", "ঁ": "",
    "অ": "o", "আ": "a", "ই": "i", "ঈ": "i", "উ": "u", "ঊ": "u", "ঋ": "ri", "এ": "e", "ঐ": "oi",
    "ও": "o", "ঔ": "ou",
    "া": "a", "ি": "i", "ী": "i", "ু": "u", "ূ": "u", "ৃ": "ri", "ে": "e", "ৈ": "oi", "ো": "o", "ৌ": "ou",
    "্": "", "়": "",
}
# Banglish / English spelling rules, applied in order
_LATIN = [("chh", "c"), ("ch", "c"), ("sh", "s"), ("ss", "s"), ("ph", "p"), ("bh", "b"), ("kh", "k"),
          ("gh", "g"), ("th", "t"), ("dh", "d"), ("jh", "j"), ("rh", "r"), ("w", "o"), ("oo", "u"),
          ("ee", "i"), ("y", "i"), ("z", "j"), ("q", "k"), ("x", "ks"), ("f", "p"), ("v", "b")]
_VOWELS = set("aeiou")


def _devanagari_to_bengali(ch: str) -> str:
    # ASR sometimes writes Bengali speech in Hindi script; the Unicode blocks are parallel
    cp = ord(ch)
    return chr(cp + 0x80) if 0x0900 <= cp <= 0x097F else ch


def phonetic_key(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    text = unicodedata.normalize("NFC", "".join(_devanagari_to_bengali(c) for c in text))
    out = []
    for c in text:
        if c in _BN:
            out.append(_BN[c])
        elif c.isascii() and c.isalpha():
            out.append(c)
        elif c.isspace() or c in "-_/":
            out.append(" ")
        # digits, punctuation, danda and other symbols are dropped
    s = "".join(out)
    for a, b in _LATIN:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)                 # golla -> gola
    return " ".join(s.split())


def _skeleton(key: str) -> str:
    # consonants only: Bengali script omits the inherent vowel (সরষে ~ "srse"), Banglish writes it
    return "".join(c for c in key if c not in _VOWELS and c != " ")


def similarity(a: str, b: str) -> float:
    a_c, b_c = a.replace(" ", ""), b.replace(" ", "")
    if min(len(a_c), len(b_c)) <= 3:                # very short names: exact match only
        return 100.0 if a_c == b_c else 0.0
    full = _ratio(a_c, b_c)
    sa, sb = _skeleton(a), _skeleton(b)
    if min(len(sa), len(sb)) < 3:                   # too few consonants for a reliable skeleton
        return full
    return 0.5 * full + 0.5 * _ratio(sa, sb)


def _strip_suffix(span: str) -> str:
    # Bengali possessive on the last word: ইলিশের -> "iliser" -> "ilis", রসগোল্লার -> "rsgolar" -> "rsgola"
    head, _, last = span.rpartition(" ")
    if len(last) > 4 and last.endswith("er"):
        last = last[:-2]
    elif len(last) > 5 and last.endswith("ar"):
        last = last[:-1]
    return f"{head} {last}".strip()


# Words that are never part of a name (request words in Bengali, Banglish, English)
_STOP_WORDS = """
দাও দেখাও রেসিপি আমাকে আমার এর কি কী কেমন ছবি ভিডিও কিভাবে কীভাবে বানাতে বানায় রান্না করে লাগে
একটু বলো তো এটা এই কোন উপকরণ দিয়ে জন্য
dao dekhao recipe amake amar er ki kemon chobi video kivabe kibhabe banate banay ranna kore lage
ektu bolo to eta ei kon upokoron diye jonno
give me the of for show picture photo image how to make cook please a an is this what recipes
it time do does can you i my with and or in on about tell want need
""".split()
STOP_KEYS = {phonetic_key(w) for w in _STOP_WORDS}


# ---------------------------------------------------------------- data classes
@dataclass
class Entry:
    task: str
    id: str
    alias: str
    key: str


@dataclass
class Match:
    task: str | None
    id: str | None
    score: float
    zone: str                                       # "accept" | "ask" | "none"
    name_bn: str = ""
    name_en: str = ""
    span: str = ""                                  # the words that matched
    candidates: list = field(default_factory=list)  # [(task, id, score)] best first


# ---------------------------------------------------------------- resolver
class Resolver:
    def __init__(self, labels_path: Path = DATA / "labels.json",
                 aliases_path: Path = DATA / "aliases.json"):
        self.labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
        extra = json.loads(Path(aliases_path).read_text(encoding="utf-8")) if Path(aliases_path).exists() else {}
        self.entries: list[Entry] = []
        for task, classes in self.labels.items():
            for cid, info in classes.items():
                names = {cid.replace("_", " ")}
                for field_name in ("name_en", "name_bn"):
                    for part in info.get(field_name, "").split("/"):
                        part = part.strip()
                        if part:
                            names.add(part)
                            names.add(re.sub(r"\(.*?\)", "", part).strip())   # "Bhat (rice)" -> "Bhat"
                            names.update(re.findall(r"\((.*?)\)", part))      # ... and "rice"
                names.update(extra.get(task, {}).get(cid, []))
                for alias in names:
                    key = phonetic_key(alias)
                    if key:
                        self.entries.append(Entry(task, cid, alias, key))

    def info(self, task: str, cid: str) -> dict:
        return self.labels.get(task, {}).get(cid, {})

    # -- full sentence -> one class id
    def resolve(self, text: str, tasks: set[str] | None = None, max_words: int = 4) -> Match:
        words = [w for w in phonetic_key(text).split() if w not in STOP_KEYS]
        best: dict[tuple[str, str], tuple[float, int, str]] = {}      # (task,id) -> (score, span_len, span)
        for n in range(1, max_words + 1):
            for i in range(len(words) - n + 1):
                span = " ".join(words[i:i + n])
                for e in self.entries:
                    if tasks and e.task not in tasks:
                        continue
                    if not 0.5 <= len(span) / len(e.key) <= 1.8:       # skip windows far off in length
                        continue
                    s = max(similarity(span, e.key), similarity(_strip_suffix(span), e.key))
                    cur = best.get((e.task, e.id))
                    if cur is None or (s, len(span)) > (cur[0], cur[1]):
                        best[(e.task, e.id)] = (s, len(span), span)

        # rank by score, then prefer the longer match ("jira gura" beats "jira")
        ranked = sorted(best.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)
        cands = [(t, i, round(v[0], 1)) for (t, i), v in ranked[:3]]
        if not ranked or ranked[0][1][0] < ASK:
            return Match(None, None, round(ranked[0][1][0], 1) if ranked else 0.0, "none", candidates=cands)
        (task, cid), (score, _, span) = ranked[0]
        info = self.info(task, cid)
        return Match(task, cid, round(score, 1), "accept" if score >= ACCEPT else "ask",
                     info.get("name_bn", ""), info.get("name_en", ""), span, cands)

    # -- partial input -> suggestions while typing
    def suggest(self, text: str, k: int = 5, tasks: set[str] | None = None, min_score: float = 60) -> list[dict]:
        typed = phonetic_key(text).replace(" ", "")
        if len(typed) < 2:
            return []
        scores: dict[tuple[str, str], float] = {}
        for e in self.entries:
            if tasks and e.task not in tasks:
                continue
            alias = e.key.replace(" ", "")
            if alias.startswith(typed):
                s = 100.0
            elif len(typed) >= 4:                     # typo in the part typed so far
                s = max(_ratio(typed, alias[:len(typed)]), _ratio(typed, alias))
            else:
                continue
            if s > scores.get((e.task, e.id), 0):
                scores[(e.task, e.id)] = s
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [dict(task=t, id=i, score=round(s, 1), **{f: self.info(t, i).get(f, "") for f in ("name_bn", "name_en")})
                for (t, i), s in top if s >= min_score]
