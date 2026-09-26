# -*- coding: utf-8 -*-
"""
Deterministic understanding for English, Indian English, Kannada, Hindi and
romanised mixes (Hinglish / Kanglish / Tanglish).

Output is a plain dict of *candidate* facts. The orchestrator decides what they
mean in context (which slot a bare answer fills, whether a date is a
correction, etc.). Nothing here is hard-coded to example sentences: it works
from vocabularies + grammatical markers (from/to, se/tak, -inda/-ge, ನಿಂದ/ಗೆ).
"""

from __future__ import annotations

import re
from datetime import date

import dates as D
import locations as L

# ---------------------------------------------------------------- vocab
FLIGHT_WORDS = r"flights?|fly|flying|plane|airfare|air\s*ticket|air\s*tickets|airline|one[\s-]?way|round[\s-]?trip|multi[\s-]?city|ವಿಮಾನ|ಫ್ಲೈಟ್|फ्लाइट|उड़ान|उडान|हवाई|जहाज"
HOTEL_WORDS = r"hotels?|stay|staying|rooms?|accommodation|resort|homestay|lodge|ಹೋಟೆಲ್|ರೂಮ್|ವಸತಿ|होटल|कमरा|ठहरने|रुकने"
PLAN_WORDS = (r"plan\s+(?:a|an|my|our|the)?\s*(?:[\w-]+\s+){0,4}?(?:trip|holiday|vacation|itinerary|getaway|tour)|itinerary|trip\s+plan|holiday\s+plan|"
              r"vacation|sightseeing|things\s+to\s+do|day[\s-]?by[\s-]?day|ಪ್ರವಾಸ|ಟ್ರಿಪ್\s*ಪ್ಲಾನ್|ಯೋಜನೆ|यात्रा\s*योजना|ट्रिप\s*प्लान|घूमने|घूमना|यात्रा\s*की\s*योजना")
INFO_WORDS = (r"baggage|luggage|bags?\b|visa|passport|insurance|web\s*check[\s-]?in|online\s*check[\s-]?in|boarding\s*pass|"
              r"refund|reschedul|cancel\s+(?:my|the)\s+(?:flight|booking|ticket|reservation)|wheelchair|documents?|"
              r"how\s+early|reach\s+the\s+airport|power\s*bank|name\s+(?:on|mismatch|different)|ಬ್ಯಾಗೇಜ್|ಲಗೇಜ್|ಸಾಮಾನು|ವೀಸಾ|ಪಾಸ್‌?ಪೋರ್ಟ್|ಚೆಕ್[- ]?ಇನ್|ವಿಮೆ|ಮರುಪಾವತಿ|ರೀಫಂಡ್|ಗಾಲಿಕುರ್ಚಿ|"
              r"सामान|बैगेज|लगेज|वीज़ा|वीजा|पासपोर्ट|चेक[- ]?इन|बीमा|रिफ़?ंड|व्हीलचेयर|saamaan|samaan|saamanu")

CABINS = [
    ("premium economy", "Premium Economy"), ("premium", "Premium Economy"), ("प्रीमियम इकॉनमी", "Premium Economy"),
    ("ಪ್ರೀಮಿಯಂ ಎಕಾನಮಿ", "Premium Economy"),
    ("business", "Business"), ("biz class", "Business"), ("ಬಿಸಿನೆಸ್", "Business"), ("ಬಿಸಿನೆಸ್ ಕ್ಲಾಸ್", "Business"),
    ("बिज़नेस", "Business"), ("बिजनेस", "Business"),
    ("first class", "First"), ("first-class", "First"), ("ಫಸ್ಟ್ ಕ್ಲಾಸ್", "First"), ("फर्स्ट क्लास", "First"),
    ("economy", "Economy"), ("eco class", "Economy"), ("coach", "Economy"), ("ಎಕಾನಮಿ", "Economy"),
    ("इकॉनमी", "Economy"), ("इकोनॉमी", "Economy"), ("इकोनोमी", "Economy"),
]

