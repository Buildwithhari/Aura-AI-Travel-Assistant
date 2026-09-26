"""Kannada / Hindi input in script and in English letters (no LLM)."""
import json
import os
import re

import i18n
from helpers import Chat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KN = re.compile(r"[\u0C80-\u0CFF]")
HI = re.compile(r"[\u0900-\u097F]")


def test_romanized_detection():
    assert i18n.detect_script_language("naale bengaluru inda delhi ge flight beku") == "kn"
    assert i18n.detect_script_language("nanage hotel beku goa alli") == "kn"
    assert i18n.detect_script_language("mujhe kal delhi jana hai") == "hi"
    for english in ["flight from delhi to goa tomorrow", "book a hotel in Goa", "Mysore to Delhi", "I need a flight"]:
        assert i18n.detect_script_language(english) == "en", english


def test_romanized_kannada_gets_kannada_replies_for_whole_flow():
    c = Chat()
    for msg in ["namaskara", "naale bengaluru inda delhi ge flight beku", "one way", "2 adults economy"]:
        p = c.say(msg)
        assert p["language"] == "kn" and KN.search(p["reply"]), (msg, p["reply"])
    assert c.block("flights")


def test_knowledge_questions_in_kannada_and_hindi():
    c = Chat()
    p = c.say("ಬ್ಯಾಗೇಜ್ ಎಷ್ಟು ಕೆಜಿ ಅನುಮತಿ ಇದೆ?")
    assert p["rag_used"] and "15 kg" in p["reply"] and KN.search(p["reply"])
    p = Chat().say("ಪ್ರಯಾಣ ವಿಮೆ ಏನು ಕವರ್ ಮಾಡುತ್ತದೆ?")
    assert p["rag_used"] and "ವಿಮೆ" in p["reply"]
    p = Chat().say("सामान कितना ले जा सकते हैं?")
    assert p["rag_used"] and "15 kg" in p["reply"] and HI.search(p["reply"])


def test_english_questions_still_english():
    p = Chat().say("what is the baggage allowance?")
    assert p["language"] == "en" and "15 kg" in p["reply"] and not KN.search(p["reply"])


def test_every_knowledge_answer_is_translated_and_keeps_facts():
    docs = json.load(open(os.path.join(ROOT, "data", "travel_knowledge.json"), encoding="utf-8"))
    for d in docs:
        for lang, script in (("kn", KN), ("hi", HI)):
            text = d.get(f"content_{lang}")
            assert text and script.search(text), (d["id"], lang)
            for fact in re.findall(r"\b\d+\s?kg\b|\b[A-Z]{3,4}\b", d["content"]):
                assert fact in text, (d["id"], lang, fact)
