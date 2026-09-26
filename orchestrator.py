# -*- coding: utf-8 -*-
"""
Layer 3 - Conversation orchestration (custom state machine, no LangGraph).

One turn:
    settings (reply language, time zone)
      -> button action?  ---------------------------------> action handler
      -> understand(text): rules (nlu_rules) + TF-IDF classifier
                           + optional mBERT + optional LLM extraction
      -> pending clarification? (airport choice, role, family breakdown ...)
      -> route: command | info (RAG) | flight | hotel | plan | social | clarify
      -> mode step: apply new facts to structured state, validate,
                    ask ONLY for what is still missing, or search
      -> finalize: localized reply, blocks (cards), quick replies,
                   optional LLM rephrase with fact guard, analytics fields

Structured state (per session):
    flight  : trip_type, legs[{origin, destination, date}], return_date,
              adults/children/infants, cabin
    hotel   : city, check-in/out, rooms, guests
    plan    : curated plan id, days, interests, budget style, travellers
    results : sample options shown;  selection : chosen flights/hotel/seats
"""

from __future__ import annotations

import logging
import math
import os
import re
import time

import dates as D
import i18n
import llm
import locations as L
import nlu_rules as N
import providers
import rag_engine
from intent_classifier import CLASSIFIER

log = logging.getLogger("aura.orchestrator")

CONFIDENCE_THRESHOLD = 0.35
MAX_LEGS = 5
MAX_PAX = 9
MAX_NIGHTS = 30
RAG_INTENTS = {"baggage_info", "web_checkin", "insurance", "modify_booking",
               "cancel_booking", "refund_status", "visa_enquiry"}
GREET_RE = re.compile(r"^(hi+|hey+|hello|hola|namaste|namaskar[a]?|namaskaram|vanakkam|good\s+(?:morning|afternoon|evening)|ನಮಸ್ಕಾರ|ನಮಸ್ತೆ|नमस्ते|नमस्कार|வணக்கம்|నమస్కారం|നമസ്കാരം)[\s!.,]*(?:aura|ಔರಾ|ऑरा)?[\s!.]*$", re.I)
SOCIAL = {"greeting", "goodbye", "help", "small_talk", "human_handoff"}
RESET_WORDS = re.compile(r"^(new search|start over|start again|reset|restart|clear|book another flight|ಹೊಸದಾಗಿ ಪ್ರಾರಂಭಿಸಿ|फिर से शुरू)\b", re.I)
LANG_SWITCH = [
    (re.compile(r"\b(?:reply|speak|talk|respond|continue|switch|change)\b.*\b(?:in|to)\s+english\b|\benglish\s+please\b|\bin\s+english\b", re.I), "en"),
    (re.compile(r"\b(?:reply|speak|talk|respond|continue|switch|change)\b.*\b(?:in|to)\s+kannada\b|\bkannada\s*(?:please|dalli|alli)\b|ಕನ್ನಡದಲ್ಲಿ", re.I), "kn"),
    (re.compile(r"\b(?:reply|speak|talk|respond|continue|switch|change)\b.*\b(?:in|to)\s+hindi\b|\bhindi\s*(?:please|mein|me)\b|हिंदी\s*में|हिन्दी\s*में", re.I), "hi"),
]


def t(state, key, **kw):
    return i18n.t(key, state.get("lang", "en"), **kw)


# --------------------------------------------------------------------- state
def _leg() -> dict:
    return {"origin": None, "destination": None, "date": None}


def _flight() -> dict:
    return {"trip_type": None, "legs": [_leg()], "return_date": None, "adults": None,
            "children": 0, "infants": 0, "cabin": None, "mc_done": False}


def _hotel() -> dict:
    return {"city": None, "checkin": None, "checkout": None, "nights_hint": None,
            "rooms": None, "adults": None, "children": 0, "unsupported": None}


def _plan() -> dict:
    return {"plan_id": None, "days": None, "interests": [], "style": None,
            "travellers": None, "budget_amount": None, "prefs_asked": False}


def new_state(session_id: str) -> dict:
    s = {
        "session_id": session_id, "history": [], "lang": "en", "lang_mode": "auto", "tz": D.DEFAULT_TZ,
        "mode": None, "flight": _flight(), "hotel": _hotel(), "plan": _plan(),
        "pending": [], "asked": None,
        "results": {"flights": {}, "hotels": []},
        "selection": {"flights": {}, "hotel": None, "seats": {}},
        "last_plan": None, "checkout": None, "intent": None,
    }
    s["slots"] = compat_slots(s)
    s["expected_slot"] = None
    return s


# Backwards-compatible alias used by older scripts.
def _empty_slots() -> dict:
    return compat_slots(new_state("x"))


# --------------------------------------------------------------------- turn
class Turn:
    def __init__(self, state: dict, text: str):
        self.state = state
        self.text = text or ""
        self.today = D.today_for(state.get("tz"))
        self.acks: list[str] = []
        self.changed: set = set()
        self.notes: list[str] = []
        self.errors: list[str] = []
        self.body: list[str] = []
        self.blocks: list[dict] = []
        self.quick: list[dict] = []
        self.hint: dict | None = None
        self.intent = None
        self.confidence = 1.0
        self.source = "fast"
        self.ask_feedback = False
        self.rag: dict | None = None
        self.flight_changed = False
        self.hotel_changed = False
        self.extra: dict = {}
        self.timings: dict = {}

    def tr(self, key, **kw):
        return t(self.state, key, **kw)

    def qr(self, label: str, value: str):
        if not any(q["value"] == value for q in self.quick):
            self.quick.append({"label": label, "value": value})


# --------------------------------------------------------------------- format helpers
def money(n: int | float) -> str:
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def loc_label(loc: dict | None) -> str:
    return L.label(loc)


def fdate(state, iso) -> str:
    return D.fmt(iso, state.get("lang", "en"))


def pax_text(state, adults, children=0, infants=0) -> str:
    parts = [i18n.t("n_adults", state["lang"], n=adults)]
    if children:
        parts.append(i18n.t("n_children", state["lang"], n=children))
    if infants:
        parts.append(i18n.t("n_infants", state["lang"], n=infants))
    return ", ".join(parts)


def cabin_text(state, cabin) -> str:
    return i18n.t(f"cabin_{(cabin or 'Economy').replace(' ', '_')}", state["lang"])


# --------------------------------------------------------------------- understanding
def _llm_ok() -> bool:
    try:
        return llm.available_cached()
    except Exception:
        return False


