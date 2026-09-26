"""End-to-end conversation behaviour (no server, no LLM)."""
import os
import re

import providers
from helpers import Chat, assert_clean, day, spoken

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ one-way
def test_one_way_domestic_journey_never_asks_return():
    c = Chat()
    c.say("Book a flight")
    assert set(c.qr_values()) == {"one way", "round trip", "multi city"}
    c.say("one way")
    c.say("from Chennai")
    c.say("to Kolkata")
    p = c.say(spoken(15))
    assert "return" not in p["missing"]
    p = c.say("2 adults and 1 kid, economy")
    blk = c.block("flights")
    assert blk and len(blk["legs"]) == 1 and len(blk["legs"][0]["options"]) >= 3
    assert all("return" not in r.lower() for r in c.replies)
    for r in c.replies:
        assert_clean(r)


def test_details_in_any_order_single_message():
    c = Chat()
    c.say(f"economy, just me, one-way, going to Hyderabad from Pune on {spoken(12)}")
    blk = c.block("flights")
    assert blk["legs"][0]["options"][0]["origin"] == "PNQ" and blk["legs"][0]["options"][0]["destination"] == "HYD"
    assert blk["legs"][0]["date"] == day(12)


def test_never_assumes_round_trip():
    c = Chat()
    p = c.say(f"I need a flight from Delhi to Chennai on {spoken(10)} for 1 adult in economy")
    assert p["missing"] == ["trip_type"] and not c.block("flights")


# ------------------------------------------------------------------ round-trip
def test_round_trip_international_with_corrections():
    c = Chat()
    c.say(f"Round trip Bengaluru to Dubai leaving {spoken(30)} returning {spoken(37)}, 2 adults, business")
    blk = c.block("flights")
    assert [lg["date"] for lg in blk["legs"]] == [day(30), day(37)]
    assert blk["legs"][0]["options"][0]["destination"] == "DXB"
    assert blk["legs"][1]["options"][0]["origin"] == "DXB"
    assert not blk["legs"][0]["options"][0]["domestic"]
    # change passengers: dates and route are preserved, search re-runs
    c.say("actually make it 3 adults")
    blk = c.block("flights")
    assert c.s["flight"]["adults"] == 3 and [lg["date"] for lg in blk["legs"]] == [day(30), day(37)]
    # change only the return date
    c.say(f"change the return to {spoken(40)}")
    assert c.s["flight"]["legs"][0]["date"] == day(30) and c.s["flight"]["return_date"] == day(40)
    # switching to one-way drops the return date
    c.say("make it one way")
    assert c.s["flight"]["return_date"] is None and len(c.block("flights")["legs"]) == 1


def test_return_must_follow_departure():
    c = Chat()
    c.say("round trip from Delhi to Chennai")
    c.say(spoken(20))
    p = c.say(spoken(15))
    assert c.s["flight"]["return_date"] is None and "return" in p["missing"]
    assert "after" in p["reply"].lower()


def test_past_and_invalid_dates_rejected():
    c = Chat()
    c.say("one way from Delhi to Chennai")
    p = c.say("yesterday")
    assert c.s["flight"]["legs"][0]["date"] is None and "past" in p["reply"].lower()
    p = c.say("31 feb")
    assert c.s["flight"]["legs"][0]["date"] is None and "calendar date" in p["reply"].lower()


def test_ambiguous_date_correction_asks():
    c = Chat()
    c.say(f"round trip Delhi to Chennai {spoken(20)} to {spoken(25)}")
    p = c.say(f"change it to {spoken(22)}")
    assert "departure date or the return" in p["reply"]
    c.say("return")
    assert c.s["flight"]["return_date"] == day(22) and c.s["flight"]["legs"][0]["date"] == day(20)