TRIP_TYPES = [
    (r"multi[\s-]?city|multi[\s-]?stop|multiple\s+cities|ಮಲ್ಟಿ\s*ಸಿಟಿ|मल्टी\s*सिटी", "multi_city"),
    (r"round[\s-]?trip|return\s+(?:trip|ticket|flight)|both\s+ways|two[\s-]?way|up\s*and\s*down|ರೌಂಡ್\s*ಟ್ರಿಪ್|ಹೋಗಿ\s*ಬರುವ|ಹೋಗಿ\s*ಬರ|राउंड\s*ट्रिप|आना[\s-]*जाना|आने[\s-]*जाने", "round_trip"),
    (r"one[\s-]?way|oneway|single\s+(?:trip|journey|ticket)|ಒನ್\s*-?\s*ವೇ|ಏಕಮುಖ|वन\s*-?\s*वे|एक\s*तरफ़ा|एक\s*तरफा", "one_way"),
]

NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "a": 1, "an": 1, "single": 1, "couple": 2, "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
}
_NUM = r"(\d{1,2}|" + "|".join(sorted((re.escape(k) for k in NUM_WORDS), key=len, reverse=True)) + r")"
KN_PEOPLE = {"ಒಬ್ಬರು": 1, "ಒಬ್ಬನೇ": 1, "ಒಬ್ಬಳೇ": 1, "ಇಬ್ಬರು": 2, "ಮೂವರು": 3, "ನಾಲ್ವರು": 4, "ಐವರು": 5}

INTERESTS = {
    "budget": r"budget|cheap|affordable|low[\s-]?cost|backpack|ಬಜೆಟ್|ಕಡಿಮೆ\s*ಖರ್ಚು|बजट|सस्ता",
    "luxury": r"luxury|luxurious|premium\s+stay|5[\s-]?star|five[\s-]?star|lavish|ಐಷಾರಾಮಿ|ಲಕ್ಷುರಿ|लक्ज़री|लक्जरी|आलीशान",
    "adventure": r"adventure|trek|trekking|hiking|rafting|scuba|diving|thrill|ಸಾಹಸ|ಅಡ್ವೆಂಚರ್|साहसिक|एडवेंचर",
    "family": r"family|kids?|children|child[\s-]?friendly|parents|ಕುಟುಂಬ|ಫ್ಯಾಮಿಲಿ|परिवार|फैमिली|बच्चों",
    "culture": r"culture|cultural|heritage|history|historic|temples?|museums?|art|ಸಂಸ್ಕೃತಿ|ಪರಂಪರೆ|संस्कृति|विरासत",
}

ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5, "last": -1, "ಮೊದಲ": 1, "ಎರಡನೇ": 2, "ಮೂರನೇ": 3, "पहला": 1, "पहली": 1,
    "दूसरा": 2, "दूसरी": 2, "तीसरा": 3, "तीसरी": 3,
}

YES = r"^(yes|yeah|yep|yup|sure|ok|okay|haan|ha|han|haa|ಹೌದು|ಸರಿ|हाँ|हां|ठीक)\b"
NO = r"^(no|nope|nah|nahi|nahin|illa|beda|ಇಲ್ಲ|ಬೇಡ|नहीं|ना)\b"


def _search(pattern: str, text: str) -> re.Match | None:
    return re.search(pattern, text, re.IGNORECASE)


# ---------------------------------------------------------------- roles
_ORIGIN_BEFORE = re.compile(r"(?:\bfrom|\bfrm|\bleaving|\bdeparting|\bdepart|\bex|\bout\s+of|\bstarting\s+(?:from|at))\s*$")
_DEST_BEFORE = re.compile(r"(?:\bto|\btill|\binto|\btowards|\breach(?:ing)?|\bvisit(?:ing)?|\barriving\s+(?:in|at)|\bgoing|\bdestination\s*(?:is)?)\s*$")
_HOTEL_BEFORE = re.compile(r"(?:\bin|\bat|\bnear|\baround)\s*$")
_ORIGIN_AFTER = re.compile(r"^(?:\s*(?:se|से|inda|ninda|irundhu|la\s+irundhu|nundi|ninnu|ninda)\b|\s*से|ಿನಿಂದ|ನಿಂದ|ಇಂದ|ಯಿಂದ|ದಿಂದ|ರಿಂದ|ಿಂದ|ು?\s*ಇಂದ|\s*(?:to|-|–|→|>)\s)")
_DEST_AFTER = re.compile(r"^(?:\s*(?:tak|तक|ko|को|ke\s+liye|के\s+लिए|ge|ku|ki|ilekku|jaana|jana|जाना|poganum|hogbeku|vellali)\b|\s*(?:तक|को|के\s+लिए|जाना|जा)|ಿಗೆ|ಗೆ|ಕ್ಕೆ|ಕೆ|ು?\s*ಗೆ)")


