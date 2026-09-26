# -*- coding: utf-8 -*-
"""
Date understanding for Aura.

* Relative dates ("tomorrow", "next Friday", "ನಾಳೆ", "कल") are resolved against
  *today in the user's time zone* (sent by the browser; default Asia/Kolkata).
* Day-first numeric dates (Indian convention): 06/10/2026 == 6 October 2026.
* Invalid calendar dates (31 Feb) and past dates are returned with an `error`
  so the conversation can reject them instead of silently accepting them.
* Dates without a year roll forward to the next occurrence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

try:  # Windows needs the `tzdata` package for zoneinfo; we fall back to IST.
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

DEFAULT_TZ = "Asia/Kolkata"
_IST = timezone(timedelta(hours=5, minutes=30))
MAX_DAYS_AHEAD = 360  # sample inventory horizon

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
    # Kannada
    "ಜನವರಿ": 1, "ಫೆಬ್ರವರಿ": 2, "ಮಾರ್ಚ್": 3, "ಏಪ್ರಿಲ್": 4, "ಮೇ": 5, "ಜೂನ್": 6, "ಜುಲೈ": 7,
    "ಆಗಸ್ಟ್": 8, "ಸೆಪ್ಟೆಂಬರ್": 9, "ಅಕ್ಟೋಬರ್": 10, "ನವೆಂಬರ್": 11, "ಡಿಸೆಂಬರ್": 12,
    # Hindi
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6, "जुलाई": 7,
    "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "नवंबर": 11, "नवम्बर": 11,
    "दिसंबर": 12, "दिसम्बर": 12,
}
WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
    "ಸೋಮವಾರ": 0, "ಮಂಗಳವಾರ": 1, "ಬುಧವಾರ": 2, "ಗುರುವಾರ": 3, "ಶುಕ್ರವಾರ": 4, "ಶನಿವಾರ": 5, "ಭಾನುವಾರ": 6,
    "सोमवार": 0, "मंगलवार": 1, "बुधवार": 2, "गुरुवार": 3, "शुक्रवार": 4, "शनिवार": 5, "रविवार": 6,
}
# word -> offset in days
RELATIVE = {
    "today": 0, "tonight": 0, "tomorrow": 1, "tmrw": 1, "tmr": 1,
    "day after tomorrow": 2, "day after": 2, "overmorrow": 2,
    "aaj": 0, "kal": 1, "parso": 2, "parson": 2, "naale": 1, "nale": 1, "naadidu": 2,
    "आज": 0, "कल": 1, "परसों": 2, "ಇಂದು": 0, "ಇವತ್ತು": 0, "ನಾಳೆ": 1, "ನಾಡಿದ್ದು": 2,
}
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "a": 1, "an": 1,
}
_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯०१२३४५६७८९", "01234567890123456789")


@dataclass
class DateHit:
    start: int
    end: int
    iso: str | None
    error: str | None = None   # "past" | "invalid" | "too_far"
    text: str = ""


def normalize_digits(text: str) -> str:
    """Convert Kannada/Devanagari digits to ASCII (same length, spans preserved)."""
    return (text or "").translate(_DIGITS)


def today_for(tz_name: str | None = None) -> date:
    name = tz_name or DEFAULT_TZ
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(name)).date()
        except Exception:
            pass
    return datetime.now(_IST).date()


def valid_tz(tz_name: str | None) -> str:
    if not tz_name or len(tz_name) > 64 or not re.match(r"^[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+){0,2}$", tz_name):
        return DEFAULT_TZ
    if ZoneInfo is not None:
        try:
            ZoneInfo(tz_name)
            return tz_name
        except Exception:
            return DEFAULT_TZ
    return DEFAULT_TZ


def _check(d: date, today: date, explicit_year: bool) -> tuple[str | None, str | None]:
    if d < today:
        return d.isoformat(), "past"
    if (d - today).days > MAX_DAYS_AHEAD:
        return d.isoformat(), "too_far"
    return d.isoformat(), None


def _mk(y: int, m: int, d: int, today: date, explicit_year: bool) -> tuple[str | None, str | None]:
    try:
        dt = date(y, m, d)
    except ValueError:
        return None, "invalid"
    if not explicit_year and dt < today:
        try:
            dt = date(y + 1, m, d)
        except ValueError:
            return None, "invalid"
    return _check(dt, today, explicit_year)


_MONTH_ALT = "|".join(sorted((re.escape(k) for k in MONTHS), key=len, reverse=True))
_WD_ALT = "|".join(sorted((re.escape(k) for k in WEEKDAYS), key=len, reverse=True))
_REL_ALT = "|".join(sorted((re.escape(k) for k in RELATIVE), key=len, reverse=True))
_B = r"(?<![A-Za-z\u0C80-\u0CFF\u0900-\u097F])"   # left boundary incl. Indic letters
_E = r"(?![A-Za-z])"                                # right boundary (Indic may inflect)


def find_dates(text: str, today: date) -> list[DateHit]:
    src = normalize_digits(text or "")
    low = src.lower()
    hits: list[DateHit] = []
    taken = [False] * len(low)

    def add(a: int, b: int, iso: str | None, err: str | None) -> None:
        if any(taken[a:b]):
            return
        for i in range(a, b):
            taken[i] = True
        hits.append(DateHit(a, b, iso, err, src[a:b]))

    # 1) ISO yyyy-mm-dd
    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", low):
        iso, err = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)), today, True)
        add(m.start(), m.end(), iso, err)

    # 2) day range with month: "10-15 oct", "10 to 15 october"
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:-|–|to|till|until)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT}){_E}\.?(?:\s*,?\s*(\d{{4}}))?", low):
        mon = MONTHS[m.group(3)]
        yr = int(m.group(4)) if m.group(4) else today.year
        a_iso, a_err = _mk(yr, mon, int(m.group(1)), today, bool(m.group(4)))
        b_iso, b_err = _mk(yr, mon, int(m.group(2)), today, bool(m.group(4)))
        if any(taken[m.start():m.end()]):
            continue
        mid = m.start(2)
        add(m.start(), mid, a_iso, a_err)
        add(mid, m.end(), b_iso, b_err)

    # 3) "6 oct 2026", "6th of october"
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({_MONTH_ALT}){_E}\.?(?:\s*,?\s*(\d{{4}}))?", low):
        yr = int(m.group(3)) if m.group(3) else today.year
        iso, err = _mk(yr, MONTHS[m.group(2)], int(m.group(1)), today, bool(m.group(3)))
        add(m.start(), m.end(), iso, err)

    # 4) "oct 6", "october 6th, 2026"
    for m in re.finditer(rf"{_B}({_MONTH_ALT}){_E}\.?\s*(\d{{1,2}})(?:st|nd|rd|th)?\b(?:\s*,?\s*(\d{{4}}))?", low):
        yr = int(m.group(3)) if m.group(3) else today.year
        iso, err = _mk(yr, MONTHS[m.group(1)], int(m.group(2)), today, bool(m.group(3)))
        add(m.start(), m.end(), iso, err)

    # 5) dd/mm[/yyyy] or dd.mm.yyyy (day first)
    for m in re.finditer(r"\b(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?\b(?!\s*(?:star|%|kg|hrs?|hours?|km|adults?|people|pax))", low):
        y = m.group(3)
        yr = (int(y) + 2000 if len(y) == 2 else int(y)) if y else today.year
        iso, err = _mk(yr, int(m.group(2)), int(m.group(1)), today, bool(y))
        add(m.start(), m.end(), iso, err)

    # 6) "in 5 days", "after 3 days", "5 days from now"
    for m in re.finditer(r"\b(?:in|after)\s+(\d{1,3}|" + "|".join(NUMBER_WORDS) + r")\s+days?\b|\b(\d{1,3})\s+days?\s+from\s+(?:now|today)\b", low):
        n = m.group(1) or m.group(2)
        n = NUMBER_WORDS.get(n, None) if not n.isdigit() else int(n)
        if n is not None:
            iso, err = _check(today + timedelta(days=n), today, False)
            add(m.start(), m.end(), iso, err)

    # 7) weekends / next week
    for m in re.finditer(r"\b(this|next|coming)?\s*weekend\b", low):
        sat = today + timedelta(days=(5 - today.weekday()) % 7)
        if m.group(1) == "next":
            sat += timedelta(days=7)
        iso, err = _check(sat, today, False)
        add(m.start(), m.end(), iso, err)
    for m in re.finditer(r"\bnext\s+week\b", low):
        iso, err = _check(today + timedelta(days=7), today, False)
        add(m.start(), m.end(), iso, err)

    # 8) weekdays: "friday", "this friday", "next friday"
    for m in re.finditer(rf"{_B}(?:(this|next|coming)\s+)?({_WD_ALT}){_E}", low):
        wd = WEEKDAYS[m.group(2)]
        ahead = (wd - today.weekday()) % 7
        if m.group(1) == "next":
            # the named day in NEXT calendar week (Mon-Sun)
            start_next_week = today + timedelta(days=7 - today.weekday())
            d = start_next_week + timedelta(days=wd)
        elif m.group(1) == "this":
            d = today + timedelta(days=ahead)
        else:
            d = today + timedelta(days=ahead if ahead else 7)
        iso, err = _check(d, today, False)
        add(m.start(), m.end(), iso, err)

    # 9) relative words (longest first so "day after tomorrow" wins)
    for m in re.finditer(rf"{_B}({_REL_ALT})(?![A-Za-z])", low):
        word = m.group(1)
        if word in ("kal", "nale", "aaj") and not _near_travel_word(low):
            continue
        iso, err = _check(today + timedelta(days=RELATIVE[word]), today, False)
        add(m.start(), m.end(), iso, err)

    # 10) "yesterday" -> explicit past
    for m in re.finditer(r"\byesterday\b|कल\s+था", low):
        add(m.start(), m.end(), (today - timedelta(days=1)).isoformat(), "past")

    hits.sort(key=lambda h: h.start)
    return hits


def _near_travel_word(low: str) -> bool:
    return bool(re.search(r"flight|fly|ticket|hotel|jaana|jana|chahiye|beku|trip|travel|se\b|ge\b|inda\b|return|book|check", low))


_DUR_UNIT = r"(nights?|days?|ರಾತ್ರಿ|ದಿನ|रात|रातें|दिन|week|weeks)"


def find_duration(text: str) -> tuple[int, str] | None:
    """Return (count, 'night'|'day') for phrases like '3 nights', 'five-day', 'a week'."""
    low = normalize_digits(text or "").lower()
    m = re.search(rf"(\d{{1,2}}|{'|'.join(NUMBER_WORDS)})\s*-?\s*{_DUR_UNIT}", low)
    if not m:
        if re.search(r"\ba\s+week\b|\bone\s+week\b", low):
            return 7, "day"
        return None
    raw, unit = m.group(1), m.group(2)
    n = int(raw) if raw.isdigit() else NUMBER_WORDS.get(raw, 0)
    if unit.startswith("week"):
        return n * 7, "day"
    if unit.startswith("night") or unit in ("ರಾತ್ರಿ", "रात", "रातें"):
        return n, "night"
    return n, "day"


MONTH_NAMES = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "kn": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}
DAY_NAMES = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "kn": ["ಸೋಮ", "ಮಂಗಳ", "ಬುಧ", "ಗುರು", "ಶುಕ್ರ", "ಶನಿ", "ಭಾನು"],
    "hi": ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"],
}


def fmt(iso: str | None, lang: str = "en") -> str:
    """Human date, e.g. 'Tue, 6 Oct 2026' / 'ಮಂಗಳ, 6 ಅಕ್ಟೋಬರ್ 2026'. Digits stay ASCII."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    lang = lang if lang in MONTH_NAMES else "en"
    return f"{DAY_NAMES[lang][d.weekday()]}, {d.day} {MONTH_NAMES[lang][d.month - 1]} {d.year}"


def nights_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def add_days(iso: str, n: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=n)).isoformat()
