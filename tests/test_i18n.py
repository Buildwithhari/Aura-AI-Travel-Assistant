import re

import i18n

KANNADA = re.compile(r"[\u0C80-\u0CFF]")
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
PURE_PLACEHOLDER = re.compile(r"^[\s{}\w:.,()+·→-]*$")


def test_every_key_has_all_languages_with_same_placeholders():
    for table in (i18n.M, i18n.UI):
        for key, entry in table.items():
            en = i18n.placeholders(entry["en"])
            for lang in ("kn", "hi"):
                assert lang in entry, (key, lang)
                assert i18n.placeholders(entry[lang]) == en, (key, lang)


def test_translations_are_in_the_right_script():
    """Kannada/Hindi entries must actually be Kannada/Hindi (not English left behind)."""
    for table in (i18n.M, i18n.UI):
        for key, entry in table.items():
            for lang, script in (("kn", KANNADA), ("hi", DEVANAGARI)):
                val = entry[lang]
                val = " ".join(val) if isinstance(val, tuple) else val
                text = re.sub(r"\{\w+\}", "", val)
                if not re.search(r"[A-Za-z\u0C80-\u0CFF\u0900-\u097F]", text):
                    continue   # only placeholders / symbols, e.g. "{cabin}"
                assert script.search(text), (key, lang, val)


def test_plurals_and_formatting():
    assert i18n.t("n_adults", "en", n=1) == "1 adult"
    assert i18n.t("n_adults", "en", n=2) == "2 adults"
    assert i18n.t("n_children", "kn", n=1) == "1 ಮಗು"
    assert i18n.t("n_children", "kn", n=2) == "2 ಮಕ್ಕಳು"
    assert i18n.t("missing_key_xyz", "kn") == "missing_key_xyz"


def test_script_detection():
    assert i18n.detect_script_language("ನಾಳೆ ದೆಹಲಿಗೆ") == "kn"
    assert i18n.detect_script_language("दिल्ली से गोवा") == "hi"
    assert i18n.detect_script_language("flight to delhi tomorrow") == "en"
    assert i18n.detect_script_language("ok") is None
