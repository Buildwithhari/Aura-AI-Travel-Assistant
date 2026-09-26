"""
Layer 1 - Fast NLP (deterministic, sub-second).

Responsibilities:
  1. Intent classification with TF-IDF -> Logistic Regression (primary) / Linear SVM (challenger).
     Model selection rule (matches the Tesseraflux spec): prefer LogReg for its calibrated
     probabilities (needed for threshold-based triage); only switch to SVM if it beats LogReg
     on macro-F1 by >= 0.03. If SVM wins, it is wrapped in CalibratedClassifierCV so we still
     get probabilities for the confidence gate.
  2. Custom NER via regex (origin, destination, date, passengers, cabin class).
     spaCy is used only if installed; the bot runs fine without it.

Nothing here touches the network. Trains in ~1s on import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

# Optional spaCy NER. If the model isn't present we silently fall back to regex only.
try:
    import spacy

    _NLP = spacy.load("en_core_web_sm")
except Exception:  # noqa: BLE001 - any failure means "no spaCy", which is fine.
    _NLP = None


# --------------------------------------------------------------------------- #
# Training data. Small on purpose: fast to train, easy to extend per intent.
# --------------------------------------------------------------------------- #
TRAINING_DATA: list[tuple[str, str]] = [
    # greeting
    ("hi", "greeting"),
    ("hello", "greeting"),
    ("hey there", "greeting"),
    ("good morning", "greeting"),
    ("namaste", "greeting"),
    ("hey, can you help me", "greeting"),
    ("how are you", "greeting"),
    ("how are you aura", "greeting"),
    ("are you there", "greeting"),
    ("who are you", "greeting"),
    ("good afternoon", "greeting"),
    ("good evening", "greeting"),
    # flight_search
    ("i need a flight", "flight_search"),
    ("book me a flight to delhi", "flight_search"),
    ("flight from mumbai to goa tomorrow", "flight_search"),
    ("i want to fly to bangalore next week", "flight_search"),
    ("search flights delhi to chennai for 2 people", "flight_search"),
    ("show me flights to hyderabad", "flight_search"),
    ("any flights from pune to delhi on friday", "flight_search"),
    ("business class flight to dubai", "flight_search"),
    ("i need to travel to kolkata by air", "flight_search"),
    ("get me a ticket to jaipur", "flight_search"),
    ("search a flight", "flight_search"),
    ("book a flight", "flight_search"),
    ("find a flight", "flight_search"),
    ("look for flights", "flight_search"),
    ("search flight", "flight_search"),
    ("book flight", "flight_search"),
    ("i want to book a flight", "flight_search"),
    ("can you search a flight for me", "flight_search"),
    ("flight search", "flight_search"),
    ("find me a flight", "flight_search"),
    ("book a flight from delhi to mumbai", "flight_search"),
    ("book a flight from delhi to mumbai tomorrow for 2 adults in business class", "flight_search"),
    # international flight search
    ("international flight", "flight_search"),
    ("book international flight", "flight_search"),
    ("i want to travel abroad", "flight_search"),
    ("i need an international trip", "flight_search"),
    ("flight to dubai", "flight_search"),
    ("bangalore to singapore", "flight_search"),
    ("delhi to london", "flight_search"),
    ("mumbai to bangkok", "flight_search"),
    ("flight from chennai to dubai", "flight_search"),
    # hotel_search
    ("i need a hotel", "hotel_search"),
    ("book a hotel in goa", "hotel_search"),
    ("find me a room in delhi for 2 nights", "hotel_search"),
    ("hotels in mumbai near the airport", "hotel_search"),
    ("i want to stay in bangalore this weekend", "hotel_search"),
    ("cheap accommodation in jaipur", "hotel_search"),
    ("show me hotels in chennai", "hotel_search"),
    # modify_booking
    ("i want to change my flight", "modify_booking"),
    ("can i reschedule my booking", "modify_booking"),
    ("change my travel date", "modify_booking"),
    ("modify my reservation", "modify_booking"),
    ("i need to update passenger details", "modify_booking"),
    ("postpone my trip to next week", "modify_booking"),
    # cancel_booking
    ("cancel my flight", "cancel_booking"),
    ("i want a refund for my ticket", "cancel_booking"),
    ("please cancel my hotel booking", "cancel_booking"),
    ("how do i cancel my reservation", "cancel_booking"),
    ("cancel booking and refund", "cancel_booking"),
    # baggage_info
    ("what is the baggage allowance", "baggage_info"),
    ("how many bags can i carry", "baggage_info"),
    ("checked baggage limit for domestic", "baggage_info"),
    ("can i carry 20kg luggage", "baggage_info"),
    ("cabin bag size rules", "baggage_info"),
    # web_checkin
    ("how do i do web check in", "web_checkin"),
    ("web checkin for my flight", "web_checkin"),
    ("i want to check in online", "web_checkin"),
    ("get my boarding pass", "web_checkin"),
    # insurance
    ("do you offer travel insurance", "insurance"),
    ("add insurance to my booking", "insurance"),
    ("what does travel insurance cover", "insurance"),
    ("i want trip protection", "insurance"),
    # human_handoff
    ("i want to talk to a human", "human_handoff"),
    ("connect me to an agent", "human_handoff"),
    ("this is not working, get me support", "human_handoff"),
    ("speak to customer care", "human_handoff"),
    # goodbye
    ("bye", "goodbye"),
    ("thank you, that's all", "goodbye"),
    ("goodbye", "goodbye"),
    ("thanks see you", "goodbye"),
    # help / fallback-ish
    ("what can you do", "help"),
    ("help", "help"),
    ("how does this work", "help"),
    ("what are your features", "help"),
]


# --------------------------------------------------------------------------- #
# Slot vocabulary for the regex NER.
# --------------------------------------------------------------------------- #
# City/airport vocabulary now comes from the checked catalogue in locations.py
# (the old hand-written tables had wrong codes, e.g. RNC for Ranchi, UDP for Udaipur).
import locations as _L

KNOWN_CITIES: dict[str, str] = {
    alias: _L._display_city(alias, codes)
    for alias, codes in _L.CITY_ALIASES.items() if re.search(r"[a-z]", alias)
}
AIRPORT_CODES: dict[str, str] = {code.lower(): rec[1] for code, rec in _L.AIRPORTS.items()}
INDIAN_CITIES = {rec[1] for rec in _L.AIRPORTS.values() if rec[3] == "India"} | {
    v for k, v in KNOWN_CITIES.items() if all(_L.AIRPORTS[c][3] == "India" for c in _L.CITY_ALIASES[k])}
INTERNATIONAL_CITIES = {rec[1] for rec in _L.AIRPORTS.values() if rec[3] != "India"} | {
    v for k, v in KNOWN_CITIES.items() if all(_L.AIRPORTS[c][3] != "India" for c in _L.CITY_ALIASES[k])}


def detect_international(origin: str | None, destination: str | None) -> bool:
    """Return True if the route is international (Indian origin, foreign destination or vice-versa)."""
    if not origin or not destination:
        return False
    o_indian = origin in INDIAN_CITIES
    d_indian = destination in INDIAN_CITIES
    o_intl = origin in INTERNATIONAL_CITIES
    d_intl = destination in INTERNATIONAL_CITIES
    return (o_indian and d_intl) or (o_intl and d_indian) or (o_intl and d_intl)

CABIN_CLASSES = {
    "economy": "Economy",
    "premium economy": "Premium Economy",
    "business": "Business",
    "business class": "Business",
    "first": "First Class",
    "first class": "First Class",
}

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Patterns that unambiguously mean "search/book a flight" — fast path, no ML needed.
_FLIGHT_TRIGGER_PATTERNS = [
    r"^(?:search|book|find|look\s+for|get)\s+(?:a\s+|me\s+a\s+)?flights?\b",
    r"^(?:i\s+want\s+to\s+)?book\s+(?:a\s+)?flight\b",
    r"^(?:can\s+you\s+)?(?:search|find|book)\s+(?:a\s+)?flight\b",
    r"^flight\s+search\b",
    r"^(?:i\s+need|i\s+want)\s+(?:a\s+)?flight\b",
    r"^(?:search|show|find)\s+(?:me\s+)?flights?\b",
]

# Regex for flight numbers like IS766, AU196, VB174, GN321, 6E301, AI101
_FLIGHT_NUMBER_RE = re.compile(r"\b([A-Za-z0-9]{2})(\d{2,4})\b")

# Patterns for selecting a specific flight from results.
_SELECT_FLIGHT_PATTERNS = [
    # "book IndSky IS766", "select Aurora Air AU196", "choose VB174"
    r"(?:book|select|choose|pick|go\s+with|i(?:'ll)?\s+take)\s+.{0,30}?\b[A-Za-z0-9]{2}\d{2,4}\b",
    # "IndSky IS766", "Aurora Air AU196" — airline name + flight number
    r"^[A-Za-z]+(?:\s+[A-Za-z]+)?\s+[A-Za-z0-9]{2}\d{2,4}$",
]


def extract_flight_number(text: str) -> str | None:
    """Extract a flight number like IS766, AU196, VB174 from text."""
    m = _FLIGHT_NUMBER_RE.search(text)
    if m:
        return (m.group(1) + m.group(2)).upper()
    return None


def detect_select_flight(text: str) -> tuple[bool, str | None]:
    """Detect if the user is selecting a specific flight.
    Returns (is_selection, flight_number_or_None)."""
    low = text.strip().lower()
    for pat in _SELECT_FLIGHT_PATTERNS:
        if re.search(pat, low, re.IGNORECASE):
            fn = extract_flight_number(text)
            if fn:
                return True, fn
    # Bare flight number: "IS766"
    stripped = text.strip()
    if re.match(r"^[A-Za-z0-9]{2}\d{2,4}$", stripped):
        return True, stripped.upper()
    return False, None

# Date keywords for slot-reply detection.
_DATE_KEYWORDS = {
    "today", "tomorrow", "day after tomorrow", "day after",
    "next week", "this weekend", "next weekend",
    *_WEEKDAYS,
}


@dataclass
class Entities:
    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    adult_count: int | None = None
    child_count: int | None = None
    infant_count: int | None = None
    cabin_class: str | None = None
    trip_type: str | None = None
    segments: list[dict] | None = None
    origin_country: str | None = None
    destination_country: str | None = None
    raw_matches: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "adult_count": self.adult_count,
            "child_count": self.child_count,
            "infant_count": self.infant_count,
            "cabin_class": self.cabin_class,
            "trip_type": self.trip_type,
            "segments": self.segments,
            "origin_country": self.origin_country,
            "destination_country": self.destination_country,
        }


# --------------------------------------------------------------------------- #
# Passenger parser — handles natural language passenger descriptions.
# --------------------------------------------------------------------------- #
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1,
}


def parse_passengers(text: str) -> dict:
    """Parse passenger counts from natural text.

    Returns dict with adult_count, child_count, infant_count.
    Any unmentioned type returns None (not 0) so caller can decide defaults.
    """
    low = text.lower().strip()
    result = {"adult_count": None, "child_count": None, "infant_count": None}

    num_word_pat = r"(?:" + "|".join(_NUMBER_WORDS.keys()) + r"|\d+)"

    def _to_int(s: str) -> int:
        s = s.strip().lower()
        if s in _NUMBER_WORDS:
            return _NUMBER_WORDS[s]
        try:
            return int(s)
        except ValueError:
            return 0

    # Explicit patterns: "N adult(s)", "N child/children", "N infant(s)"
    adult_m = re.search(rf"({num_word_pat})\s*adults?", low)
    child_m = re.search(rf"({num_word_pat})\s*(?:children|childs?|kids?)", low)
    infant_m = re.search(rf"({num_word_pat})\s*(?:infants?|babies|baby)", low)

    if adult_m:
        result["adult_count"] = _to_int(adult_m.group(1))
    if child_m:
        result["child_count"] = _to_int(child_m.group(1))
    if infant_m:
        result["infant_count"] = _to_int(infant_m.group(1))

    # If any explicit type was found, return immediately.
    if any(v is not None for v in result.values()):
        return result

    # Colloquial patterns
    if re.search(r"\bme\s+and\s+my\s+(?:wife|husband|partner|spouse)\b", low):
        result["adult_count"] = 2
        return result
    if re.search(r"\b(?:just\s+)?(?:for\s+)?me\b", low) and len(low.split()) <= 3:
        result["adult_count"] = 1
        return result
    if re.search(r"\b(?:for\s+)?(?:two|2)\s+(?:people|persons?)\b", low):
        result["adult_count"] = 2
        return result

    # "family of N" → all adults by default
    family_m = re.search(rf"\bfamily\s+of\s+({num_word_pat})\b", low)
    if family_m:
        result["adult_count"] = _to_int(family_m.group(1))
        return result

    # "N passengers" / "N people" / "for N"
    pax_m = re.search(rf"({num_word_pat})\s*(?:passengers?|people|persons?|pax|travellers?|travelers?)", low)
    if not pax_m:
        pax_m = re.search(rf"\bfor\s+({num_word_pat})\b(?!\s*nights?)", low)
    if pax_m:
        result["adult_count"] = _to_int(pax_m.group(1))
        return result

    return result


def parse_cabin_class(text: str) -> str | None:
    """Parse cabin class from text. Returns normalized name or None."""
    low = text.lower().strip()
    # Check longest keys first to match "premium economy" before "economy".
    for key in sorted(CABIN_CLASSES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", low):
            return CABIN_CLASSES[key]
    return None


def detect_slot_reply_type(text: str) -> str | None:
    """Detect what type of slot-filling reply this is (without context).

    Returns one of: 'trip_type', 'city', 'date', 'passenger', 'cabin', or None.
    """
    low = text.strip().lower()

    # Check trip type
    _trip_keywords = {
        "one way", "one-way", "oneway", "round trip", "round-trip", "roundtrip",
        "return", "return trip", "single", "both ways", "two way", "two-way",
    }
    if low in _trip_keywords:
        return "trip_type"

    # Check cabin class first (before city check, since "economy" etc.)
    if parse_cabin_class(low):
        return "cabin"

    # Check date keywords
    if low in _DATE_KEYWORDS:
        return "date"
    # dd/mm or dd-mm pattern
    if re.match(r"^\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?$", low):
        return "date"
    # ISO date pattern (from calendar picker: 2026-07-05)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", low):
        return "date"

    # Check passenger patterns
    pax = parse_passengers(low)
    if any(v is not None for v in pax.values()):
        return "passenger"

    # Check city/airport code
    if low in AIRPORT_CODES or low in KNOWN_CITIES:
        return "city"

    return None


# --------------------------------------------------------------------------- #
# Classifier
# --------------------------------------------------------------------------- #
class IntentClassifier:
    """Trains both candidate models on import and keeps the winner."""

    def __init__(self) -> None:
        self.vectorizer_params = dict(ngram_range=(1, 2), lowercase=True, min_df=1)
        self.model: Pipeline | None = None
        self.selected = "logreg"
        self.macro_f1 = 0.0
        self._train()

    def _build(self, clf) -> Pipeline:
        return Pipeline(
            [
                ("tfidf", TfidfVectorizer(**self.vectorizer_params)),
                ("clf", clf),
            ]
        )

    def _train(self) -> None:
        texts = [t for t, _ in TRAINING_DATA]
        labels = [y for _, y in TRAINING_DATA]
        X = np.array(texts)
        y = np.array(labels)

        # Use few folds because some classes are tiny; this is a demo-scale dataset.
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

        logreg = self._build(LogisticRegression(max_iter=1000, C=4.0))
        svm = self._build(LinearSVC(C=1.0))

        try:
            logreg_pred = cross_val_predict(logreg, X, y, cv=cv)
            svm_pred = cross_val_predict(svm, X, y, cv=cv)
            f1_logreg = f1_score(y, logreg_pred, average="macro", zero_division=0)
            f1_svm = f1_score(y, svm_pred, average="macro", zero_division=0)
        except ValueError:
            # Not enough samples per class to cross-validate; default to LogReg.
            f1_logreg, f1_svm = 1.0, 0.0

        # Selection rule: LogReg unless SVM wins macro-F1 by >= 0.03.
        if f1_svm - f1_logreg >= 0.03:
            self.selected = "svm"
            self.macro_f1 = float(f1_svm)
            # Wrap SVM so we still get probabilities for the confidence gate.
            calibrated = self._build(CalibratedClassifierCV(LinearSVC(C=1.0), cv=3))
            calibrated.fit(X, y)
            self.model = calibrated
        else:
            self.selected = "logreg"
            self.macro_f1 = float(f1_logreg)
            logreg.fit(X, y)
            self.model = logreg

    # Exact-match greetings that should always return high confidence.
    _GREETING_EXACT = {
        "hi", "hey", "hello", "namaste", "good morning", "good afternoon",
        "good evening", "hey there", "hola", "howdy", "sup", "yo",
    }

    # Small-talk phrases that get a short natural reply, not a full help message.
    _SMALL_TALK = {
        "how are you": "I'm good, thank you! How can I help with your flight today?",
        "how are you aura": "I'm good, thank you! How can I help with your flight today?",
        "how are you doing": "I'm doing great! How can I help with your flight today?",
        "are you there": "Yes, I'm here to help with your flight search and booking support.",
        "who are you": "I'm Aura, your flight assistant. I can help you search and book flights, choose seats, and more.",
        "what is your name": "I'm Aura, your flight assistant.",
        "whats up": "I'm here and ready to help! Need to search for a flight?",
    }

    def predict(self, text: str) -> tuple[str, float]:
        """Return (intent, confidence). Confidence is max class probability."""
        if not text or not text.strip():
            return "help", 0.0

        normalised = text.strip().lower()

        # Fast-path 0: small-talk ("how are you", "are you there", "who are you").
        if normalised in self._SMALL_TALK:
            return "small_talk", 0.95

        # Fast-path 1: exact greeting matches.
        if normalised in self._GREETING_EXACT:
            return "greeting", 0.95

        # Fast-path 1.5: flight selection ("book IndSky IS766", "AU196").
        # Must fire BEFORE flight_search triggers to avoid mis-routing.
        is_select, flight_no = detect_select_flight(text)
        if is_select and flight_no:
            return "select_flight", 0.95

        # Fast-path 2: flight trigger patterns ("search a flight", "book a flight", etc.)
        for pat in _FLIGHT_TRIGGER_PATTERNS:
            if re.search(pat, normalised):
                return "flight_search", 0.92

        # Fast-path 2.3: international flight keywords
        _intl_kw = {"international flight", "international trip", "travel abroad",
                    "book international flight", "international flights"}
        if normalised in _intl_kw or any(kw in normalised for kw in _intl_kw):
            return "flight_search", 0.92

        # Fast-path 2.5: multi-city checks
        if "multi city" in normalised or "multicity" in normalised or "multi-city" in normalised:
            return "flight_search", 0.95
        to_matches = re.findall(r'\b[a-z]{3,15}\b\s+to\s+\b[a-z]{3,15}\b', normalised)
        if len(to_matches) >= 2:
            return "flight_search", 0.95

        # Fast-path 3: route patterns like "blr to del", "from mumbai to goa".
        route = detect_route_pattern(normalised)
        if route:
            return "flight_search", 0.92

        # Fast-path 4: bare airport code or city name (slot-only reply).
        if normalised in AIRPORT_CODES or normalised in KNOWN_CITIES:
            return "_slot_reply", 0.90

        # Fast-path 5: detect slot-reply types (date, passenger, cabin).
        slot_type = detect_slot_reply_type(normalised)
        if slot_type:
            return f"_slot_reply_{slot_type}", 0.90

        proba = self.model.predict_proba([text])[0]
        idx = int(np.argmax(proba))
        intent = self.model.classes_[idx]
        return str(intent), float(proba[idx])


# --------------------------------------------------------------------------- #
# Regex NER (the "custom NER"). spaCy augments it when available.
# --------------------------------------------------------------------------- #
def _normalize_date(token: str) -> str:
    today = date.today()
    token = token.lower().strip()
    if token == "today":
        return today.isoformat()
    if token == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if token in ("day after tomorrow", "day after"):
        return (today + timedelta(days=2)).isoformat()
    if token in _WEEKDAYS:
        target = _WEEKDAYS.index(token)
        ahead = (target - today.weekday()) % 7
        ahead = 7 if ahead == 0 else ahead
        return (today + timedelta(days=ahead)).isoformat()
    if token in ("next week",):
        return (today + timedelta(days=7)).isoformat()
    # dd-mm or dd/mm (assume current year)
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?$", token)
    if m:
        p1, p2 = int(m.group(1)), int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else today.year
        if yr < 100:
            yr += 2000
        # Try both formats: day-month and month-day
        try:
            return date(yr, p2, p1).isoformat()
        except ValueError:
            try:
                return date(yr, p1, p2).isoformat()
            except ValueError:
                return token
    return token


def detect_route_pattern(text: str) -> tuple[str, str] | None:
    """Detect '<origin> to <destination>' patterns using city names or airport codes.
    Returns (origin_city, dest_city) or None."""
    low = text.strip().lower()
    # Patterns: "X to Y", "from X to Y", "flight from X to Y", "book flight X to Y"
    m = re.search(
        r"(?:(?:book\s+)?(?:a\s+)?(?:flight|flights)?\s*)?(?:from\s+)?([a-z ]+?)\s+to\s+([a-z ]+?)(?:\s+(?:on|for|tomorrow|today|next|this|\d)|$)",
        low,
    )
    if not m:
        return None
    origin_raw = m.group(1).strip()
    dest_raw = m.group(2).strip()
    origin = _match_city(origin_raw)
    dest = _match_city(dest_raw)
    if origin and dest:
        return origin, dest
    return None


def extract_multi_city_segments(text: str) -> list[dict]:
    # Splits the text by 'and', 'then', or comma.
    parts = re.split(r'\band\b|\bthen\b|,', text.lower())
    segments = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Find origin and destination
        # Match "X to Y"
        m = re.search(r'\b([a-z ]+?)\s+to\s+([a-z ]+?)(?:\s+(?:on|for|tomorrow|today|next|this|\d)|$)', part)
        origin, dest = None, None
        if m:
            origin = _match_city(m.group(1))
            dest = _match_city(m.group(2))
        else:
            # Let's see if there are any city names
            found_cities = []
            words = re.findall(r'\b[a-z]{3,15}\b', part)
            for w in words:
                c = _match_city(w)
                if c and c not in found_cities:
                    found_cities.append(c)
            if len(found_cities) >= 2:
                origin, dest = found_cities[0], found_cities[1]
        
        if origin and dest:
            # Extract date for this segment if present
            dep_date = None
            date_patterns = [
                r"\b\d{4}-\d{2}-\d{2}\b",
                r"day after tomorrow", r"\btomorrow\b", r"\btoday\b", r"next week",
                *[rf"\b{d}\b" for d in _WEEKDAYS],
                r"\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?\b"
            ]
            for pat in date_patterns:
                dm = re.search(pat, part)
                if dm:
                    dep_date = _normalize_date(dm.group(0))
                    break
            segments.append({
                "origin": origin,
                "destination": dest,
                "departure_date": dep_date
            })
    return segments


COUNTRIES = {
    "india": "India",
    "uae": "UAE",
    "united arab emirates": "UAE",
    "uk": "UK",
    "united kingdom": "UK",
    "usa": "USA",
    "us": "USA",
    "singapore": "Singapore",
    "thailand": "Thailand",
    "malaysia": "Malaysia",
    "france": "France",
    "germany": "Germany",
    "maldives": "Maldives",
    "sri lanka": "Sri Lanka",
}


def _resolve_place(word: str) -> tuple[str | None, str | None]:
    """Return (city_name, country_name) if resolved, otherwise (None, None)."""
    w = word.strip().lower()
    city = _match_city(w)
    if city:
        return city, None
    if w in COUNTRIES:
        return None, COUNTRIES[w]
    return None, None


def extract_entities(text: str) -> Entities:
    ent = Entities()
    low = text.lower()

    # Trip type parsing
    trip = None
    to_matches = re.findall(r'\b[a-z]{3,15}\b\s+to\s+\b[a-z]{3,15}\b', low)
    if "multi city" in low or "multicity" in low or "multi-city" in low or len(to_matches) >= 2:
        trip = "multi_city"
    elif any(kw in low for kw in ["round trip", "round-trip", "roundtrip", "return", "both ways"]):
        trip = "round_trip"
    elif any(kw in low for kw in ["one way", "one-way", "oneway", "single"]):
        # Guard: "one day" must NOT match "one way".
        if "one day" not in low:
            trip = "one_way"
    
    if trip:
        ent.trip_type = trip

    if ent.trip_type == "multi_city":
        ent.segments = extract_multi_city_segments(text)
    else:
        # Check for X to Y pattern where X/Y can be cities or countries.
        m = re.search(
            r"(?:from\s+)?([a-z ]{2,30}?)\s+to\s+([a-z ]{2,30}?)(?:\s+(?:on|for|tomorrow|today|next|this|\d)|$)",
            low,
        )
        if m:
            p1_raw = m.group(1).strip()
            p2_raw = m.group(2).strip()
            c1, cntry1 = _resolve_place(p1_raw)
            c2, cntry2 = _resolve_place(p2_raw)
            if c1 or cntry1:
                ent.origin = c1
                ent.origin_country = cntry1
            if c2 or cntry2:
                ent.destination = c2
                ent.destination_country = cntry2

        if not ent.origin and not ent.destination:
            # Check for multilingual directionality:
            # Origin suffixes: la irundhu, irundhu, se, nundi, inda, ninnu
            # Destination suffixes: ku, ki, ge, ilekku, tak, ke liye
            origin_m = re.search(r"\b([a-z]+)\s+(?:la\s+irundhu|irundhu|se|nundi|inda|ninnu)\b", low)
            if origin_m:
                c1, cntry1 = _resolve_place(origin_m.group(1))
                if c1 or cntry1:
                    ent.origin = c1
                    ent.origin_country = cntry1
            
            dest_m = re.search(r"\b([a-z]+)\s+(?:ku|ki|ge|ilekku|tak|ke\s+liye)\b", low)
            if dest_m:
                c2, cntry2 = _resolve_place(dest_m.group(1))
                if c2 or cntry2:
                    ent.destination = c2
                    ent.destination_country = cntry2
            else:
                for suffix in ["ku", "ki", "ge"]:
                    m = re.search(rf"\b([a-z]+){suffix}\b", low)
                    if m:
                        c2, cntry2 = _resolve_place(m.group(1))
                        if c2 or cntry2:
                            ent.destination = c2
                            ent.destination_country = cntry2
                            break

    # Passengers: parse with the full parser
    pax = parse_passengers(low)
    if pax["adult_count"] is not None:
        ent.adult_count = pax["adult_count"]
    if pax["child_count"] is not None:
        ent.child_count = pax["child_count"]
    if pax["infant_count"] is not None:
        ent.infant_count = pax["infant_count"]

    # Cabin class
    cabin = parse_cabin_class(low)
    if cabin:
        ent.cabin_class = cabin

    # Dates
    date_patterns = [
        r"day after tomorrow", r"\btomorrow\b", r"\btoday\b", r"next week",
        *[rf"\b{d}\b" for d in _WEEKDAYS],
        r"\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?\b",
    ]
    for pat in date_patterns:
        m = re.search(pat, low)
        if m:
            ent.departure_date = _normalize_date(m.group(0))
            break

    # If both are filled, we are done with route extraction.
    if (ent.origin or ent.origin_country) and (ent.destination or ent.destination_country):
        return ent

    # Cities or countries with from/to directionality
    from_m = re.search(r"\bfrom\s+([a-z ]{2,30}?)(?:\s+to\b|\s+on\b|\s+for\b|$)", low)
    to_m = re.search(r"\bto\s+([a-z ]{2,30}?)(?:\s+from\b|\s+on\b|\s+for\b|\s+tomorrow\b|\s+today\b|\s+next\b|$)", low)
    
    if from_m and not ent.origin and not ent.origin_country:
        c1, cntry1 = _resolve_place(from_m.group(1))
        if c1 or cntry1:
            ent.origin = c1
            ent.origin_country = cntry1
            
    if to_m and not ent.destination and not ent.destination_country:
        c2, cntry2 = _resolve_place(to_m.group(1))
        if c2 or cntry2:
            ent.destination = c2
            ent.destination_country = cntry2

    # Any other known cities / airport codes mentioned without from/to keywords.
    if not ent.destination and not ent.origin and not ent.origin_country and not ent.destination_country:
        found_cities = []
        found_countries = []
        words = re.findall(r'\b[a-z]{3,30}\b', low)
        for w in words:
            c1, cntry1 = _resolve_place(w)
            if c1 and c1 not in found_cities:
                found_cities.append(c1)
            if cntry1 and cntry1 not in found_countries:
                found_countries.append(cntry1)
        if found_cities:
            ent.destination = found_cities.pop(0)
            if found_cities:
                ent.origin = found_cities.pop(0)
        elif found_countries:
            ent.destination_country = found_countries.pop(0)
            if found_countries:
                ent.origin_country = found_countries.pop(0)

    # spaCy GPE as a backstop only.
    if _NLP is not None and (not ent.destination) and (not ent.destination_country):
        doc = _NLP(text)
        gpes = [e.text for e in doc.ents if e.label_ == "GPE"]
        for g in gpes:
            c, cntry = _resolve_place(g)
            if c and c not in (ent.origin, ent.destination):
                ent.destination = c
                break
            elif cntry and cntry not in (ent.origin_country, ent.destination_country):
                ent.destination_country = cntry
                break

    return ent


def _match_city(fragment: str) -> str | None:
    """Resolve a text fragment to a canonical city name.
    Checks airport codes first (exact match), then known city names."""
    frag = fragment.strip().lower()
    # Airport code (exact).
    if frag in AIRPORT_CODES:
        return AIRPORT_CODES[frag]
    # Full city name (exact).
    if frag in KNOWN_CITIES:
        return KNOWN_CITIES[frag]
    # Substring search in known cities. Only return if exactly one city is matched.
    matched_cities = []
    for raw, canon in KNOWN_CITIES.items():
        if re.search(rf"\b{re.escape(raw)}\b", frag):
            if canon not in matched_cities:
                matched_cities.append(canon)
    if len(matched_cities) == 1:
        return matched_cities[0]
    return None


# Singleton trained once at import.
CLASSIFIER = IntentClassifier()


if __name__ == "__main__":
    print(f"Selected model: {CLASSIFIER.selected} (macro-F1={CLASSIFIER.macro_f1:.2f})")
    test_cases = [
        "flight from mumbai to delhi tomorrow for 2 people in business",
        "i need a hotel in goa",
        "cancel my booking",
        "asdkjh qwoieu",
        # Airport-code & route-pattern tests
        "blr to del",
        "del to bom",
        "from blr to bom",
        "flight from delhi to mumbai",
        "del",   # bare code — slot reply
        "bom",   # bare code — slot reply
        # New: flight trigger fast paths
        "search a flight",
        "book a flight",
        "find a flight",
        # Passenger parsing
        "2 adults 1 child 1 infant",
        "me and my wife",
        # Cabin class
        "business",
        "premium economy",
        "economy",
        "first class",
        # Date slot reply
        "tomorrow",
    ]
    for q in test_cases:
        intent, conf = CLASSIFIER.predict(q)
        ents = extract_entities(q)
        print(f"\n> {q}\n  intent={intent} conf={conf:.2f}\n  slots={ents.as_dict()}")