def understand(turn: Turn) -> dict:
    state, text = turn.state, turn.text
    u = N.extract(text, turn.today)
    t0 = time.perf_counter()
    intent, conf = CLASSIFIER.predict(text)
    turn.timings["intent_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    source = "fast"

    # optional multilingual model (off by default)
    try:
        from nlu import mbert_classifier as MB
        multilingual = MB.detect_multilingual_text(text)
    except Exception:
        MB, multilingual = None, False
    if MB is not None and os.environ.get("USE_MBERT", "false").lower() == "true" and (multilingual or conf < CONFIDENCE_THRESHOLD):
        try:
            res = MB.predict_intent_with_mbert(text)
            if res.get("confidence", 0) >= float(os.environ.get("MBERT_CONFIDENCE_THRESHOLD", "0.70")):
                intent, conf, source = res["intent"], float(res["confidence"]), "mbert"
        except Exception as e:  # model failure must degrade safely
            log.error("mBERT failed: %s", e)
            intent, conf, source = "fallback", 0.0, "custom_fallback"

    if intent.startswith("_slot_reply"):
        intent = "slot_reply"
    if GREET_RE.match(text.strip()) and source != "custom_fallback":
        intent, conf = "greeting", 0.95

    # LLM extraction only when the deterministic layer found nothing usable.
    signal = (N.has_booking_entities(u) or u["domain_flight"] or u["domain_hotel"] or u["cmd_plan"]
              or u["info"] or u["yes"] or u["no"] or any(u[k] for k in ("cmd_checkout", "cmd_review", "cmd_simulate"))
              or (intent in SOCIAL | RAG_INTENTS | {"flight_search", "hotel_search", "select_flight"} and conf >= 0.55))
    if not signal and source != "custom_fallback" and len(text.split()) >= 3 and _llm_ok():
        t1 = time.perf_counter()
        out = llm.extract(text, {"mode": state.get("mode"), "asked": state.get("asked"), "today": turn.today.isoformat()})
        turn.timings["llm_ms"] = round((time.perf_counter() - t1) * 1000, 1)
        if out:
            source = "llm"
            _merge_llm(u, out, turn.today)
            if out.get("intent"):
                intent, conf = out["intent"], float(out.get("confidence") or 0.8)
        else:
            source = "degraded"
    turn.intent, turn.confidence, turn.source = intent, conf, source
    u["intent"], u["conf"] = intent, conf
    return u


def _merge_llm(u: dict, out: dict, today) -> None:
    """LLM output is untrusted: every value is re-validated through our resolvers."""
    ents = out.get("entities") or {}
    def place(val, role):
        if not val or not isinstance(val, str):
            return
        for p in L.find_places(val)[:1]:
            p.extra["role"] = role
            u["places"].append(p)
    place(ents.get("origin"), "origin")
    place(ents.get("destination"), "destination")
    place(ents.get("hotel_city"), "at")
    for key, role in (("departure_date", "depart"), ("return_date", "return"),
                      ("check_in", "checkin"), ("check_out", "checkout")):
        v = ents.get(key)
        if isinstance(v, str) and v:
            for h in D.find_dates(v, today)[:1]:
                h.role = role
                u["dates"].append(h)
    for key, dst in (("adults", "adults"), ("children", "children"), ("infants", "infants")):
        v = ents.get(key)
        if isinstance(v, int) and 0 <= v <= MAX_PAX and v:
            u["pax"][dst] = v
    cab = ents.get("cabin_class")
    if isinstance(cab, str):
        u["cabin"] = N.parse_cabin(cab) or u["cabin"]
    tt = ents.get("trip_type")
    if tt in ("one_way", "round_trip", "multi_city"):
        u["trip_type"] = tt
    if out.get("intent") == "flight_search":
        u["domain_flight"] = True
    elif out.get("intent") == "hotel_search":
        u["domain_hotel"] = True
    elif out.get("intent") in ("plan_trip", "itinerary"):
        u["cmd_plan"] = u["domain_plan"] = True


# --------------------------------------------------------------------- entry point
def run_turn(state: dict, user_text: str, action: str | None = None, payload: dict | None = None,
             lang: str | None = None, lang_mode: str | None = None, tz: str | None = None,
             from_button: bool = False) -> dict:
    t_start = time.perf_counter()
    _apply_settings(state, lang, lang_mode, tz)
    text = (user_text or "").strip()
    turn = Turn(state, text)
    if text:
        state["history"].append({"role": "user", "text": text})
        if state["lang_mode"] == "auto" and not from_button:
            detected = i18n.detect_script_language(text)
            if detected:
                state["lang"] = detected
    try:
        if action:
            handle_action(turn, action, payload or {})
        else:
            handle_text(turn)
    finally:
        turn.timings["total_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    return finalize(turn)


def _apply_settings(state, lang, lang_mode, tz):
    if lang_mode in ("auto", "manual"):
        state["lang_mode"] = lang_mode
    if lang in i18n.LANGS and (lang_mode == "manual" or state.get("lang_mode") == "manual"):
        state["lang"] = lang
    if tz:
        state["tz"] = D.valid_tz(tz)


# --------------------------------------------------------------------- text routing
def handle_text(turn: Turn) -> None:
    state, text = turn.state, turn.text
    low = text.lower()

    if RESET_WORDS.match(low):
        _reset(state)
        turn.intent = "reset"
        turn.body.append(turn.tr("reset"))
        turn.extra["clear_results"] = True
        _starter_quick(turn)
        return

    for pat, code in LANG_SWITCH:
        if pat.search(text):
            state["lang"], state["lang_mode"] = code, "manual"
            turn.intent = "language_switch"
            turn.body.append(turn.tr("language_set"))
            if state.get("asked"):
                _continue_mode(turn)
            return

    u = understand(turn)

    # 1) pending clarification first
    if state["pending"] and _resolve_pending(turn, u):
        return

    # 2) explicit commands that act on current selections
    if _commands(turn, u):
        return

    # 3) travel-knowledge questions (grounded retrieval)
    if u["info"] or (u["intent"] in RAG_INTENTS and u["conf"] >= 0.45 and not N.has_booking_entities(u)):
        _info(turn, u)
        return

    mode = state.get("mode")
    entities = N.has_booking_entities(u)
    places = u["places"]
    asked = state.get("asked") or ""
    if mode == "flight" and (asked in ("origin", "destination") or asked.startswith("leg_route")) \
            and not entities and not _other_intent(u) and re.search(r"[A-Za-z\u0900-\u097F\u0C80-\u0CFF]{3,}", text):
        _unknown_place(turn, asked)
        return

    # 4) choose the flow
    if mode == "plan" and re.search(r"change\s+(?:my\s+)?pref|different\s+pref|ಆದ್ಯತೆ\s*ಬದಲ|पसंद\s*बदल", low):
        state["plan"].update({"interests": [], "style": None, "prefs_asked": False})
        plan_step(turn, dict(u, interests=[], cmd_no_pref=False))
        return
    if u["cmd_plan"] or (mode == "plan" and (entities or u["interests"] or u["duration"] or u["cmd_no_pref"])
                         and not u["domain_flight"] and not u["domain_hotel"]):
        _enter(state, "plan")
        plan_step(turn, u)
        return
    wants_hotel = (u["domain_hotel"] and not u["domain_flight"]) or (
        u["intent"] == "hotel_search" and u["conf"] >= 0.5 and mode != "flight" and not u["domain_flight"])
    if wants_hotel or (mode == "hotel" and (entities or u["rooms"] or u["duration"]) and not u["domain_flight"]):
        _enter(state, "hotel")
        hotel_step(turn, u)
        return
    mc_answer = state.get("asked") == "mc_more" and (u["yes"] or u["no"] or u["cmd_add_leg"] or u["cmd_search"])
    if u["domain_flight"] or (u["intent"] == "flight_search" and u["conf"] >= 0.5) or u["trip_type"] \
            or (mode is None and len(places) >= 2) or (mode == "flight" and (entities or mc_answer or u["cmd_remove"])):
        _enter(state, "flight")
        flight_step(turn, u)
        return
    if mode is None and len(places) == 1 and not u["info"]:
        _what_for(turn, places[0])
        return

    # 5) social / fallback
    intent = u["intent"]
    if intent in SOCIAL and turn.source != "custom_fallback":
        _social(turn, intent, low)
        return
    _clarify(turn, u)


def _enter(state, mode):
    if state.get("mode") != mode:
        state["asked"] = None
    state["mode"] = mode


def _continue_mode(turn):
    """Re-ask the open question (e.g. after a language change)."""
    mode = turn.state.get("mode")
    empty = N.extract("", turn.today)
    if mode == "flight":
        flight_next(turn)
    elif mode == "hotel":
        hotel_next(turn)
    elif mode == "plan":
        plan_step(turn, empty)


def _reset(state):
    keep = {k: state[k] for k in ("session_id", "history", "lang", "lang_mode", "tz")}
    fresh = new_state(state["session_id"])
    state.clear()
    state.update(fresh)
    state.update(keep)


def _starter_quick(turn):
    turn.qr(turn.tr("qr_book_flight"), "Book a flight")
    turn.qr(turn.tr("qr_find_hotel"), "Find a hotel")
    turn.qr(turn.tr("qr_plan_trip"), "Plan a trip")


def _social(turn, intent, low):
    turn.intent = intent
    if intent == "greeting":
        turn.body.append(turn.tr("greeting"))
        _starter_quick(turn)
    elif intent == "goodbye":
        turn.body.append(turn.tr("goodbye"))
    elif intent == "human_handoff":
        turn.body.append(turn.tr("handoff"))
    elif intent == "small_talk":
        key = "who_are_you" if ("who" in low or "name" in low) else "how_are_you"
        turn.body.append(turn.tr(key))
        _starter_quick(turn)
    else:
        turn.body.append(turn.tr("help"))
        _starter_quick(turn)
    if turn.state.get("asked") and intent != "goodbye":
        _continue_mode(turn)


def _clarify(turn, u):
    turn.intent = "fallback"
    if turn.source == "custom_fallback" or not u["text"].strip():
        turn.body.append(turn.tr("clarify_rephrase"))
    elif turn.state.get("asked"):
        turn.body.append(turn.tr("didnt_get"))
        _continue_mode(turn)
        return
    else:
        turn.body.append(turn.tr("clarify"))
    _starter_quick(turn)


_PHRASE_RE = re.compile(r"\b(from|to)\s+([A-Za-z][A-Za-z]{2,}(?:\s+[A-Za-z]{3,})?)")
_NOT_PLACE = re.compile(r"(?i)^(the|a|an|my|me|go|fly|book|travel|visit|come|be|see|do|get|return|economy|business|"
                        r"premium|first|change|make|add|stay|check|reach|plan|somewhere|anywhere|home)\b")


def _unmatched_phrases(u) -> list[tuple[str, str]]:
    out = []
    for m in _PHRASE_RE.finditer(u["text"]):
        a, b = m.start(2), m.end(2)
        word = m.group(2).split()[0] if len(m.group(2).split()) > 1 and L.suggest(m.group(2).split()[0]) else m.group(2)
        if _NOT_PLACE.match(word) or any(p.start < b and a < p.end for p in u["places"]):
            continue
        if any(d.start < b and a < d.end for d in u["dates"]):
            continue
        out.append(("origin" if m.group(1).lower() == "from" else "destination", word))
    return out


def _unknown_place(turn, asked):
    state = turn.state
    u_phr = _PHRASE_RE.search(turn.text)
    raw = (u_phr.group(2) if u_phr else turn.text.strip())[:40]
    sug = L.suggest(raw)
    if sug:
        F = state["flight"]
        if asked.startswith("leg_route"):
            i = int(asked.split(":")[1])
            field = "origin" if not F["legs"][i]["origin"] else "destination"
        else:
            i, field = 0, asked
        _push_pending(state, {"kind": "airport", "target": ("flight", i, field), "codes": sug, "name": raw,
                              "place_kind": "city", "suggest": True})
        _ask_pending(turn)
        return
    turn.intent = "clarify_place"
    turn.errors.append(turn.tr("unknown_place", place=raw))
    flight_next(turn)


def _what_for(turn, place):
    turn.intent = "clarify_place"
    name = place.name
    turn.body.append(turn.tr("what_for", place=name))
    turn.qr(turn.tr("qr_flights_to", place=name), f"Flights to {name}")
    if providers.HOTELS.city_for_codes(place.codes):
        turn.qr(turn.tr("qr_hotels_in", place=name), f"Hotels in {name}")
    if providers.ITINERARIES.match([place], name):
        turn.qr(turn.tr("qr_plan_for", place=name), f"Plan a trip to {name}")


# --------------------------------------------------------------------- info / RAG
def _info(turn, u):
    state = turn.state
    intent = u["intent"] if u["intent"] in RAG_INTENTS else "knowledge_query"
    turn.intent = intent
    turn.ask_feedback = True
    low = u["low"]
    if "visa" in low or "ವೀಸಾ" in low or "वीज़ा" in low or "वीजा" in low:
        codes = _trip_codes(state) + [c for p in u["places"] for c in p.codes]
        if codes and all(L.is_domestic(c) for c in codes):
            turn.body.append(turn.tr("visa_domestic"))
            _resume(turn)
            return
    t0 = time.perf_counter()
    res = rag_engine.answer(turn.text, intent if intent != "knowledge_query" else None, lang=state["lang"])
    turn.timings["rag_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if res.get("used"):
        turn.source = "rag"
        turn.rag = res
        answer = res["answer"]
        if state["lang"] != "en" and not res.get("localized"):
            translated = llm.translate(answer, state["lang"]) if _llm_ok() else None
            if translated:
                answer = translated
            else:
                answer = turn.tr("english_only") + "\n" + answer
        turn.body.append(answer)
    else:
        turn.body.append(turn.tr("domain_fallback"))
        _starter_quick(turn)
    _resume(turn)


def _resume(turn):
    """After a side question, repeat the open booking question (if any)."""
    if turn.state.get("asked") and turn.state.get("mode"):
        _continue_mode(turn)


def _trip_codes(state) -> list[str]:
    F = state["flight"]
    out = []
    for lg in F["legs"]:
        for k in ("origin", "destination"):
            if lg[k]:
                out.append(lg[k]["code"])
    return out


# --------------------------------------------------------------------- pending clarifications
def _push_pending(state, item):
    state["pending"].append(item)


def _other_intent(u) -> bool:
    """Is the user clearly doing something else instead of answering?"""
    return bool(u["info"] or u["cmd_plan"] or u["cmd_checkout"] or u["cmd_review"] or u["cmd_simulate"]
                or (u["intent"] in SOCIAL | RAG_INTENTS and u["conf"] >= 0.5))


def _resolve_pending(turn: Turn, u: dict) -> bool:
    state = turn.state
    p = state["pending"][0]
    kind = p["kind"]
    low = u["low"]
    if _other_intent(u) or u["domain_hotel"]:
        return False  # answer that first; the open question is repeated afterwards

    if kind == "airport":
        chosen = None
        short = len(u["text"].split()) <= 4
        roled = any(pl.extra.get("role") in ("origin", "destination") for pl in u["places"])
        if roled or len(u["places"]) >= 2:
            # the user restated the route: drop stale questions and re-read it
            state["pending"] = [q for q in state["pending"] if q["kind"] != "airport"]
            return False
        for pl in u["places"]:
            inter = [c for c in pl.codes if c in p["codes"]]
            if len(inter) == 1:
                chosen = inter[0]
                break
            if short and len(pl.codes) == 1:
                chosen = pl.codes[0]  # a bare answer naming another airport: accept it
                break
        if not chosen and u["ordinal"] and 1 <= u["ordinal"] <= len(p["codes"]):
            chosen = p["codes"][u["ordinal"] - 1]
        if not chosen and not u["places"]:
            sug = [c for c in L.suggest(u["text"]) if c in p["codes"]]
            if len(sug) == 1:
                chosen = sug[0]  # a close spelling of one of the offered airports
        if not chosen:
            if N.has_booking_entities(u) and not u["places"]:
                return False  # e.g. "2 adults" - apply it, then ask again
            _ask_pending(turn, prefix=turn.tr("didnt_get"))
            return True
        state["pending"].pop(0)
        _set_target(turn, p["target"], L.airport(chosen))
        _after_pending(turn, u, consumed_places=True)
        return True

    if kind == "role":
        role = None
        if re.search(r"\b(from|origin|departure|leaving|se)\b|ನಿಂದ|ಇಂದ|से", low):
            role = "origin"
        elif re.search(r"\b(to|destination|going|arriv\w*)\b|ಗೆ|तक|को", low):
            role = "destination"
        roled = [pl for pl in u["places"] if pl.extra.get("role") in ("origin", "destination")]
        if roled:
            state["pending"].pop(0)
            return False  # a fuller answer: normal flow applies it
        if not role:
            _ask_pending(turn, prefix=turn.tr("didnt_get"))
            return True
        state["pending"].pop(0)
        place = L.Place(p["name"], 0, 0, p["codes"], p.get("place_kind", "city"), p["name"])
        place.extra["role"] = role
        u2 = N.extract("", turn.today)
        u2["places"] = [place]
        _enter(state, "flight")
        flight_step(turn, u2)
        return True

    if kind == "family":
        pax = u["pax"]
        if pax["adults"] is None and pax["children"] is None and pax["infants"] is None:
            _ask_pending(turn, prefix=turn.tr("didnt_get"))
            return True
        state["pending"].pop(0)
        _enter(state, p.get("mode", "flight"))
        if state["mode"] == "hotel":
            hotel_step(turn, u)
        else:
            flight_step(turn, u)
        return True

    if kind == "date_which":
        which = None
        if re.search(r"\b(return|back|coming back)\b|ವಾಪಸ್|ಹಿಂತಿರುಗ|वापसी", low):
            which = "return"
        elif re.search(r"\b(depart\w*|outbound|going|leav\w*|onward)\b|ಹೊರಡುವ|जाने", low):
            which = "depart"
        if not which:
            if N.has_booking_entities(u):
                state["pending"].pop(0)
                return False
            _ask_pending(turn, prefix=turn.tr("didnt_get"))
            return True
        state["pending"].pop(0)
        F = state["flight"]
        if which == "return":
            _set_return(turn, p["iso"])
        else:
            _set_leg_date(turn, 0, p["iso"])
        _flight_validate(turn)
        flight_next(turn)
        return True

    state["pending"].pop(0)
    return False


def _after_pending(turn, u, consumed_places=False):
    state = turn.state
    mode = state.get("mode")
    if consumed_places:
        u = dict(u)
        u["places"] = []
    if state["pending"]:
        _ask_pending(turn)
        return
    if mode == "flight":
        if N.has_booking_entities(u):
            flight_step(turn, u)
        else:
            _flight_validate(turn)
            flight_next(turn)
    elif mode == "hotel":
        hotel_next(turn)
    elif mode == "plan":
        plan_step(turn, u)


def _ask_pending(turn, prefix: str | None = None):
    state = turn.state
    p = state["pending"][0]
    msg = ""
    if p["kind"] == "airport":
        key = {"city": "ask_airport_choice", "state": "ask_state_airport", "country": "ask_country_airport"}.get(p.get("place_kind"), "ask_airport_choice")
        if p.get("note") == "gateway":
            key = "ask_state_gateway"
        if p.get("suggest"):
            key = "did_you_mean"
        msg = turn.tr(key, place=p["name"])
        for c in p["codes"]:
            ap = L.airport(c)
            turn.qr(f"{ap['city']} ({c}) · {ap['name']}", c)
        turn.hint = {"kind": "location"}
    elif p["kind"] == "role":
        msg = turn.tr("ask_role", place=p["name"])
        turn.qr(turn.tr("qr_flying_from", place=p["name"]), f"from {p['name']}")
        turn.qr(turn.tr("qr_flying_to", place=p["name"]), f"to {p['name']}")
    elif p["kind"] == "family":
        msg = turn.tr("ask_family", n=p["n"])
        n = p["n"]
        for a, c in ((2, n - 2), (n, 0), (1, n - 1)):
            if a >= 1 and c >= 0 and a + c == n:
                label = pax_text(state, a, c)
                value = f"{a} adults {c} children" if c else f"{a} adults"
                turn.qr(label, value)
    elif p["kind"] == "date_which":
        msg = turn.tr("ask_date_which", date=fdate(state, p["iso"]))
        turn.qr(turn.tr("qr_departure"), "departure")
        turn.qr(turn.tr("qr_return"), "return")
    state["asked"] = "pending"
    turn.body.append((prefix + " " if prefix else "") + msg)


def _set_target(turn, target, loc):
    state = turn.state
    if target[0] == "flight":
        _, i, field = target
        _set_leg_place(turn, i, field, loc)
    elif target[0] == "hotel":
        pass


# --------------------------------------------------------------------- FLIGHT
def _set_leg_place(turn, i, field, loc):
    F = turn.state["flight"]
    while len(F["legs"]) <= i:
        F["legs"].append(_leg())
    old = F["legs"][i][field]
    if old and old["code"] == loc["code"]:
        return
    other = F["legs"][i]["destination" if field == "origin" else "origin"]
    if other and other["code"] == loc["code"]:
        turn.errors.append(turn.tr("same_airport", code=loc["code"]))
        return
    F["legs"][i][field] = loc
    turn.flight_changed = True
    turn.changed.add(("leg", i, field))


def _date_error(turn, h):
    if h.error == "past":
        turn.errors.append(turn.tr("date_past", today=fdate(turn.state, turn.today.isoformat())))
    elif h.error == "too_far":
        turn.errors.append(turn.tr("date_too_far"))
    else:
        turn.errors.append(turn.tr("date_invalid"))


def _set_leg_date(turn, i, iso):
    F = turn.state["flight"]
    if F["legs"][i]["date"] == iso:
        return
    if F["trip_type"] == "multi_city":
        prev = F["legs"][i - 1]["date"] if i > 0 else None
        if prev and iso < prev:
            turn.errors.append(turn.tr("leg_order", n=i + 1, prev=i, date=fdate(turn.state, prev)))
            return
    elif i == 0 and F["return_date"] and iso >= F["return_date"]:
        F["return_date"] = None
        turn.notes.append(turn.tr("note_return_cleared"))
    F["legs"][i]["date"] = iso
    turn.flight_changed = True
    turn.changed.add(("leg", i, "date"))


def _set_return(turn, iso):
    F = turn.state["flight"]
    if F["trip_type"] != "round_trip":
        if F["trip_type"] == "one_way":
            turn.notes.append(turn.tr("note_switched_round"))
        turn.changed.add(("trip",))
        F["trip_type"] = "round_trip"
    if F["return_date"] == iso:
        return
    dep = F["legs"][0]["date"]
    if dep and iso <= dep:
        turn.errors.append(turn.tr("return_before_depart", date=fdate(turn.state, dep)))
        return
    F["return_date"] = iso
    turn.flight_changed = True
    turn.changed.add(("return",))


def _queue_place(turn, place: L.Place, target):
    """Resolve a place mention into a slot, or queue a clarification."""
    state = turn.state
    if place.kind == "country" and not place.codes:
        turn.errors.append(turn.tr("ask_city_in_country", place=place.name))
        return
    if len(place.codes) == 1:
        _set_target(turn, target, L.airport(place.codes[0]))
        return
    _push_pending(state, {"kind": "airport", "target": target, "codes": place.codes[:6], "name": place.name,
                          "place_kind": place.kind, "note": place.note})


def _leg_segments(u) -> list[dict]:
    """Group places into (origin, destination) pairs; attach the date that follows each pair."""
    pairs: list[dict] = []
    cur: dict | None = None
    for p in u["places"]:
        role = p.extra.get("role")
        if role == "origin" or (role is None and (cur is None or cur.get("destination"))):
            cur = {"origin": p, "destination": None, "end": p.end}
            pairs.append(cur)
        else:
            if cur is None or cur.get("destination"):
                cur = {"origin": None, "destination": p, "end": p.end}
                pairs.append(cur)
            else:
                cur["destination"] = p
                cur["end"] = p.end
    for d in u["dates"]:
        owner = None
        for pr in pairs:
            if pr["end"] <= d.start:
                owner = pr
        if owner is not None and "date" not in owner:
            owner["date"] = d
    return pairs


def _target_leg(F) -> int:
    for i, lg in enumerate(F["legs"]):
        if not (lg["origin"] and lg["destination"] and lg["date"]):
            return i
    return len(F["legs"]) - 1


def _leg_ref(low: str) -> int | None:
    m = re.search(r"\b(?:flight|leg|segment)\s*(?:no\.?|number|#)?\s*(\d)\b", low)
    if m:
        return int(m.group(1)) - 1
    for w, n in N.ORDINALS.items():
        if n > 0 and re.search(rf"\b{re.escape(w)}\s+(?:flight|leg|segment)\b", low):
            return n - 1
    return None


def flight_step(turn: Turn, u: dict) -> None:
    state = turn.state
    F = state["flight"]
    turn.intent = "flight_search"
    low = u["low"]

    # ---- trip type
    tt = u["trip_type"]
    if tt and tt != F["trip_type"]:
        old = F["trip_type"]
        F["trip_type"] = tt
        turn.flight_changed = True
        turn.changed.add(("trip",))
        if old == "round_trip" and tt != "round_trip" and F["return_date"]:
            F["return_date"] = None
            turn.notes.append(turn.tr("note_return_removed"))
        if tt == "multi_city":
            F["mc_done"] = False
        elif len(F["legs"]) > 1:
            F["legs"] = F["legs"][:1]

    # ---- multi-city editing commands
    ref = _leg_ref(low)
    if F["trip_type"] == "multi_city" and u["cmd_remove"] and ref is not None:
        if 0 <= ref < len(F["legs"]) and len(F["legs"]) > 1:
            F["legs"].pop(ref)
            F["mc_done"] = False
            turn.flight_changed = True
            turn.notes.append(turn.tr("leg_removed", n=ref + 1))
        u = dict(u, places=[], dates=[])
    if F["trip_type"] == "multi_city" and state.get("asked") == "mc_more":
        if u["cmd_search"] or (u["no"] and not u["places"]):
            if len([lg for lg in F["legs"] if lg["origin"] and lg["destination"] and lg["date"]]) >= 2:
                F["mc_done"] = True
        elif (u["yes"] or u["cmd_add_leg"]) and not u["places"]:
            if len(F["legs"]) >= MAX_LEGS:
                turn.errors.append(turn.tr("mc_max", n=MAX_LEGS))
            else:
                F["legs"].append(_leg())
                F["mc_done"] = False

    # ---- passengers / cabin
    pax = u["pax"]
    if pax["family"] and pax["adults"] is None:
        _push_pending(state, {"kind": "family", "n": pax["family"], "mode": "flight"})
    else:
        _apply_pax(turn, F, pax)
    if u["cabin"] and u["cabin"] != F["cabin"]:
        F["cabin"] = u["cabin"]
        turn.flight_changed = True
        turn.changed.add(("cabin",))

    # ---- places
    places = u["places"]
    segments = _leg_segments(u) if places else []
    full_pairs = [s for s in segments if s["origin"] and s["destination"]]
    used_dates = set()
    if len(full_pairs) >= 2 and len(segments) == len(full_pairs):
        if F["trip_type"] != "multi_city":
            F["trip_type"] = "multi_city"
            turn.changed.add(("trip",))
        adding = u["cmd_add_leg"] or bool(re.search(r"\b(also|then\s+add|plus)\b", low))
        start = _target_leg(F) if (adding and any(lg["origin"] for lg in F["legs"])) else 0
        F["legs"] = F["legs"][:start]
        for k, sg in enumerate(segments[:MAX_LEGS]):
            i = start + k
            F["legs"].append(_leg())
            _queue_place(turn, sg["origin"], ("flight", i, "origin"))
            _queue_place(turn, sg["destination"], ("flight", i, "destination"))
            if sg.get("date") is not None:
                used_dates.add(id(sg["date"]))
                if sg["date"].error:
                    _date_error(turn, sg["date"])
                else:
                    _set_leg_date(turn, i, sg["date"].iso)
        F["mc_done"] = False
        turn.flight_changed = True
    else:
        i = ref if (ref is not None and F["trip_type"] == "multi_city" and ref < len(F["legs"])) else (
            _target_leg(F) if F["trip_type"] == "multi_city" else 0)
        leg = F["legs"][i]
        for p in places:
            role = p.extra.get("role")
            if role == "at":
                role = "destination"
            if role is None:
                asked = state.get("asked") or ""
                if asked in ("origin", "destination"):
                    role = asked
                elif asked.startswith("leg_"):
                    role = "origin" if not leg["origin"] else "destination"
                elif leg["origin"] and not leg["destination"]:
                    role = "destination"
                elif leg["destination"] and not leg["origin"]:
                    role = "origin"
                elif F["trip_type"] == "multi_city" and i > 0 and not leg["destination"]:
                    role = "destination"
                else:
                    _push_pending(state, {"kind": "role", "codes": p.codes, "name": p.name, "place_kind": p.kind})
                    continue
            _queue_place(turn, p, ("flight", i, role))

    # ---- "from Xyz" / "to Xyz" where Xyz is not a known place
    for field, raw in _unmatched_phrases(u):
        i = _target_leg(F) if F["trip_type"] == "multi_city" else 0
        sug = L.suggest(raw)
        if sug:
            _push_pending(state, {"kind": "airport", "target": ("flight", i, field), "codes": sug, "name": raw,
                                  "place_kind": "city", "suggest": True})
        else:
            turn.errors.append(turn.tr("unknown_place", place=raw))

    # ---- dates
    rest = [d for d in u["dates"] if id(d) not in used_dates]
    if rest:
        _apply_flight_dates(turn, F, rest, u, ref)

    _flight_validate(turn)
    if turn.flight_changed:
        _invalidate_flights(state)
    flight_next(turn)


def _apply_pax(turn, F, pax):
    changed = False
    for key in ("adults", "children", "infants"):
        if pax[key] is not None and pax[key] != F[key]:
            F[key] = pax[key]
            changed = True
    if not changed:
        return
    a, c, i = F["adults"] or 0, F["children"] or 0, F["infants"] or 0
    if F["adults"] is not None and (a < 1 or a + c > MAX_PAX):
        turn.errors.append(turn.tr("pax_invalid", max=MAX_PAX))
        F["adults"] = None
        return
    if i > a and F["adults"] is not None:
        turn.errors.append(turn.tr("pax_infants"))
        F["infants"] = a
    turn.flight_changed = True
    if F["adults"]:
        turn.changed.add(("pax",))


def _apply_flight_dates(turn, F, hits, u, ref):
    state = turn.state
    asked = state.get("asked") or ""
    unl = [h for h in hits if not getattr(h, "role", None) or h.role == "leave"]
    for h in hits:
        if h.error:
            _date_error(turn, h)
    ok = [h for h in hits if not h.error]
    if F["trip_type"] == "multi_city":
        for h in ok:
            i = ref if ref is not None and ref < len(F["legs"]) else (
                int(asked.split(":")[1]) if asked.startswith("leg_") and ":" in asked else _target_leg(F))
            _set_leg_date(turn, i, h.iso)
        return
    roles = {id(h): getattr(h, "role", None) for h in ok}
    unlabeled = [h for h in ok if roles[id(h)] in (None, "leave", "checkin", "checkout")]
    for h in ok:
        if roles[id(h)] == "return":
            _set_return(turn, h.iso)
        elif roles[id(h)] == "depart":
            _set_leg_date(turn, 0, h.iso)
    if not unlabeled:
        return
    if len(unlabeled) >= 2:
        _set_leg_date(turn, 0, unlabeled[0].iso)
        if F["trip_type"] in (None, "round_trip"):
            if F["trip_type"] is None:
                F["trip_type"] = "round_trip"
                turn.changed.add(("trip",))
            _set_return(turn, unlabeled[1].iso)
        return
    h = unlabeled[0]
    if roles[id(h)] == "leave":
        _set_leg_date(turn, 0, h.iso)
    elif asked == "return":
        _set_return(turn, h.iso)
    elif asked == "depart" or not F["legs"][0]["date"]:
        _set_leg_date(turn, 0, h.iso)
    elif F["trip_type"] == "round_trip" and not F["return_date"]:
        _set_return(turn, h.iso)
    elif F["trip_type"] == "round_trip":
        _push_pending(state, {"kind": "date_which", "iso": h.iso})
    else:
        _set_leg_date(turn, 0, h.iso)


def _flight_validate(turn):
    F = turn.state["flight"]
    dep = F["legs"][0]["date"]
    if F["trip_type"] == "round_trip" and dep and F["return_date"] and F["return_date"] <= dep:
        turn.errors.append(turn.tr("return_before_depart", date=fdate(turn.state, dep)))
        F["return_date"] = None
    if F["trip_type"] == "multi_city":
        for i in range(1, len(F["legs"])):
            prev, cur = F["legs"][i - 1]["date"], F["legs"][i]["date"]
            if prev and cur and cur < prev:
                turn.errors.append(turn.tr("leg_order", n=i + 1, prev=i, date=fdate(turn.state, prev)))
                F["legs"][i]["date"] = None


def _invalidate_flights(state):
    state["results"]["flights"] = {}
    state["selection"]["flights"] = {}
    state["selection"]["seats"] = {}
    state["checkout"] = None


def flight_missing(F) -> list[str]:
    miss = []
    if not F["trip_type"]:
        miss.append("trip_type")
    if F["trip_type"] == "multi_city":
        for i, lg in enumerate(F["legs"]):
            if not lg["origin"] or not lg["destination"]:
                miss.append(f"leg_route:{i}")
            if not lg["date"]:
                miss.append(f"leg_date:{i}")
        complete = [lg for lg in F["legs"] if lg["origin"] and lg["destination"] and lg["date"]]
        if not miss and (len(complete) < 2 or not F["mc_done"]):
            miss.append("mc_more")
    else:
        lg = F["legs"][0]
        if not lg["origin"]:
            miss.append("origin")
        if not lg["destination"]:
            miss.append("destination")
        if not lg["date"]:
            miss.append("depart")
        if F["trip_type"] == "round_trip" and not F["return_date"]:
            miss.append("return")
    if not F["adults"]:
        miss.append("pax")
    if not F["cabin"]:
        miss.append("cabin")
    return miss


def flight_next(turn: Turn) -> None:
    state = turn.state
    F = state["flight"]
    turn.extra["missing"] = flight_missing(F)
    if state["pending"]:
        _ask_pending(turn)
        return
    miss = turn.extra["missing"]
    if not miss:
        if not state["results"]["flights"]:
            flight_search(turn)
        else:
            turn.body.append(turn.tr("flights_still_shown"))
        return
    nxt = miss[0]
    lg0 = F["legs"][0]
    q = ""
    if nxt == "trip_type":
        if lg0["origin"] and lg0["destination"]:
            q = turn.tr("ask_trip_type_route", route=f"{loc_label(lg0['origin'])} → {loc_label(lg0['destination'])}")
        else:
            q = turn.tr("ask_trip_type")
        turn.qr(turn.tr("qr_one_way"), "one way")
        turn.qr(turn.tr("qr_round_trip"), "round trip")
        turn.qr(turn.tr("qr_multi_city"), "multi city")
    elif nxt == "origin":
        q = turn.tr("ask_origin_dest", dest=loc_label(lg0["destination"])) if lg0["destination"] else turn.tr("ask_origin")
        turn.hint = {"kind": "location"}
    elif nxt == "destination":
        q = turn.tr("ask_destination_from", origin=loc_label(lg0["origin"])) if lg0["origin"] else turn.tr("ask_destination")
        turn.hint = {"kind": "location"}
    elif nxt == "depart":
        q = turn.tr("ask_depart", route=f"{loc_label(lg0['origin'])} → {loc_label(lg0['destination'])}")
        turn.hint = {"kind": "date", "field": "depart", "min": turn.today.isoformat()}
    elif nxt == "return":
        q = turn.tr("ask_return", date=fdate(state, lg0["date"]))
        turn.hint = {"kind": "date", "field": "return", "min": D.add_days(lg0["date"], 1)}
    elif nxt.startswith("leg_route"):
        i = int(nxt.split(":")[1])
        lg = F["legs"][i]
        if i > 0 and not lg["origin"] and F["legs"][i - 1]["destination"] and not lg["destination"]:
            q = turn.tr("mc_ask_next_dest", n=i + 1, origin=loc_label(F["legs"][i - 1]["destination"]))
            # a destination-only answer continues from where the previous flight lands
            lg["origin"] = F["legs"][i - 1]["destination"]
        elif lg["origin"] and not lg["destination"]:
            q = turn.tr("mc_ask_leg_dest", n=i + 1, origin=loc_label(lg["origin"]))
        elif i == 0 and not lg["origin"] and not lg["destination"]:
            q = turn.tr("mc_intro")
        else:
            q = turn.tr("mc_ask_leg_route", n=i + 1)
        turn.hint = {"kind": "location"}
        nxt = f"leg_route:{i}"
    elif nxt.startswith("leg_date"):
        i = int(nxt.split(":")[1])
        lg = F["legs"][i]
        q = turn.tr("mc_ask_leg_date", n=i + 1, route=f"{loc_label(lg['origin'])} → {loc_label(lg['destination'])}")
        mn = F["legs"][i - 1]["date"] if i > 0 and F["legs"][i - 1]["date"] else turn.today.isoformat()
        turn.hint = {"kind": "date", "field": f"leg{i}", "min": mn}
    elif nxt == "mc_more":
        n = len(F["legs"])
        if n < 2:
            F["legs"].append(_leg())
            return flight_next(turn)
        q = turn.tr("mc_more", n=n)
        if n < MAX_LEGS:
            turn.qr(turn.tr("qr_add_flight"), "add another flight")
        turn.qr(turn.tr("qr_search_flights"), "search flights")
    elif nxt == "pax":
        if not F["cabin"]:
            q = turn.tr("ask_pax_cabin")
            turn.qr(pax_text(state, 1) + " · " + cabin_text(state, "Economy"), "1 adult economy")
            turn.qr(pax_text(state, 2) + " · " + cabin_text(state, "Economy"), "2 adults economy")
            turn.qr(pax_text(state, 2, 1) + " · " + cabin_text(state, "Economy"), "2 adults 1 child economy")
            turn.qr(pax_text(state, 1) + " · " + cabin_text(state, "Business"), "1 adult business")
        else:
            q = turn.tr("ask_pax")
            for a, c, i_ in ((1, 0, 0), (2, 0, 0), (2, 1, 0), (2, 1, 1)):
                turn.qr(pax_text(state, a, c, i_), f"{a} adults {c} children {i_} infants")
    elif nxt == "cabin":
        q = turn.tr("ask_cabin")
        for cab, val in (("Economy", "economy"), ("Premium Economy", "premium economy"), ("Business", "business"), ("First", "first class")):
            turn.qr(cabin_text(state, cab), val)
    state["asked"] = nxt
    turn.body.append(q)


def flight_search(turn: Turn) -> None:
    state = turn.state
    F = state["flight"]
    t0 = time.perf_counter()
    legs = []
    if F["trip_type"] == "multi_city":
        legs = [(lg["origin"], lg["destination"], lg["date"]) for lg in F["legs"]]
    else:
        lg = F["legs"][0]
        legs = [(lg["origin"], lg["destination"], lg["date"])]
        if F["trip_type"] == "round_trip":
            legs.append((lg["destination"], lg["origin"], F["return_date"]))
    block_legs = []
    results = {}
    for i, (o, d, dt) in enumerate(legs):
        opts = providers.FLIGHTS.search_leg(o["code"], d["code"], dt, F["cabin"], leg=i)
        for op in opts:  # price for THIS party, shown on the card (same rule as price_summary)
            op["total_for_pax"] = (F["adults"] * op["fare_adult"] + (F["children"] or 0) * op["fare_child"]
                                   + (F["infants"] or 0) * op["fare_infant"])
        results[str(i)] = opts
        title_key = "leg_title_return" if (F["trip_type"] == "round_trip" and i == 1) else (
            "leg_title_outbound" if F["trip_type"] == "round_trip" else "leg_title_n" if F["trip_type"] == "multi_city" else "leg_title_one")
        block_legs.append({"leg": i, "title": turn.tr(title_key, n=i + 1), "route": f"{loc_label(o)} → {loc_label(d)}",
                           "date": dt, "date_label": fdate(state, dt), "options": opts})
    turn.timings["mock_search_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    state["results"]["flights"] = results
    state["selection"]["flights"] = {}
    state["asked"] = "select_flight"
    state["last_shown"] = "flights"
    if not any(results.values()):
        turn.body.append(turn.tr("no_sample_flights"))
        return
    pax = pax_text(state, F["adults"], F["children"], F["infants"])
    key = {"one_way": "flights_found_one", "round_trip": "flights_found_round", "multi_city": "flights_found_multi"}[F["trip_type"]]
    turn.body.append(turn.tr(key, n=len(legs), pax=pax, cabin=cabin_text(state, F["cabin"])))
    turn.blocks.append({"type": "flights", "legs": block_legs,
                        "pax": {"adults": F["adults"], "children": F["children"], "infants": F["infants"]}})
    turn.ask_feedback = True


def _find_option(state, leg: int | None, option_id: str | None = None, flight_no: str | None = None, ordinal: int | None = None,
                 cheapest=False, fastest=False):
    res = state["results"]["flights"]
    legs = [str(leg)] if leg is not None else [k for k in sorted(res) if int(k) not in state["selection"]["flights"]] or sorted(res)
    for k in legs:
        opts = res.get(k) or []
        for o in opts:
            if option_id and o["id"] == option_id:
                return o
            if flight_no and o["flight_no"].replace(" ", "").upper() == flight_no.replace(" ", "").upper():
                return o
        if opts and ordinal:
            idx = ordinal - 1 if ordinal > 0 else len(opts) - 1
            if 0 <= idx < len(opts):
                return opts[idx]
        if opts and cheapest:
            return min(opts, key=lambda o: o["fare_adult"])
        if opts and fastest:
            return min(opts, key=lambda o: o["duration_min"])
    return None


def select_flight(turn, option) -> None:
    state = turn.state
    turn.intent = "select_flight"
    state["selection"]["flights"][option["leg"]] = option
    state["selection"]["seats"].pop(option["leg"], None)
    state["checkout"] = None
    turn.body.append(turn.tr("flight_selected", flight=f"{option['airline']} {option['flight_no']}",
                             route=f"{option['origin']} → {option['destination']}"))
    remaining = [int(k) for k in state["results"]["flights"] if int(k) not in state["selection"]["flights"]]
    turn.extra["selected_flight"] = option
    if remaining:
        F = state["flight"]
        nxt = min(remaining)
        key = "pick_return" if F["trip_type"] == "round_trip" else "pick_leg"
        turn.body.append(turn.tr(key, n=nxt + 1))
        state["asked"] = "select_flight"
        return
    state["asked"] = None
    _after_flights_quick(turn)


def _dest_hotel_city(state):
    F = state["flight"]
    if F["trip_type"] == "multi_city":
        lg = F["legs"][0]
    else:
        lg = F["legs"][0]
    if lg["destination"]:
        return providers.HOTELS.city_for_codes([lg["destination"]["code"]])
    return None


def _after_flights_quick(turn):
    state = turn.state
    city = _dest_hotel_city(state)
    if city and not state["selection"]["hotel"]:
        name = providers.HOTELS.cities[city]["name"]
        turn.body.append(turn.tr("offer_hotel", city=name))
        turn.qr(turn.tr("qr_hotels_in", place=name), "add a hotel")
    turn.qr(turn.tr("qr_review"), "review my trip")
    turn.qr(turn.tr("qr_seats"), "choose seats")
    turn.qr(turn.tr("qr_simulate"), "simulate flight update")


# --------------------------------------------------------------------- HOTEL
def _prefill_hotel(state) -> list[str]:
    """Use flight context for the hotel search; return what was prefilled."""
    H, F = state["hotel"], state["flight"]
    filled = []
    if not H["city"]:
        city = _dest_hotel_city(state)
        if city:
            H["city"] = city
            filled.append("city")
    sel = state["selection"]["flights"]
    lg0 = F["legs"][0]
    if not H["checkin"] and lg0["date"] and H["city"] == _dest_hotel_city(state):
        arr = lg0["date"]
        if 0 in sel and sel[0].get("arrive_day_offset"):
            arr = D.add_days(arr, sel[0]["arrive_day_offset"])
        H["checkin"] = arr
        filled.append("checkin")
        nxt = F["return_date"] if F["trip_type"] == "round_trip" else (
            F["legs"][1]["date"] if F["trip_type"] == "multi_city" and len(F["legs"]) > 1 else None)
        if nxt and not H["checkout"] and nxt > arr:
            H["checkout"] = nxt
            filled.append("checkout")
    if H["adults"] is None and F["adults"]:
        H["adults"], H["children"] = F["adults"], F["children"] or 0
        filled.append("guests")
    return filled


def hotel_step(turn: Turn, u: dict) -> None:
    state = turn.state
    H = state["hotel"]
    turn.intent = "hotel_search"
    changed = False

    for p in u["places"]:
        if p.extra.get("role") == "origin":
            continue
        cid = providers.HOTELS.city_for_codes(p.codes)
        if cid:
            if H["city"] != cid:
                H["city"] = cid
                H["unsupported"] = None
                changed = True
                turn.changed.add(("hotel_city",))
        else:
            H["unsupported"] = p.name
            turn.errors.append(turn.tr("hotel_city_unsupported", city=p.name,
                                       list=", ".join(providers.HOTELS.supported())))
        break
    prefilled = _prefill_hotel(state) if not (H["checkin"] or H["checkout"] or u["dates"]) else []

    for h in u["dates"]:
        if h.error:
            _date_error(turn, h)
    ok = [h for h in u["dates"] if not h.error]
    asked = state.get("asked")
    unl = []
    for h in ok:
        role = getattr(h, "role", None)
        if role in ("checkin", "depart"):
            H["checkin"] = h.iso
        elif role in ("checkout", "return"):
            H["checkout"] = h.iso
        elif role == "leave" and (H["checkin"] or any(getattr(x, "role", None) in ("checkin", "depart") for x in ok)):
            H["checkout"] = h.iso
        else:
            unl.append(h)
    if len(unl) >= 2:
        H["checkin"], H["checkout"] = unl[0].iso, unl[1].iso
    elif unl:
        if asked == "checkout" or (H["checkin"] and not H["checkout"] and asked != "checkin"):
            H["checkout"] = unl[0].iso
        else:
            H["checkin"] = unl[0].iso
    if ok:
        changed = True
        turn.changed.update({("checkin",), ("checkout",)})
    dur = u["duration"]
    if dur:
        n = dur[0] if dur[1] == "night" else max(1, dur[0] - 1)
        H["nights_hint"] = n
        if H["checkin"]:
            H["checkout"] = D.add_days(H["checkin"], n)
        changed = True
    elif H["nights_hint"] and H["checkin"] and not H["checkout"]:
        H["checkout"] = D.add_days(H["checkin"], H["nights_hint"])

    pax = u["pax"]
    if pax["family"] and pax["adults"] is None:
        _push_pending(state, {"kind": "family", "n": pax["family"], "mode": "hotel"})
    else:
        if pax["adults"] is not None:
            H["adults"] = pax["adults"]
            changed = True
        if pax["children"] is not None:
            H["children"] = pax["children"]
            changed = True
    if u["rooms"]:
        H["rooms"] = u["rooms"]
        changed = True

    if H["checkin"] and H["checkout"]:
        n = D.nights_between(H["checkin"], H["checkout"])
        if n <= 0:
            turn.errors.append(turn.tr("checkout_before", date=fdate(state, H["checkin"])))
            H["checkout"] = None
        elif n > MAX_NIGHTS:
            turn.errors.append(turn.tr("too_many_nights", n=MAX_NIGHTS))
            H["checkout"] = None
    if changed or prefilled:
        state["results"]["hotels"] = []
        state["selection"]["hotel"] = None
        state["checkout"] = None
    if prefilled and H["city"] and ("checkin" in prefilled or "guests" in prefilled):
        turn.notes.append(turn.tr("note_prefilled"))
    hotel_next(turn)


def hotel_missing(H) -> list[str]:
    miss = []
    if not H["city"]:
        miss.append("hotel_city")
    if not H["checkin"]:
        miss.append("checkin")
    if not H["checkout"]:
        miss.append("checkout")
    if not H["adults"]:
        miss.append("guests")
    return miss


def hotel_next(turn: Turn) -> None:
    state = turn.state
    H = state["hotel"]
    if state["pending"]:
        _ask_pending(turn)
        return
    miss = hotel_missing(H)
    turn.extra["missing"] = miss
    if not miss:
        if not state["results"]["hotels"]:
            hotel_search(turn)
        else:
            turn.body.append(turn.tr("hotels_still_shown"))
        return
    nxt = miss[0]
    if nxt == "hotel_city":
        q = turn.tr("ask_hotel_city")
        for cid in ("goa", "jaipur", "bengaluru", "dubai", "singapore"):
            name = providers.HOTELS.cities[cid]["name"]
            turn.qr(name, f"hotel in {name}")
    elif nxt == "checkin":
        q = turn.tr("ask_checkin", city=providers.HOTELS.cities[H["city"]]["name"])
        turn.hint = {"kind": "date", "field": "checkin", "min": turn.today.isoformat()}
    elif nxt == "checkout":
        q = turn.tr("ask_checkout", date=fdate(state, H["checkin"]))
        turn.hint = {"kind": "date", "field": "checkout", "min": D.add_days(H["checkin"], 1)}
        for n in (2, 3, 5):
            turn.qr(turn.tr("n_nights", n=n), f"{n} nights")
    else:
        q = turn.tr("ask_guests")
        for a, c in ((1, 0), (2, 0), (2, 1), (2, 2)):
            turn.qr(pax_text(state, a, c), f"{a} adults {c} children")
    state["asked"] = nxt
    turn.body.append(q)


def _rooms(H) -> int:
    return H["rooms"] or max(1, math.ceil((H["adults"] or 1) / 2))


def hotel_search(turn: Turn) -> None:
    state = turn.state
    H = state["hotel"]
    hotels = providers.HOTELS.hotels_for(H["city"])
    nights = D.nights_between(H["checkin"], H["checkout"])
    rooms = _rooms(H)
    for h in hotels:
        h["nights"], h["rooms"] = nights, rooms
        h["stay_total"] = h["price_per_night"] * nights * rooms
    state["results"]["hotels"] = hotels
    state["asked"] = "select_hotel"
    state["last_shown"] = "hotels"
    name = providers.HOTELS.cities[H["city"]]["name"]
    turn.body.append(turn.tr("hotels_found", n=len(hotels), city=name, nights=nights, rooms=rooms,
                             checkin=fdate(state, H["checkin"]), checkout=fdate(state, H["checkout"]),
                             guests=pax_text(state, H["adults"], H["children"])))
    turn.blocks.append({"type": "hotels", "city": name, "nights": nights, "rooms": rooms,
                        "checkin": H["checkin"], "checkout": H["checkout"],
                        "checkin_label": fdate(state, H["checkin"]), "checkout_label": fdate(state, H["checkout"]),
                        "hotels": hotels})
    turn.ask_feedback = True


def select_hotel(turn, hotel) -> None:
    state = turn.state
    turn.intent = "select_hotel"
    state["selection"]["hotel"] = hotel
    state["checkout"] = None
    state["asked"] = None
    turn.body.append(turn.tr("hotel_selected", hotel=hotel["name"]))
    turn.qr(turn.tr("qr_review"), "review my trip")
    if not state["selection"]["flights"]:
        turn.qr(turn.tr("qr_book_flight"), "Book a flight")


# --------------------------------------------------------------------- REVIEW / CHECKOUT / ALERT / SEATS
def _summary(state) -> dict | None:
    F, H = state["flight"], state["hotel"]
    flights = [state["selection"]["flights"][k] for k in sorted(state["selection"]["flights"])]
    hotel = state["selection"]["hotel"]
    if not flights and not hotel:
        return None
    pax = {"adults": F["adults"] or 0, "children": F["children"] or 0, "infants": F["infants"] or 0}
    nights = D.nights_between(H["checkin"], H["checkout"]) if hotel and H["checkin"] and H["checkout"] else 0
    return providers.price_summary(pax, flights, hotel, nights, _rooms(H), state["selection"]["seats"])


def _localize_lines(state, summ):
    out = []
    for ln in summ["lines"]:
        item = dict(ln)
        if ln["kind"] == "flight":
            item["label"] = f"{ln['airline']} {ln['flight_no']} · {ln['origin']} → {ln['destination']} · {fdate(state, ln['date'])}"
            parts = [f"{ln['adults']} × {money(ln['fare_adult'])}"]
            if ln["children"]:
                parts.append(f"{ln['children']} × {money(ln['fare_child'])}")
            if ln["infants"]:
                parts.append(f"{ln['infants']} × {money(ln['fare_infant'])}")
            item["detail"] = " + ".join(parts)
        elif ln["kind"] == "hotel":
            item["label"] = f"{ln['name']}, {ln['city']}"
            item["detail"] = f"{money(ln['price_per_night'])} × {i18n.t('n_nights', state['lang'], n=ln['nights'])} × {i18n.t('n_rooms', state['lang'], n=ln['rooms'])}"
        else:
            item["label"] = i18n.t("seat_line", state["lang"], leg=ln["leg"] + 1)
            item["detail"] = ", ".join(ln["seats"])
        item["amount_label"] = money(ln["amount"])
        out.append(item)
    return out


def review(turn: Turn) -> None:
    state = turn.state
    turn.intent = "review"
    res = state["results"]["flights"]
    sel = state["selection"]["flights"]
    missing_legs = [int(k) + 1 for k in res if int(k) not in sel] if (res and sel) else []
    summ = _summary(state)
    if not summ:
        turn.body.append(turn.tr("review_nothing"))
        _starter_quick(turn)
        return
    if missing_legs:
        turn.body.append(turn.tr("review_missing_leg", n=missing_legs[0]))
        return
    turn.body.append(turn.tr("review_intro"))
    turn.blocks.append({"type": "review", "lines": _localize_lines(state, summ), "total": summ["total"],
                        "total_label": money(summ["total"]), "sample": True})
    state["asked"] = "review"
    turn.qr(turn.tr("qr_checkout"), "demo checkout")
    if not state["selection"]["hotel"] and _dest_hotel_city(state):
        turn.qr(turn.tr("qr_add_hotel"), "add a hotel")
    if state["selection"]["flights"]:
        turn.qr(turn.tr("qr_seats"), "choose seats")
        turn.qr(turn.tr("qr_simulate"), "simulate flight update")
    turn.ask_feedback = True


def checkout(turn: Turn) -> None:
    state = turn.state
    turn.intent = "demo_checkout"
    res = state["results"]["flights"]
    sel = state["selection"]["flights"]
    if res and sel and any(int(k) not in sel for k in res):
        return review(turn)
    summ = _summary(state)
    if not summ:
        turn.body.append(turn.tr("review_nothing"))
        _starter_quick(turn)
        return
    state["checkout"] = {"total": summ["total"], "at": turn.today.isoformat()}
    turn.body.append(turn.tr("checkout_done"))
    turn.blocks.append({"type": "checkout", "lines": _localize_lines(state, summ), "total": summ["total"],
                        "total_label": money(summ["total"]), "sample": True, "booked": False, "payment_taken": False})
    state["asked"] = None
    if state["selection"]["flights"]:
        turn.qr(turn.tr("qr_simulate"), "simulate flight update")
    turn.qr(turn.tr("qr_plan_trip"), "Plan a trip")
    turn.qr(turn.tr("qr_start_over"), "start over")
    turn.ask_feedback = True


def simulate_update(turn: Turn, leg: int | None = None) -> None:
    state = turn.state
    turn.intent = "simulated_update"
    sel = state["selection"]["flights"]
    if not sel:
        turn.body.append(turn.tr("alert_need_flight"))
        if state["results"]["flights"]:
            return
        turn.qr(turn.tr("qr_book_flight"), "Book a flight")
        return
    f = sel.get(leg) if leg is not None and leg in sel else sel[min(sel)]
    delay = 30
    h, m = map(int, f["depart"].split(":"))
    total = h * 60 + m + delay
    new = f"{(total // 60) % 24:02d}:{total % 60:02d}"
    turn.body.append(turn.tr("alert_text", flight=f"{f['airline']} {f['flight_no']}",
                             route=f"{f['origin']} → {f['destination']}", date=fdate(state, f["date"]),
                             old=f["depart"], new=new, mins=delay))
    turn.blocks.append({"type": "alert", "simulated": True, "live_feed": False, "flight_no": f["flight_no"],
                        "airline": f["airline"], "route": f"{f['origin']} → {f['destination']}", "date": f["date"],
                        "old": f["depart"], "new": new, "delay_min": delay})
    turn.ask_feedback = True


SEAT_RE = re.compile(r"^\d{1,2}[A-F]$")
SEAT_PRICES = {0, 600, 800}


def open_seats(turn: Turn, leg: int | None) -> None:
    state = turn.state
    sel = state["selection"]["flights"]
    if not sel:
        turn.body.append(turn.tr("alert_need_flight"))
        return
    leg = leg if leg in sel else min(sel)
    f = sel[leg]
    F = state["flight"]
    turn.intent = "seat_selection"
    turn.body.append(turn.tr("seats_open", flight=f"{f['airline']} {f['flight_no']}"))
    turn.extra["seat_params"] = {"leg": leg, "flight": f["flight_no"], "airline": f["airline"],
                                 "route": f"{f['origin']} → {f['destination']}", "date": fdate(state, f["date"]),
                                 "time": f"{f['depart']} – {f['arrive']}", "cabin": f["cabin"],
                                 "passengers": (F["adults"] or 1) + (F["children"] or 0), "lang": state["lang"]}
    turn.extra["show_seat_selection"] = True


def save_seats(turn: Turn, payload: dict) -> None:
    state = turn.state
    turn.intent = "seat_selection"
    try:
        leg = int(payload.get("leg", 0))
    except (TypeError, ValueError):
        leg = -1
    seats = payload.get("seats") or []
    F = state["flight"]
    need = (F["adults"] or 1) + (F["children"] or 0)
    ok = (leg in state["selection"]["flights"] and isinstance(seats, list) and 0 < len(seats) <= need
          and all(isinstance(s, dict) and SEAT_RE.match(str(s.get("seat", ""))) and int(s.get("price", -1)) in SEAT_PRICES for s in seats)
          and len({s["seat"] for s in seats}) == len(seats))
    if not ok:
        turn.body.append(turn.tr("seats_invalid"))
        return
    state["selection"]["seats"][leg] = [{"seat": s["seat"], "price": int(s["price"])} for s in seats]
    state["checkout"] = None
    turn.body.append(turn.tr("seats_saved", seats=", ".join(s["seat"] for s in seats)))
    turn.qr(turn.tr("qr_review"), "review my trip")


# --------------------------------------------------------------------- commands (text)
def _commands(turn: Turn, u: dict) -> bool:
    state = turn.state
    low = u["low"]
    res_f = state["results"]["flights"]
    res_h = state["results"]["hotels"]

    if u["cmd_checkout"] and (state["selection"]["flights"] or state["selection"]["hotel"]):
        checkout(turn)
        return True
    if u["cmd_simulate"] and not u["places"]:
        simulate_update(turn, _leg_ref(low))
        return True
    if u["cmd_seats"] and state["selection"]["flights"] and not u["places"]:
        open_seats(turn, _leg_ref(low))
        return True
    if u["cmd_review"] and not N.has_booking_entities(u):
        review(turn)
        return True
    # choosing a displayed option by flight number / ordinal / cheapest / fastest
    last = state.get("last_shown")
    if res_f and last == "flights" and not N.has_booking_entities(u):
        known = [o["flight_no"] for opts in res_f.values() for o in opts]
        fn = N.parse_flight_no(turn.text, known)
        cheapest = bool(re.search(r"\bcheap\w*|lowest|ಅಗ್ಗದ|सबसे\s+सस्ता", low))
        fastest = bool(re.search(r"\bfast\w*|quick\w*|shortest|non[\s-]?stop|direct", low))
        if fn or ((u["cmd_select"] or u["ordinal"]) and (u["ordinal"] or cheapest or fastest)) or (cheapest or fastest):
            opt = _find_option(state, None, flight_no=fn, ordinal=None if fn else u["ordinal"],
                               cheapest=cheapest and not fn, fastest=fastest and not fn and not cheapest)
            if opt:
                select_flight(turn, opt)
                return True
    if res_h and last == "hotels" and not N.has_booking_entities(u):
        pick = None
        for h in res_h:
            if h["name"].lower() in low:
                pick = h
        if not pick and u["ordinal"]:
            idx = u["ordinal"] - 1 if u["ordinal"] > 0 else len(res_h) - 1
            if 0 <= idx < len(res_h):
                pick = res_h[idx]
        if not pick and re.search(r"\bcheap\w*|lowest|budget", low):
            pick = min(res_h, key=lambda h: h["price_per_night"])
        if not pick and re.search(r"\bbest\s+rated|highest\s+rated|top\s+rated", low):
            pick = max(res_h, key=lambda h: h["rating"])
        if pick:
            select_hotel(turn, pick)
            return True
    if u["cmd_add_hotel"] and not u["dates"] and (state["selection"]["flights"] or state["flight"]["legs"][0]["destination"]):
        _enter(state, "hotel")
        hotel_step(turn, u)
        return True
    return False


# --------------------------------------------------------------------- button actions
def handle_action(turn: Turn, action: str, payload: dict) -> None:
    state = turn.state
    if action == "select_flight":
        opt = _find_option(state, payload.get("leg") if isinstance(payload.get("leg"), int) else None,
                           option_id=str(payload.get("id") or ""))
        if opt:
            select_flight(turn, opt)
        else:
            turn.intent = "select_flight"
            turn.body.append(turn.tr("option_gone"))
    elif action == "select_hotel":
        hid = str(payload.get("id") or "")
        pick = next((h for h in state["results"]["hotels"] if h["id"] == hid), None)
        if pick:
            select_hotel(turn, pick)
        else:
            turn.intent = "select_hotel"
            turn.body.append(turn.tr("option_gone"))
    elif action == "review":
        review(turn)
    elif action == "checkout":
        checkout(turn)
    elif action == "simulate_update":
        simulate_update(turn, payload.get("leg") if isinstance(payload.get("leg"), int) else None)
    elif action == "open_seats":
        open_seats(turn, payload.get("leg") if isinstance(payload.get("leg"), int) else None)
    elif action == "seats_selected":
        save_seats(turn, payload)
    elif action == "back_from_seat_selection":
        turn.intent = "seat_selection"
        turn.body.append(turn.tr("back_from_seats"))
        turn.qr(turn.tr("qr_review"), "review my trip")
        turn.qr(turn.tr("qr_seats"), "choose seats")
    elif action == "welcome":
        turn.intent = "welcome"
        turn.body.append(turn.tr("welcome"))
        _starter_quick(turn)
    elif action == "reset":
        _reset(state)
        turn.intent = "reset"
        turn.body.append(turn.tr("reset"))
        turn.extra["clear_results"] = True
        _starter_quick(turn)
    else:
        turn.intent = "unknown_action"
        turn.body.append(turn.tr("clarify"))


# --------------------------------------------------------------------- PLAN
def plan_step(turn: Turn, u: dict) -> None:
    state = turn.state
    P = state["plan"]
    turn.intent = "plan_trip"
    plans = providers.ITINERARIES.plans
    lang = state["lang"]

    pid = providers.ITINERARIES.match(u["places"], u["text"]) if (u["places"] or u["text"]) else None
    if pid and pid != P["plan_id"]:
        keep = P.get("travellers")
        P.clear()
        P.update(_plan())
        P["plan_id"], P["travellers"] = pid, keep
    elif u["places"] and not pid:
        name = u["places"][0].name
        turn.body.append(turn.tr("plan_unsupported", place=name, list=", ".join(p["name"][lang] for p in plans.values())))
        for p in plans.values():
            turn.qr(p["name"][lang], f"plan a trip to {p['name']['en']}")
        state["asked"] = "plan_dest"
        return

    if u["duration"]:
        n, unit = u["duration"]
        P["days"] = n + 1 if unit == "night" else n
        P["days_explicit"] = True
    elif state.get("asked") == "plan_days":
        m = re.search(r"\b(\d{1,2})\b", D.normalize_digits(u["text"]))
        if m:
            P["days"] = int(m.group(1))
    styles = [i for i in u["interests"] if i in ("budget", "luxury")]
    others = [i for i in u["interests"] if i not in ("budget", "luxury")]
    if styles:
        P["style"] = styles[-1]
    for i in others:
        if i not in P["interests"]:
            P["interests"].append(i)
    explicit_none = bool(re.search(r"\bno\s+(?:particular\s+|special\s+)?pref|\bno\s+preference|ಆದ್ಯತೆ\s*ಇಲ್ಲ|कोई\s+पसंद\s+नहीं", u["low"]))
    if u["interests"] or u["budget_amount"] or explicit_none or (u["cmd_no_pref"] and state.get("asked") == "plan_prefs"):
        P["prefs_asked"] = True
    tv = u["pax"]
    if P["travellers"] is None and state["flight"]["adults"]:
        P["travellers"] = state["flight"]["adults"] + (state["flight"]["children"] or 0)
    if tv["adults"]:
        P["travellers"] = tv["adults"] + (tv["children"] or 0)
    elif tv["family"]:
        P["travellers"] = tv["family"]
    if u["budget_amount"]:
        P["budget_amount"] = u["budget_amount"]

    # next missing
    if not P["plan_id"]:
        turn.body.append(turn.tr("plan_ask_dest", list=", ".join(p["name"][lang] for p in plans.values())))
        for p in plans.values():
            turn.qr(p["name"][lang], f"plan a trip to {p['name']['en']}")
        state["asked"] = "plan_dest"
        return
    plan = plans[P["plan_id"]]
    pname = plan["name"][lang]
    if P["days"] is not None and not (plan["min_days"] <= P["days"] <= plan["max_days"]):
        closest = min(max(P["days"], plan["min_days"]), plan["max_days"])
        turn.body.append(turn.tr("plan_days_range", dest=pname, min=plan["min_days"], max=plan["max_days"],
                                 days=P["days"], closest=closest))
        turn.qr(turn.tr("n_days", n=closest), f"{closest} days")
        P["days"] = None
        state["asked"] = "plan_days"
        return
    if P["days"] is None:
        turn.body.append(turn.tr("plan_ask_days", dest=pname, min=plan["min_days"], max=plan["max_days"]))
        for n in range(plan["min_days"], plan["max_days"] + 1):
            turn.qr(turn.tr("n_days", n=n), f"{n} days")
        state["asked"] = "plan_days"
        return
    if not P["prefs_asked"] and not P["interests"] and not P["style"]:
        turn.body.append(turn.tr("plan_ask_prefs"))
        for key in ("budget", "luxury", "adventure", "family", "culture"):
            turn.qr(turn.tr("interest_" + key), key)
        turn.qr(turn.tr("qr_no_pref"), "no preference")
        state["asked"] = "plan_prefs"
        return
    build_plan(turn)


def build_plan(turn: Turn) -> None:
    state = turn.state
    P = state["plan"]
    lang = state["lang"]
    plan = providers.ITINERARIES.plans[P["plan_id"]]
    n = P["days"]
    ranked = sorted(range(len(plan["days"])), key=lambda i: (plan["days"][i]["priority"], i))[:n]
    chosen = sorted(ranked)
    used_tags: set[str] = set()
    days_out = []
    for k, idx in enumerate(chosen):
        d = plan["days"][idx]
        acts = [{"text": a[lang], "tag": None} for a in d["core"]]
        for tag in P["interests"] + ([P["style"]] if P["style"] == "luxury" else []):
            opt = d["options"].get(tag)
            if opt:
                acts.append({"text": opt[lang], "tag": tag, "tag_label": turn.tr("interest_" + tag)})
                used_tags.add(tag)
        days_out.append({"n": k + 1, "title": d["title"][lang], "stop": plan["stops"][d["stop"]]["name"][lang],
                         "activities": acts})
    route, seen = [], set()
    for idx in chosen:
        s = plan["days"][idx]["stop"]
        if s not in seen:
            seen.add(s)
            st = plan["stops"][s]
            route.append({"name": st["name"][lang], "lat": st["lat"], "lon": st["lon"]})
    # return leg for round routes (e.g. Kerala ends in Kochi)
    last = plan["days"][chosen[-1]]["stop"]
    if last in seen and route and plan["stops"][last]["name"][lang] != route[-1]["name"]:
        st = plan["stops"][last]
        route.append({"name": st["name"][lang], "lat": st["lat"], "lon": st["lon"]})

    travellers = P["travellers"] or 1
    style = P["style"] or "standard"
    notes = []
    if P["budget_amount"]:
        cost = lambda s: plan["daily_pp"][s] * n * travellers
        if cost(style) > P["budget_amount"]:
            fit = next((s for s in ("luxury", "standard", "budget") if cost(s) <= P["budget_amount"]
                        and ["budget", "standard", "luxury"].index(s) < ["budget", "standard", "luxury"].index(style)), None)
            if fit:
                style = fit
                notes.append(turn.tr("plan_budget_adjusted", style=turn.tr("style_" + fit), amount=money(P["budget_amount"])))
            else:
                notes.append(turn.tr("plan_over_budget", amount=money(P["budget_amount"])))
    pp_day = plan["daily_pp"][style]
    total = pp_day * n * travellers
    unsupported = [t_ for t_ in P["interests"] if t_ not in used_tags]
    for t_ in unsupported:
        notes.append(turn.tr("plan_pref_unsupported", pref=turn.tr("interest_" + t_)))
    adjusted = n != plan["base_days"] or bool(used_tags) or style != "standard"
    P["style_used"] = style
    state["last_plan"] = P["plan_id"]
    turn.body.append(turn.tr("plan_result", days=n, dest=plan["name"][lang]))
    if adjusted:
        turn.body.append(turn.tr("plan_adjusted"))
    turn.blocks.append({
        "type": "itinerary", "plan_id": P["plan_id"], "title": turn.tr("plan_title", days=n, dest=plan["name"][lang]),
        "summary": plan["summary"][lang], "days_n": n, "route": route, "days": days_out,
        "interests": [turn.tr("interest_" + x) for x in P["interests"]],
        "budget": {"style": style, "style_label": turn.tr("style_" + style), "pp_day": pp_day,
                   "pp_day_label": money(pp_day), "travellers": travellers, "total": total,
                   "total_label": money(total), "excludes_flights": True},
        "adjusted": adjusted, "notes": notes, "sample": True,
    })
    state["asked"] = None
    turn.ask_feedback = True
    ap = plan["airports"][0]
    city = L.airport(ap)["city"]
    turn.qr(turn.tr("qr_flights_to", place=city), f"flights to {city}")
    hc = providers.HOTELS.city_for_codes(plan["airports"])
    if hc:
        hn = providers.HOTELS.cities[hc]["name"]
        turn.qr(turn.tr("qr_hotels_in", place=hn), f"hotels in {hn}")
    turn.qr(turn.tr("qr_change_prefs"), "change preferences")


# --------------------------------------------------------------------- finalize
def compat_slots(state) -> dict:
    """Flat view of the structured state (analytics, older tests/scripts)."""
    F, H = state["flight"], state["hotel"]
    lg = F["legs"][0]
    dest = lg["destination"]["city"] if lg["destination"] else None
    if state.get("mode") == "hotel" and H["city"]:
        dest = providers.HOTELS.cities[H["city"]]["name"]
    return {
        "trip_type": F["trip_type"],
        "origin": lg["origin"]["city"] if lg["origin"] else None,
        "origin_code": lg["origin"]["code"] if lg["origin"] else None,
        "destination": dest,
        "destination_code": lg["destination"]["code"] if lg["destination"] else None,
        "departure_date": lg["date"], "return_date": F["return_date"],
        "adult_count": F["adults"], "child_count": F["children"] or 0, "infant_count": F["infants"] or 0,
        "cabin_class": F["cabin"],
        "segments": [{"origin": x["origin"]["city"] if x["origin"] else None,
                      "destination": x["destination"]["city"] if x["destination"] else None,
                      "departure_date": x["date"]} for x in F["legs"]] if F["trip_type"] == "multi_city" else [],
        "add_segment_done": F["mc_done"],
        "hotel_city": H["city"], "check_in": H["checkin"], "check_out": H["checkout"],
    }


def build_ack(turn: Turn) -> list[str]:
    """Short acknowledgement of what changed THIS turn, in a fixed order."""
    st, ch = turn.state, turn.changed
    F, H = st["flight"], st["hotel"]
    items = []
    if ("trip",) in ch and F["trip_type"]:
        items.append(turn.tr("ack_trip_" + F["trip_type"]))
    for i, lg in enumerate(F["legs"]):
        o, d, dt = (("leg", i, "origin") in ch), (("leg", i, "destination") in ch), (("leg", i, "date") in ch)
        if not (o or d or dt):
            continue
        bits = []
        if (o or d) and lg["origin"] and lg["destination"]:
            bits.append(f"{loc_label(lg['origin'])} → {loc_label(lg['destination'])}")
        elif o and lg["origin"]:
            bits.append(turn.tr("ack_origin", place=loc_label(lg["origin"])))
        elif d and lg["destination"]:
            bits.append(turn.tr("ack_destination", place=loc_label(lg["destination"])))
        if dt and lg["date"]:
            bits.append(fdate(st, lg["date"]) if F["trip_type"] == "multi_city" else turn.tr("ack_depart", date=fdate(st, lg["date"])))
        if F["trip_type"] == "multi_city":
            items.append(turn.tr("ack_leg", n=i + 1, details=", ".join(bits)))
        else:
            items.extend(bits)
    if ("return",) in ch and F["return_date"]:
        items.append(turn.tr("ack_return", date=fdate(st, F["return_date"])))
    if ("pax",) in ch and F["adults"]:
        items.append(pax_text(st, F["adults"], F["children"], F["infants"]))
    if ("cabin",) in ch and F["cabin"]:
        items.append(cabin_text(st, F["cabin"]))
    if ("hotel_city",) in ch and H["city"]:
        items.append(turn.tr("ack_hotel_city", city=providers.HOTELS.cities[H["city"]]["name"]))
    if ("checkin",) in ch and H["checkin"]:
        items.append(turn.tr("ack_checkin", date=fdate(st, H["checkin"])))
    if ("checkout",) in ch and H["checkout"]:
        items.append(turn.tr("ack_checkout", date=fdate(st, H["checkout"])))
    return items + turn.acks


def finalize(turn: Turn) -> dict:
    state = turn.state
    parts = []
    if turn.errors:
        parts.extend(turn.errors)
    acks = build_ack(turn)
    if acks and not any(b["type"] in ("flights", "hotels") for b in turn.blocks):
        parts.append(turn.tr("ack", items=", ".join(dict.fromkeys(acks))))
    parts.extend(turn.notes)
    parts.extend(turn.body)
    reply = " ".join(p.strip() for p in parts if p and p.strip())
    if not reply:
        reply = turn.tr("clarify")

    # Optional natural rewording by the configured LLM. Guarded: every number,
    # date, price, code and flight number must survive or we keep the original.
    rephrased = False
    if os.environ.get("LLM_REPHRASE", "true").lower() == "true" and turn.intent not in ("reset",) and _llm_ok():
        t0 = time.perf_counter()
        new = llm.rephrase(reply, state["lang"])
        turn.timings["rephrase_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if new:
            reply, rephrased = new, True

    state["intent"] = turn.intent
    state["slots"] = compat_slots(state)
    state["expected_slot"] = state.get("asked")
    hint = turn.hint or {}
    results_flat = []
    for b in turn.blocks:
        if b["type"] == "flights":
            for lg in b["legs"]:
                results_flat.extend(lg["options"])
        elif b["type"] == "hotels":
            results_flat.extend(b["hotels"])
    rag = turn.rag or {}
    payload = {
        "success": True,
        "reply": reply,
        "language": state["lang"],
        "language_mode": state["lang_mode"],
        "intent": turn.intent,
        "confidence": round(float(turn.confidence), 3),
        "source": turn.source,
        "rephrased": rephrased,
        "blocks": turn.blocks,
        "quick_replies": turn.quick,
        "input_hint": turn.hint,
        "ask_feedback": turn.ask_feedback,
        "rag_used": bool(rag.get("used")),
        "rag_score": rag.get("score", 0.0),
        "rag_sources": [{"title": s["title"]} for s in rag.get("sources", [])],
        "clear_results": bool(turn.extra.get("clear_results")),
        "show_seat_selection": bool(turn.extra.get("show_seat_selection")),
        "seat_params": turn.extra.get("seat_params"),
        "selected_flight": turn.extra.get("selected_flight"),
        "slots": dict(state["slots"]),
        "missing": turn.extra.get("missing", []),
        "results": results_flat,
        "show_date_picker": hint.get("kind") == "date",
        "min_date": hint.get("min"),
        "stage_timings_ms": turn.timings,
        "current_flow": state.get("mode"),
    }
    state["history"].append({"role": "assistant", "text": reply})
    state["history"] = state["history"][-50:]
    state["_last"] = payload
    return state