# ------------------------------------------------------------------ multi-city
def test_multi_city_add_remove_correct():
    c = Chat()
    c.say("multi city")
    c.say(f"Bengaluru to Delhi on {spoken(10)}")
    p = c.say("Jaipur")                                 # origin continues from Delhi
    assert c.s["flight"]["legs"][1]["origin"]["code"] == "DEL"
    c.say(spoken(14))
    c.say("add another flight")
    p = c.say(f"from Jaipur to Bengaluru on {spoken(12)}")   # before flight 2 -> rejected
    assert c.s["flight"]["legs"][2]["date"] is None and "can't be before" in p["reply"]
    c.say(spoken(18))
    assert len(c.s["flight"]["legs"]) == 3
    c.say("change flight 2 date to " + spoken(15))
    assert c.s["flight"]["legs"][1]["date"] == day(15)
    c.say("remove flight 3")
    assert len(c.s["flight"]["legs"]) == 2
    c.say("search flights")
    c.say("1 adult economy")
    blk = c.block("flights")
    assert [lg["options"][0]["origin"] + "-" + lg["options"][0]["destination"] for lg in blk["legs"]] == ["BLR-DEL", "DEL-JAI"]
    # each segment is selected separately
    c.pick_flight(0)
    p, _ = c.pick_flight(1)
    assert set(c.s["selection"]["flights"]) == {0, 1}


def test_multi_city_international():
    c = Chat()
    c.say(f"Mumbai to Singapore on {spoken(40)} and Singapore to Bangkok on {spoken(44)}, 2 adults economy")
    c.say("BOM")
    c.say("Suvarnabhumi")
    c.say("search flights")
    blk = c.block("flights")
    assert [lg["options"][0]["destination"] for lg in blk["legs"]] == ["SIN", "BKK"]


# ------------------------------------------------------------------ locations
def test_ambiguous_city_asks_instead_of_guessing():
    c = Chat()
    p = c.say("flight from Delhi to Mumbai")
    assert c.s["flight"]["legs"][0]["destination"] is None
    assert set(c.qr_values()) == {"BOM", "NMI"}
    c.say("Navi Mumbai")
    assert c.s["flight"]["legs"][0]["destination"]["code"] == "NMI"


def test_state_needs_airport_choice_and_typo_suggestions():
    c = Chat()
    p = c.say("flight to Kerala")
    assert "state" in p["reply"] and set(c.qr_values()) == {"COK", "TRV", "CCJ", "CNN"}
    c.say("Trivandrum")
    assert c.s["flight"]["legs"][0]["destination"]["code"] == "TRV"
    p = c.say("from Banglor")
    assert "BLR" in c.qr_values()
    c.say("BLR")
    assert c.s["flight"]["legs"][0]["origin"]["code"] == "BLR"
    p = c.say("from Xyzzyville")
    assert "couldn't find" in p["reply"]


def test_same_origin_and_destination_rejected():
    c = Chat()
    p = c.say("one way flight from Delhi to Delhi")
    assert "can't both be DEL" in p["reply"]


# ------------------------------------------------------------------ hotels, totals, checkout
def test_hotels_five_options_with_images_and_fields():
    for city in providers.HOTELS.cities:
        hotels = providers.HOTELS.hotels_for(city)
        assert len(hotels) >= 5, city
        for h in hotels:
            assert os.path.exists(os.path.join(ROOT, h["image"].lstrip("/"))), h["image"]
            assert h["name"] and h["area"] and h["price_per_night"] > 0 and 0 < h["rating"] <= 5 and h["amenities"]
    assert os.path.exists(os.path.join(ROOT, "static/img/hotels/fallback.svg"))


def test_hotel_flow_and_unsupported_city():
    c = Chat()
    p = c.say("hotel in Shillong")
    assert "don't have sample hotels" in p["reply"]
    c.say(f"hotel in Jaipur from {spoken(20)} for 3 nights, 2 adults")
    blk = c.block("hotels")
    assert len(blk["hotels"]) >= 5 and blk["nights"] == 3
    assert all(h["stay_total"] == h["price_per_night"] * 3 * blk["rooms"] for h in blk["hotels"])