def place_role(low: str, p: L.Place) -> str | None:
    before = low[max(0, p.start - 24):p.start]
    after = low[p.end:p.end + 16]
    if _ORIGIN_AFTER.match(after) and not _DEST_BEFORE.search(before):
        return "origin"
    if _ORIGIN_BEFORE.search(before):
        return "origin"
    if _DEST_BEFORE.search(before):
        return "destination"
    if _DEST_AFTER.match(after):
        return "destination"
    if _HOTEL_BEFORE.search(before):
        return "at"
    return None


_RETURN_CUE = re.compile(r"(return|returning|back|coming\s+back|come\s+back|fly\s+back|वापसी|वापस|ಹಿಂತಿರುಗ|ವಾಪಸ್|until|till)\s*(?:(?:flight|date|day)\s*)?(?:on|by|date|to|as|for|is)?\s*[:\-]?\s*$")
_DEPART_CUE = re.compile(r"(depart\w*|going|go|fly\w*|outbound|onward|start\w*|जाना|ಹೊರಡ\w*)\s*(?:(?:flight|date|day)\s*)?(?:on|by|date|to|as|for|is)?\s*[:\-]?\s*$")
_LEAVE_CUE = re.compile(r"leav\w*\s*(?:on|by)?\s*[:\-]?\s*$")
_CHECKIN_CUE = re.compile(r"check[\s-]?in\s*(?:on|date)?\s*[:\-]?\s*$|arriv\w*\s*(?:on)?\s*$")
_CHECKOUT_CUE = re.compile(r"check[\s-]?out\s*(?:on|date)?\s*[:\-]?\s*$")


def date_role(low: str, h: D.DateHit) -> str | None:
    before = low[max(0, h.start - 30):h.start]
    if _CHECKOUT_CUE.search(before):
        return "checkout"
    if _CHECKIN_CUE.search(before):
        return "checkin"
    if _RETURN_CUE.search(before):
        return "return"
    if _DEPART_CUE.search(before):
        return "depart"
    if _LEAVE_CUE.search(before):
        return "leave"   # depart (flight) or check-out (hotel): decided by context
    return None


# ---------------------------------------------------------------- passengers
def parse_pax(text: str) -> dict:
    """Return {'adults','children','infants','family','total'} (None where not said)."""
    low = D.normalize_digits(text).lower()
    out = {"adults": None, "children": None, "infants": None, "family": None, "total": None}

    def num(s: str) -> int:
        s = s.strip().lower()
        return int(s) if s.isdigit() else NUM_WORDS.get(s, 0)

    m = re.search(rf"{_NUM}\s*(?:adults?|grown[\s-]?ups?|ವಯಸ್ಕರು|ವಯಸ್ಕ|वयस्क|बड़े)", low)
    if m:
        out["adults"] = num(m.group(1))
    m = re.search(rf"{_NUM}\s*(?:children|childs?|kids?|ಮಕ್ಕಳು|ಮಗು|बच्चे|बच्चा|बच्चों)", low)
    if m:
        out["children"] = num(m.group(1))
    elif re.search(r"\b(?:a|one|with\s+(?:a|my|our))\s+(?:child|kid|son|daughter)\b", low):
        out["children"] = 1
    m = re.search(rf"{_NUM}\s*(?:infants?|babies|baby|toddlers?|ಶಿಶು|शिशु)", low)
    if m:
        out["infants"] = num(m.group(1))
    elif re.search(r"\b(?:a|an|one|with\s+(?:a|an|my|our))\s+(?:infant|baby)\b", low):
        out["infants"] = 1

    colloquial = _colloquial_adults(low)
    if any(out[k] is not None for k in ("adults", "children", "infants")):
        if out["adults"] is None and colloquial:
            out["adults"] = colloquial
        return out
    if colloquial:
        out["adults"] = colloquial
        return out

    m = re.search(rf"family\s+of\s+{_NUM}", low)
    if m:
        out["family"] = num(m.group(1))
        return out
    m = re.search(rf"{_NUM}\s*(?:passengers?|people|persons?|pax|travell?ers?|adults?|ಜನ|ಪ್ರಯಾಣಿಕರು|लोग|यात्री|log)\b", low) \
        or re.search(rf"{_NUM}\s*(?:ಜನ|ಪ್ರಯಾಣಿಕರು|लोग|यात्री)", low)
    if m:
        out["adults"] = num(m.group(1))
        return out
    m = re.search(rf"\bfor\s+{_NUM}\b(?!\s*(?:nights?|days?|weeks?|hours?|am|pm|rooms?|stars?))", low)
    if m and not re.search(rf"\bfor\s+{_NUM}\s*(?:st|nd|rd|th)?\s+(?:{'|'.join(D.MONTHS)})", low):
        out["adults"] = num(m.group(1))
    return out


