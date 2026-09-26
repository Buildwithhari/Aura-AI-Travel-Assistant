"""
Guided multi-turn flow tests (updated for the conversational upgrade).

Changes from the original file, and why:
  * Dates are computed relative to today: fixed July-2026 dates are now in the
    past and the assistant must reject past dates.
  * "Mumbai" has two airports (BOM, NMI) so the assistant asks which one;
    the tests answer that question instead of assuming BOM.
  * Quick replies are {label, value} objects (label is localized, value is
    what gets sent back), so assertions look at labels.
  * Cabin "First Class" is normalised to "First".
The parser unit tests for intent_classifier are unchanged.
"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("LLM_PROVIDER", "custom")

import dates as D
from intent_classifier import CLASSIFIER, extract_entities, parse_passengers, parse_cabin_class, detect_slot_reply_type
import orchestrator


def day(n):
    return (D.today_for() + timedelta(days=n)).isoformat()


def labels(p):
    return [q["label"] for q in p.get("quick_replies", [])]


def test_intent_classification():
    for text in ["search a flight", "book a flight", "find a flight", "i need a flight", "search flight",
                 "book flight", "book a flight from delhi to mumbai",
                 "book a flight from delhi to mumbai tomorrow for 2 adults in business class",
                 "flight from mumbai to goa tomorrow"]:
        assert CLASSIFIER.predict(text)[0] == "flight_search", text


def test_fast_path():
    for text in ["search a flight", "book a flight", "Bangalore", "Mumbai", "tomorrow", "2 adults", "economy", "business"]:
        assert CLASSIFIER.predict(text)[1] >= 0.90, text


def test_passenger_parser():
    assert parse_passengers("2 adults 1 child 1 infant") == {"adult_count": 2, "child_count": 1, "infant_count": 1}
    assert parse_passengers("me and my wife")["adult_count"] == 2
    assert parse_passengers("family of 4")["adult_count"] == 4


def test_cabin_class_parser():
    assert parse_cabin_class("business") == "Business"
    assert parse_cabin_class("premium economy") == "Premium Economy"
    assert parse_cabin_class("economy") == "Economy"
    assert parse_cabin_class("first class") == "First Class"


def test_slot_reply_detection():
    assert detect_slot_reply_type("one way") == "trip_type"
    assert detect_slot_reply_type("tomorrow") == "date"
    assert detect_slot_reply_type("2 adults") == "passenger"
    assert detect_slot_reply_type("economy") == "cabin"
    assert detect_slot_reply_type("blr") == "city"


def test_entity_extraction():
    ents = extract_entities("flight from delhi to mumbai tomorrow for 2 adults in business class")
    assert ents.origin == "Delhi" and ents.destination == "Mumbai"
    assert ents.departure_date is not None and ents.adult_count == 2 and ents.cabin_class == "Business"


def test_guided_flow_full():
    s = orchestrator.new_state("t-guided")
    s = orchestrator.run_turn(s, "search a flight")
    p = s["_last"]
    assert p["intent"] == "flight_search" and "trip_type" in p["missing"] and s["expected_slot"] == "trip_type"
    assert "One-way" in labels(p)
    s = orchestrator.run_turn(s, "one way")
    assert s["_last"]["slots"]["trip_type"] == "one_way" and s["expected_slot"] == "origin"
    s = orchestrator.run_turn(s, "Bangalore")
    assert s["_last"]["slots"]["origin"] == "Bengaluru" and s["expected_slot"] == "destination"
    s = orchestrator.run_turn(s, "Mumbai")              # ambiguous -> asks which airport
    assert {q["value"] for q in s["_last"]["quick_replies"]} == {"BOM", "NMI"}
    s = orchestrator.run_turn(s, "BOM")
    p = s["_last"]
    assert p["slots"]["destination"] == "Mumbai" and "depart" in p["missing"] and p["show_date_picker"]
    s = orchestrator.run_turn(s, "tomorrow")
    assert s["_last"]["slots"]["departure_date"] == day(1)
    assert "return" not in s["_last"]["missing"]          # one-way never asks for a return date
    s = orchestrator.run_turn(s, "2 adults")
    assert s["_last"]["slots"]["adult_count"] == 2 and "cabin" in s["_last"]["missing"]
    s = orchestrator.run_turn(s, "Economy")
    p = s["_last"]
    assert p["slots"]["cabin_class"] == "Economy" and p["missing"] == [] and len(p["results"]) > 0


def test_partial_info():
    s = orchestrator.run_turn(orchestrator.new_state("t-partial"), "book a flight from Delhi to Chennai")
    p = s["_last"]
    assert p["slots"]["origin"] == "Delhi" and p["slots"]["destination"] == "Chennai"
    assert "trip_type" in p["missing"] and "depart" in p["missing"]


def test_complete_info_still_asks_trip_type():
    s = orchestrator.run_turn(orchestrator.new_state("t-complete"),
                              "book a flight from Delhi to Chennai tomorrow for 2 adults in business class")
    p = s["_last"]
    assert p["slots"]["adult_count"] == 2 and p["slots"]["cabin_class"] == "Business"
    assert p["missing"] == ["trip_type"] and p["results"] == []   # never assumes round-trip


def test_round_trip_flow():
    s = orchestrator.new_state("t-round")
    for msg in ["search a flight", "Round Trip", "Delhi", "Chennai", day(20)]:
        s = orchestrator.run_turn(s, msg)
    p = s["_last"]
    assert "return" in p["missing"] and p["show_date_picker"] and p["min_date"] == day(21)
    s = orchestrator.run_turn(s, day(25))
    assert s["_last"]["slots"]["return_date"] == day(25)
    s = orchestrator.run_turn(s, "2 adults 1 child")
    s = orchestrator.run_turn(s, "Business")
    p = s["_last"]
    assert len(p["results"]) == 8 and p["slots"]["trip_type"] == "round_trip"


def test_multi_city_direct_parsing():
    s = orchestrator.run_turn(orchestrator.new_state("t-mc"),
                              f"BLR to DEL on {day(20)} and DEL to BOM on {day(25)} for 2 adults economy")
    p = s["_last"]
    segs = p["slots"]["segments"]
    assert p["slots"]["trip_type"] == "multi_city" and len(segs) == 2
    assert (segs[0]["origin"], segs[0]["destination"], segs[0]["departure_date"]) == ("Bengaluru", "Delhi", day(20))
    assert (segs[1]["origin"], segs[1]["destination"], segs[1]["departure_date"]) == ("Delhi", "Mumbai", day(25))
    assert "mc_more" in p["missing"]         # asks: add another flight or search?
    s = orchestrator.run_turn(s, "search flights")
    assert len(s["_last"]["results"]) == 8


def test_multi_city_guided_flow():
    s = orchestrator.new_state("t-mc2")
    s = orchestrator.run_turn(s, "multi city flight")
    assert s["_last"]["slots"]["trip_type"] == "multi_city" and s["expected_slot"] == "leg_route:0"
    s = orchestrator.run_turn(s, "Bangalore to Delhi")
    assert s["expected_slot"] == "leg_date:0"
    s = orchestrator.run_turn(s, day(20))
    assert s["expected_slot"] == "leg_route:1"      # second flight, origin defaults to Delhi
    s = orchestrator.run_turn(s, "Kolkata")
    s = orchestrator.run_turn(s, day(24))
    assert s["expected_slot"] == "mc_more"
    s = orchestrator.run_turn(s, "no")
    assert s["_last"]["slots"]["add_segment_done"] is True and s["expected_slot"] == "pax"
    s = orchestrator.run_turn(s, "2 adults economy")
    assert len(s["_last"]["results"]) == 8


def test_country_origin_asks_for_city():
    s = orchestrator.run_turn(orchestrator.new_state("t-intl"), "flight from India to London")
    p = s["_last"]
    assert p["slots"]["origin"] is None
    assert "city in India" in p["reply"]
