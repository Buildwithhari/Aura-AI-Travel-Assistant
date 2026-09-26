import os
from llm.provider_factory import get_provider

def _load_dotenv():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

_load_dotenv()

def is_simple_message(text: str) -> bool:
    text = text.lower().strip()
    words = text.split()
    if len(words) > 4:
        return False
        
    simple_phrases = {
        "hi", "hello", "hey", "hola", "namaste",
        "yes", "no", "y", "n", "ok", "okay", "sure", "yep", "yeah",
        "one way", "round trip", "multi city", "one-way", "round-trip", "multi-city",
        "economy", "premium economy", "business", "first class", "first", "business class",
        "book flight", "book a flight", "search flight", "search flights", "hotel", "book hotel",
        "new search", "start over", "reset", "book another flight",
        "tomorrow", "today", "day after tomorrow", "yesterday"
    }
    if text in simple_phrases:
        return True
        
    if len(words) == 1 and words[0].isdigit():
        return True
    if len(words) <= 3 and any(w in ["adult", "adults", "child", "children", "infant", "infants", "pax", "passenger", "passengers"] for w in words):
        return True
        
    from intent_classifier import KNOWN_CITIES, AIRPORT_CODES
    if len(words) <= 2:
        clean_text = text.replace(",", "").strip()
        if clean_text.upper() in AIRPORT_CODES:
            return True
        for city in KNOWN_CITIES:
            if clean_text == city.lower():
                return True
                
    return False

def parse(user_text: str, known_slots: dict | None = None) -> dict | None:
    known_slots = known_slots or {}
    
    # 1. Greeting and slot bypass: use offline CustomProvider for simple cases
    if is_simple_message(user_text):
        from llm.custom_provider import CustomProvider
        try:
            res = CustomProvider().analyze(user_text, known_slots)
            out = {"intent": res.get("intent")}
            ents = res.get("entities") or {}
            out.update(ents)
            return out
        except Exception:
            return None

    # 2. Complex queries use active LLM provider (Ollama / API)
    provider = get_provider()
    try:
        res = provider.analyze(user_text, known_slots)
        out = {"intent": res.get("intent")}
        ents = res.get("entities") or {}
        out.update(ents)
        return out
    except Exception:
        return None

def is_available() -> bool:
    provider_type = os.environ.get("LLM_PROVIDER", "custom").lower().strip()
    if provider_type == "api":
        return bool(os.environ.get("LLM_API_KEY"))
    elif provider_type == "ollama":
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except Exception:
            return False
    else:
        return True


# ---------------------------------------------------------------------------
# Travel NLU + natural wording (added for the conversational upgrade).
# Every function here returns None on ANY failure so the deterministic
# pipeline keeps working without credentials or network.
# ---------------------------------------------------------------------------
import json as _json
import re as _re
import time as _time
import urllib.request as _urlreq

_AVAIL_CACHE = {"t": 0.0, "v": False, "key": None}


def available_cached(ttl: float = 60.0) -> bool:
    key = (os.environ.get("LLM_PROVIDER"), bool(os.environ.get("LLM_API_KEY")))
    if _AVAIL_CACHE["key"] == key and _time.time() - _AVAIL_CACHE["t"] < ttl:
        return _AVAIL_CACHE["v"]
    ptype = os.environ.get("LLM_PROVIDER", "custom").lower().strip()
    if ptype == "api":
        k = os.environ.get("LLM_API_KEY", "").strip()
        v = bool(k) and k != "your_api_key_here"
    elif ptype == "ollama":
        v = is_available()
    else:
        v = False
    _AVAIL_CACHE.update(t=_time.time(), v=v, key=key)
    return v