def test_domestic_round_trip_to_checkout_totals():
    c = Chat()
    c.say(f"round trip from Bengaluru to Delhi, {spoken(20)} to {spoken(25)}, 2 adults 1 child 1 infant economy")
    _, out = c.pick_flight(0, 1)
    _, back = c.pick_flight(1, 0)
    c.say("add a hotel")
    hb = c.block("hotels")
    assert hb["nights"] == 5 and hb["checkin"] == day(20) and hb["checkout"] == day(25)
    _, hotel = c.pick_hotel(3)
    c.say("review my trip")
    review = c.block("review")
    fl = lambda f: 2 * f["fare_adult"] + f["fare_child"] + f["fare_infant"]
    expected = fl(out) + fl(back) + hotel["price_per_night"] * 5 * hb["rooms"]
    assert review["total"] == expected
    p = c.act("checkout")
    co = c.block("checkout")
    assert co["total"] == expected and co["booked"] is False and co["payment_taken"] is False
    text = p["reply"].lower()
    assert "confirmed" not in text and "no pnr" in text
    assert not re.search(r"\b[A-Z0-9]{6}\b", p["reply"].replace("PNR", ""))   # no PNR-like reference


def test_seats_are_validated_and_added_to_total():
    c = Chat()
    c.say(f"one way Delhi to Chennai {spoken(10)} 2 adults economy")
    c.pick_flight(0)
    bad = c.act("seats_selected", leg=0, seats=[{"seat": "99Z", "price": 999999}])
    assert "couldn't save" in bad["reply"]
    c.act("seats_selected", leg=0, seats=[{"seat": "4A", "price": 800}, {"seat": "12C", "price": 600}])
    c.say("review")
    lines = c.block("review")["lines"]
    assert any(l["kind"] == "seats" and l["amount"] == 1400 for l in lines)


def test_simulated_update_requires_selection_and_is_labelled():
    c = Chat()
    p = c.say("simulate a delay")
    assert "select a sample flight first" in p["reply"].lower()
    c.say(f"one way Delhi to Chennai {spoken(10)} 1 adult economy")
    _, f = c.pick_flight(0)
    p = c.act("simulate_update")
    alert = c.block("alert")
    assert alert["simulated"] is True and alert["live_feed"] is False and alert["delay_min"] == 30
    assert alert["old"] == f["depart"] and "no live airline feed" in p["reply"].lower()
    assert "real-time" not in p["reply"].lower()


# ------------------------------------------------------------------ itineraries
def test_itineraries_two_domestic_two_international():
    kinds = [p["kind"] for p in providers.ITINERARIES.plans.values()]
    assert kinds.count("domestic") >= 2 and kinds.count("international") >= 2


def test_plan_with_preferences_budget_and_route():
    c = Chat()
    c.say("Plan a trip")
    c.say("Kerala")
    c.say("5 days")
    p = c.say("family and culture, 2 people")
    it = c.block("itinerary")
    assert it["days_n"] == 5 and len(it["days"]) == 5 and it["adjusted"] is True
    assert len(it["route"]) >= 3                                   # multi-stop route sketch
    tags = {a["tag"] for d in it["days"] for a in d["activities"] if a["tag"]}
    assert {"family", "culture"} <= tags
    plan = providers.ITINERARIES.plans["kerala"]
    assert it["budget"]["total"] == plan["daily_pp"]["standard"] * 5 * 2


def test_plan_duration_out_of_range_and_unsupported_destination():
    c = Chat()
    p = c.say("plan a 10 day trip to Rajasthan")
    assert "without inventing" in p["reply"] and "6 days" in c.qr_values()
    p = c.say("plan a trip to Paris")
    assert "don't have a curated plan for Paris" in p["reply"] and not c.block("itinerary")
    assert any("Dubai" in v for v in c.qr_values())


def test_plan_budget_cap_changes_level_and_standard_plan_not_marked_adjusted():
    c = Chat()
    c.say("plan a 5 day trip to Kerala, no preference")
    it = c.block("itinerary")
    assert it and it["adjusted"] is False and it["budget"]["style"] == "standard"
    c = Chat()
    c.say("plan a 4 day trip to Rajasthan for 2 people under 30k")
    it = c.block("itinerary")
    assert it["budget"]["style"] == "budget" and it["budget"]["total"] <= 30000