def _colloquial_adults(low: str) -> int | None:
    m = re.search(rf"\b{_NUM}\s+of\s+us\b", low)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else NUM_WORDS.get(v)
    if re.search(r"\b(?:me\s+and\s+my\s+(?:wife|husband|partner|friend|spouse|mom|dad|mother|father)|my\s+(?:wife|husband|partner)\s+and\s+(?:me|i)|a\s+couple|us\s+two|both\s+of\s+us)\b", low):
        return 2
    if re.search(r"(?:\bjust\s+me\b|\bonly\s+me\b|\bmyself\b|\bsolo\b|\balone\b|\bby\s+myself\b|ಒಬ್ಬನೇ|ಒಬ್ಬಳೇ|अकेले|अकेला)", low):
        return 1
    for word, n in KN_PEOPLE.items():
        if word in low:
            return n
    return None


def parse_rooms(text: str) -> int | None:
    m = re.search(rf"{_NUM}\s*(?:rooms?|ರೂಮ್|कमरे|कमरा)", D.normalize_digits(text).lower())
    if m:
        s = m.group(1)
        return int(s) if s.isdigit() else NUM_WORDS.get(s)
    return None


def parse_cabin(text: str) -> str | None:
    low = text.lower()
    for key, val in CABINS:
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", low):
            if key == "first class" or key != "first":
                return val
    return None


def parse_trip_type(text: str) -> str | None:
    low = text.lower()
    if "one day" in low:
        return None
    for pat, val in TRIP_TYPES:
        if re.search(pat, low):
            return val
    return None


def parse_budget_amount(text: str) -> int | None:
    low = D.normalize_digits(text).lower().replace(",", "")
    m = re.search(r"(?:₹|rs\.?|inr|budget\s+(?:of|is)?|under|within|below|max(?:imum)?)\s*(\d+(?:\.\d+)?)\s*(k|lakh|lakhs|l|thousand)?", low)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(k|lakh|lakhs|thousand)\b", low)
        if not m:
            return None
    n = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("k", "thousand"):
        n *= 1000
    elif unit in ("lakh", "lakhs", "l"):
        n *= 100000
    return int(n) if n >= 1000 else None


def parse_interests(text: str) -> list[str]:
    low = text.lower()
    return [k for k, pat in INTERESTS.items() if re.search(pat, low)]


def parse_ordinal(text: str) -> int | None:
    low = text.lower()
    for w, n in ORDINALS.items():
        if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
            return n
    m = re.search(r"\b(?:option|number|no\.?|#)\s*(\d)\b", low)
    if m:
        return int(m.group(1))
    return None


def parse_flight_no(text: str, known: list[str]) -> str | None:
    up = text.upper().replace(" ", "")
    for fn in known:
        if fn.replace(" ", "").upper() in up:
            return fn
    return None