def _chat(system: str, user: str, json_mode: bool = False, timeout: float | None = None) -> str | None:
    """One completion from the configured provider (API or Ollama). None on failure."""
    ptype = os.environ.get("LLM_PROVIDER", "custom").lower().strip()
    timeout = timeout or float(os.environ.get("API_TIMEOUT_SECONDS", "4.0"))
    try:
        if ptype == "api":
            prov = os.environ.get("LLM_API_PROVIDER", "openrouter").lower()
            key = os.environ.get("LLM_API_KEY", "").strip()
            if not key or key == "your_api_key_here":
                return None
            model = os.environ.get("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct").strip()
            url = "https://api.groq.com/openai/v1/chat/completions" if prov == "groq" else "https://openrouter.ai/api/v1/chat/completions"
            if prov == "groq" and model == "meta-llama/llama-3.1-8b-instruct":
                model = "llama-3.1-8b-instant"
            body = {"model": model, "temperature": 0.4,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
                body["temperature"] = 0.0
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
            if prov != "groq":
                headers.update({"HTTP-Referer": "http://localhost:5000", "X-Title": "Aura Travel Assistant"})
            req = _urlreq.Request(url, data=_json.dumps(body).encode(), headers=headers, method="POST")
            with _urlreq.urlopen(req, timeout=timeout) as r:
                data = _json.loads(r.read().decode())
            return data["choices"][0]["message"]["content"].strip()
        if ptype == "ollama":
            body = {"model": os.environ.get("OLLAMA_MODEL", "llama3.2:3b"), "stream": False,
                    "prompt": f"{system}\n\n{user}", "options": {"temperature": 0.3}}
            if json_mode:
                body["format"] = "json"
            req = _urlreq.Request("http://localhost:11434/api/generate", data=_json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
            with _urlreq.urlopen(req, timeout=max(timeout, 10)) as r:
                return _json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:  # network, auth, quota, bad JSON ...
        print(f"[LLM] call failed: {type(e).__name__}: {e}")
    return None


_NLU_SYSTEM = (
    "You extract travel details for a travel assistant. Return ONLY a JSON object:\n"
    '{"intent": one of [flight_search, hotel_search, plan_trip, baggage_info, visa_enquiry, web_checkin, '
    'insurance, cancel_booking, modify_booking, refund_status, human_handoff, greeting, goodbye, fallback],'
    ' "confidence": 0..1, "entities": {"origin": str|null, "destination": str|null, "departure_date": "YYYY-MM-DD"|null,'
    ' "return_date": "YYYY-MM-DD"|null, "adults": int|null, "children": int|null, "infants": int|null,'
    ' "cabin_class": str|null, "trip_type": "one_way"|"round_trip"|"multi_city"|null, "hotel_city": str|null,'
    ' "check_in": "YYYY-MM-DD"|null, "check_out": "YYYY-MM-DD"|null}}\n'
    "Use the given 'today' for relative dates. Use null when not stated. Never guess airports or invent details. "
    "If the message is not about travel, use intent 'fallback'. The message may be in English, Indian English, "
    "Kannada, Hindi, Tamil, Telugu, Malayalam or a mix."
)


def extract(text: str, context: dict) -> dict | None:
    if not available_cached():
        return None
    raw = _chat(_NLU_SYSTEM, _json.dumps({"today": context.get("today"), "context": context, "message": text}), json_mode=True)
    if not raw:
        return None
    raw = _re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    try:
        data = _json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("entities", {}), dict):
        return None
    if data.get("intent") == "fallback":
        data["intent"] = None
    return data


_FACT_RE = _re.compile(r"₹[\d,]+|\b\d[\d,:.\-]*\b|\b[A-Z]{2}\s?\d{2,4}\b|\b[A-Z]{3}\b|PNR")
_LANG_NAMES = {"en": "English", "kn": "Kannada (ಕನ್ನಡ script)", "hi": "Hindi (Devanagari script)",
               "ta": "Tamil", "te": "Telugu", "ml": "Malayalam"}


def facts_preserved(original: str, candidate: str) -> bool:
    """Every number, date, price, time, airport code and flight number must survive."""
    if not candidate or len(candidate) > max(60, 2.6 * len(original)):
        return False
    norm = lambda s: s.replace(" ", "")
    cand = norm(candidate)
    return all(norm(f) in cand for f in _FACT_RE.findall(original))


def rephrase(text: str, lang: str) -> str | None:
    if not available_cached() or not text:
        return None
    system = (f"Reword this travel-assistant message so it sounds natural, warm and concise, in {_LANG_NAMES.get(lang, 'English')}. "
              "Keep every number, date, time, price, airport code, flight number and name exactly as written. "
              "Do not add facts, offers, questions or promises. Do not say anything is booked or confirmed. "
              "Return only the reworded message.")
    out = _chat(system, text, timeout=float(os.environ.get("REPHRASE_TIMEOUT_SECONDS", "3.0")))
    return out if out and facts_preserved(text, out) else None


def translate(text: str, lang: str) -> str | None:
    if not available_cached() or not text or lang == "en":
        return None
    system = (f"Translate into {_LANG_NAMES.get(lang, lang)}. Keep numbers, dates, prices, codes and names exactly. "
              "Return only the translation.")
    out = _chat(system, text)
    return out if out and facts_preserved(text, out) else None
