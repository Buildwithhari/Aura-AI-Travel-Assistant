import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import llm
from llm import is_simple_message
from llm.provider_factory import get_provider
from llm.custom_provider import CustomProvider
from llm.api_provider import APIProvider

def test_is_simple_message():
    assert is_simple_message("hi") is True
    assert is_simple_message("Bangalore") is True
    assert is_simple_message("tomorrow") is True
    assert is_simple_message("2 adults") is True
    assert is_simple_message("I need to book a flight from Bangalore to Delhi today at 6:30 for 2 adults in business class") is False

def test_provider_resolution():
    provider = get_provider()
    if os.environ.get("LLM_PROVIDER") == "api":
        assert isinstance(provider, APIProvider)
    else:
        assert isinstance(provider, CustomProvider)

def test_parse_simple_message():
    res = llm.parse("hi")
    assert res is not None
    assert res.get("intent") == "greeting"

def test_fallback_on_failure():
    bad_provider = APIProvider()
    bad_provider.api_key = "invalid_key_for_testing"
    res = bad_provider.analyze("I want to fly from Delhi to Mumbai tomorrow", {})
    assert res is not None
    assert res.get("intent") == "flight_search"
    assert res.get("entities", {}).get("origin") == "Delhi"

if __name__ == "__main__":
    print("Running LLM Provider tests...")
    test_is_simple_message()
    print("is_simple_message test passed.")
    test_provider_resolution()
    print("provider_resolution test passed.")
    test_parse_simple_message()
    print("parse_simple_message test passed.")
    test_fallback_on_failure()
    print("fallback_on_failure test passed.")
    print("All LLM Provider tests passed successfully!")
