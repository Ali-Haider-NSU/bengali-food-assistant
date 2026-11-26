"""Resolver tests: real-world spellings must land on the right class, unrelated text on nothing."""
import pytest
from food_assistant.input_layer.resolver import Resolver, phonetic_key, _skeleton


@pytest.fixture(scope="module")
def r():
    return Resolver()


@pytest.mark.parametrize("text, expected", [
    # Bengali script, with request words around the name
    ("সর্ষে ইলিশের রেসিপি দাও", "shorshe_ilish"),
    ("রসমালাইয়ের ছবি দেখাও", "roshmalai"),
    ("খিচুড়ি কিভাবে রান্না করে", "khichuri"),
    ("আলু ভর্তা", "alu_bhorta"),
    # Banglish, including misspellings
    ("shorshe ilish er recipe dao", "shorshe_ilish"),
    ("rosmalai er chobi dekhao", "roshmalai"),
    ("rasgulla", "roshgolla"),
    ("paratha", "porota"),
    ("khichdi", "khichuri"),
    ("halim recipe", "haleem"),
    # English names
    ("show me egg curry", "dim_curry"),
    ("mashed potato", "alu_bhorta"),
    ("gulab jamun", "kalojam"),
    # ASR-style errors from earlier tests
    ("কসামাংস", None),            # kosha mangsho is not in the dataset: must not be forced onto a class
    ("রাশগুল্লাহ", "roshgolla"),
    ("Rosh Gulla", "roshgolla"),
    # ingredients
    ("জিরা দেখতে কেমন", "cumin"),
    ("জিরা গুঁড়া", "cumin_powder"),
    ("kalojira", "nigella_seed"),
    ("tejpata", "bay_leaf"),
    # out-of-domain classes are recognised as such
    ("pizza", "pizza"),
    # nothing food-related
    ("আজকে আবহাওয়া কেমন", None),
    ("রেসিপি দাও", None),
])
def test_resolve(r, text, expected):
    m = r.resolve(text)
    got = m.id if m.zone == "accept" else None
    assert got == expected, f"{text!r}: got {m.id} ({m.zone}, {m.score}), candidates {m.candidates}"


def test_ood_task(r):
    assert r.resolve("burger").task == "ood"


def test_suggest_prefix(r):
    ids = [s["id"] for s in r.suggest("rosh")]
    assert "roshmalai" in ids and "roshgolla" in ids


def test_suggest_bengali(r):
    assert r.suggest("রসমা")[0]["id"] == "roshmalai"


def test_suggest_typo(r):
    assert r.suggest("khicuri")[0]["id"] == "khichuri"


def test_phonetic_key_merges_scripts():
    assert _skeleton(phonetic_key("সরষে")) == _skeleton(phonetic_key("shorshe"))
    assert _skeleton(phonetic_key("রসমালাই")) == _skeleton(phonetic_key("roshmalai"))


@pytest.mark.parametrize("text", ["আজকে আবহাওয়া কেমন", "রেসিপি দাও", "what time is it"])
def test_unrelated_is_none(r, text):
    assert r.resolve(text).zone == "none"
