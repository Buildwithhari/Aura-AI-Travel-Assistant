from datetime import date

import dates as D

TODAY = date(2026, 9, 22)   # a Tuesday


def one(text):
    hits = D.find_dates(text, TODAY)
    assert len(hits) == 1, (text, hits)
    return hits[0]


def test_relative_dates():
    assert one("tomorrow").iso == "2026-09-23"
    assert one("day after tomorrow").iso == "2026-09-24"
    assert one("in 3 days").iso == "2026-09-25"
    assert one("friday").iso == "2026-09-25"
    assert one("this friday").iso == "2026-09-25"
    assert one("next friday").iso == "2026-10-02"
    assert one("this weekend").iso == "2026-09-26"


def test_absolute_dates_are_day_first_and_roll_forward():
    assert one("06/10/2026").iso == "2026-10-06"
    assert one("6 oct").iso == "2026-10-06"
    assert one("Oct 6th").iso == "2026-10-06"
    assert one("5 March").iso == "2027-03-05"          # no year and already passed -> next year


def test_invalid_and_past_dates_are_flagged():
    assert one("31 feb").error == "invalid"
    assert one("2026-07-10").error == "past"
    assert one("yesterday").error == "past"
    assert one("2028-01-01").error == "too_far"


def test_multilingual_dates_and_digits():
    assert one("ನಾಳೆ").iso == "2026-09-23"
    assert one("कल दिल्ली से फ्लाइट").iso == "2026-09-23"
    assert one("15 ಅಕ್ಟೋಬರ್").iso == "2026-10-15"
    assert one("२५ अक्टूबर").iso == "2026-10-25"


def test_ranges_and_non_dates():
    assert [h.iso for h in D.find_dates("10-15 oct", TODAY)] == ["2026-10-10", "2026-10-15"]
    assert [h.iso for h in D.find_dates("4.5 star hotel", TODAY)] == []


def test_time_zone_handling():
    assert D.valid_tz("Asia/Kolkata") == "Asia/Kolkata"
    assert D.valid_tz("../../etc/passwd") == D.DEFAULT_TZ
    assert D.valid_tz("Not/AZone") == D.DEFAULT_TZ
    # the same instant can be a different calendar day in different zones
    days = {D.today_for(z) for z in ("Pacific/Kiritimati", "Pacific/Pago_Pago")}
    assert len(days) == 2


def test_duration_and_format():
    assert D.find_duration("3 nights") == (3, "night")
    assert D.find_duration("5-day trip") == (5, "day")
    assert D.find_duration("a week") == (7, "day")
    assert D.fmt("2026-10-06", "en") == "Tue, 6 Oct 2026"
    assert D.fmt("2026-10-06", "kn") == "ಮಂಗಳ, 6 ಅಕ್ಟೋಬರ್ 2026"