# ------------------------------------------------------------------ quick replies == typed text
def test_quick_reply_values_and_free_text_are_equivalent():
    a, b = Chat(), Chat()
    a.say("Book a flight"); b.say("Book a flight")
    a.say("round trip", button=True); b.say("I'd like a return ticket please")
    assert a.s["flight"]["trip_type"] == b.s["flight"]["trip_type"] == "round_trip"
    a.say("2 adults economy", button=True); b.say("two of us, economy class")
    assert (a.s["flight"]["adults"], a.s["flight"]["cabin"]) == (b.s["flight"]["adults"], b.s["flight"]["cabin"]) == (2, "Economy")


# ------------------------------------------------------------------ language
KANNADA = re.compile(r"[\u0C80-\u0CFF]")


def test_kannada_selected_stays_kannada_through_complete_journey():
    c = Chat(lang="kn", mode="manual")
    c.say("hello")
    c.say("Book a flight", button=True)
    c.say("one way", button=True)
    c.say("Bangalore to Delhi")           # English typing must not flip a manual choice
    c.say(spoken(15))
    c.say("2 adults economy", button=True)
    c.pick_flight(0)
    c.say("add a hotel", button=True)
    c.say("3 nights")
    c.pick_hotel(0)
    c.act("review")
    c.act("checkout")
    c.act("simulate_update")
    c.say("Plan a trip", button=True)
    c.say("plan a trip to Dubai for 4 days, luxury")
    for r in c.replies:
        assert KANNADA.search(r), r
        assert not re.search(r"\b(Here are|Got it|Which|What|When|How many|Selected|Demo checkout finished)\b", r), r
        assert_clean(r)
    assert c.last["language"] == "kn"
    # numbers, prices and codes preserved
    it = c.block("itinerary")
    assert KANNADA.search(it["title"]) and KANNADA.search(it["days"][0]["title"])
    assert "₹" in it["budget"]["total_label"]


def test_auto_language_follows_script_and_manual_switch_by_text():
    c = Chat()
    p = c.say("ನಾಳೆ ಬೆಂಗಳೂರಿನಿಂದ ದೆಹಲಿಗೆ ವಿಮಾನ")
    assert p["language"] == "kn" and KANNADA.search(p["reply"])
    p = c.say("reply in hindi")
    assert p["language"] == "hi" and p["language_mode"] == "manual"
    p = c.say("one way")
    assert re.search(r"[\u0900-\u097F]", p["reply"])


def test_mixed_language_inputs():
    c = Chat()
    c.say("bangalore se delhi kal ki flight chahiye 2 log, one way, economy")
    blk = c.block("flights")
    assert blk and blk["legs"][0]["date"] == day(1)
    c = Chat()
    c.say("Chennai la irundhu Delhi ku flight venum")
    assert c.s["flight"]["legs"][0]["origin"]["code"] == "MAA" and c.s["flight"]["legs"][0]["destination"]["code"] == "DEL"


# ------------------------------------------------------------------ UX rules
def test_feedback_only_on_answers_not_questions():
    c = Chat()
    assert c.say("hi")["ask_feedback"] is False
    assert c.say("Book a flight")["ask_feedback"] is False
    assert c.say("one way")["ask_feedback"] is False
    assert c.say("what is the baggage allowance")["ask_feedback"] is True


def test_unclear_messages_ask_for_clarification():
    c = Chat()
    p = c.say("purple monkey dishwasher")
    assert p["intent"] == "fallback" and ("not sure" in p["reply"] or "rephrase" in p["reply"])
    assert not p["blocks"]


def test_side_question_keeps_booking_context():
    c = Chat()
    c.say(f"one way Delhi to Goa {spoken(9)} 1 adult economy")
    p = c.say("what is the baggage allowance?")
    assert "more than one airport" in p["reply"]            # the open question is repeated
    c.say("Mopa")
    assert c.block("flights")["legs"][0]["options"][0]["destination"] == "GOX"


def test_visa_domestic_vs_international():
    c = Chat()
    c.say(f"one way Delhi to Chennai {spoken(9)}")
    assert "don't need a visa" in c.say("do I need a visa?")["reply"]
    c = Chat()
    p = c.say("what documents do I need for an international trip visa")
    assert p["rag_used"] is True