# ---------------------------------------------------------------- main
def extract(text: str, today: date) -> dict:
    raw = text or ""
    norm = D.normalize_digits(raw)
    low = norm.lower()

    places = L.find_places(norm)
    for p in places:
        p.extra["role"] = place_role(low, p)
    # "Bengaluru Delhi" / "BLR-DEL": two unlabelled places -> origin, destination
    unl = [p for p in places if not p.extra["role"]]
    if len(places) == 2 and len(unl) == 2:
        places[0].extra["role"], places[1].extra["role"] = "origin", "destination"
    elif len(places) == 2 and len(unl) == 1:
        other = "destination" if [p for p in places if p.extra["role"]][0].extra["role"] == "origin" else "origin"
        unl[0].extra["role"] = other if other in ("origin", "destination") else None

    hits = D.find_dates(norm, today)
    for h in hits:
        h_role = date_role(low, h)
        setattr(h, "role", h_role)

    pax = parse_pax(norm)
    out = {
        "text": raw,
        "low": low,
        "places": places,
        "dates": hits,
        "pax": pax,
        "rooms": parse_rooms(norm),
        "cabin": parse_cabin(norm),
        "trip_type": parse_trip_type(norm),
        "duration": D.find_duration(norm),
        "interests": parse_interests(norm),
        "budget_amount": parse_budget_amount(norm),
        "ordinal": parse_ordinal(norm),
        "yes": bool(re.search(YES, low.strip())),
        "no": bool(re.search(NO, low.strip())),
        "domain_flight": bool(_search(FLIGHT_WORDS, low)),
        "domain_hotel": bool(_search(HOTEL_WORDS, low)),
        "domain_plan": bool(_search(PLAN_WORDS, low)),
        "info": bool(_search(INFO_WORDS, low)),
        "correction": bool(re.search(r"\b(actually|instead|change|make\s+it|not\s+\w+\s*,?\s*(?:but|it'?s)|sorry|correction|update|switch)\b|ಬದಲಾಯಿಸಿ|ಬದಲಿಗೆ|बदल|की\s+जगह", low)),
        "cmd_checkout": bool(re.search(r"\b(demo\s+checkout|proceed\s+to\s+(?:demo\s+)?checkout|go\s+to\s+checkout|checkout\s+now|^checkout$|pay\s+now|book\s+(?:it|this|now)|confirm\s+(?:it|booking))\b|ಚೆಕ್‌?ಔಟ್|चेकआउट", low)) and not hits,
        "cmd_review": bool(re.search(r"\b(review|summary|total|how\s+much|trip\s+summary|show\s+(?:my\s+)?selection)\b|ಸಾರಾಂಶ|ಒಟ್ಟು|सारांश|कुल", low)),
        "cmd_simulate": bool(re.search(r"\b(simulat\w*|delay\w*|flight\s+status|status\s+update|on\s+time|flight\s+alert|flight\s+update)\b|ವಿಳಂಬ|ಅಪ್ಡೇಟ್|देरी|अपडेट", low)),
        "cmd_select": bool(re.search(r"\b(select|choose|pick|take|go\s+with|book|want|prefer)\b|ಆಯ್ಕೆ|चुन", low)),
        "cmd_remove": bool(re.search(r"\b(remove|delete|drop|cancel|skip)\b.*\b(flight|leg|segment|trip)\b|ತೆಗೆ|हटा", low)),
        "cmd_add_leg": bool(re.search(r"\b(add|another|one\s+more|next)\b.*\b(flight|leg|segment|city)\b|ಇನ್ನೊಂದು|ಸೇರಿಸಿ|और\s+जोड़", low)),
        "cmd_search": bool(re.search(r"\b(search|find|show)\b.*\b(flights?|these|them|options)\b|^search$|^done$|that'?s\s+all|no\s+more|ಹುಡುಕಿ|खोजें|खोजो", low)),
        "cmd_add_hotel": bool(re.search(r"\b(add|need|want|also|book)\b.*\b(hotel|stay|room)\b|hotel\s+too|ಹೋಟೆಲ್\s*ಸೇರಿಸಿ|होटल\s*भी", low)),
        "cmd_seats": bool(re.search(r"\b(seats?|seat\s+map|window\s+seat|aisle\s+seat)\b|ಸೀಟ್|सीट", low)),
        "cmd_plan": bool(_search(PLAN_WORDS, low)),
        "cmd_no_pref": bool(re.search(r"\b(no\s+preference|any|anything|doesn'?t\s+matter|no\s+prefs?|skip|none)\b|ಯಾವುದಾದರೂ|कोई\s+भी|कुछ\s+नहीं", low)),
    }
    return out


def has_booking_entities(u: dict) -> bool:
    p = u["pax"]
    return bool(u["places"] or u["dates"] or u["cabin"] or u["trip_type"]
                or any(p[k] is not None for k in ("adults", "children", "infants", "family")))
