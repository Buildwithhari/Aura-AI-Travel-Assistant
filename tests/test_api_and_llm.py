"""Flask API contract + LLM success/failure paths (network is faked)."""
import io
import json
import os
import tempfile
import urllib.error
from pathlib import Path

import analytics_store
import app as app_module
import llm
import orchestrator as O
from helpers import Chat, spoken


def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_llm(monkeypatch_env, responder):
    """Enable the API provider with a fake key and route urlopen to `responder(system, user)`."""
    os.environ.update({"LLM_PROVIDER": "api", "LLM_API_KEY": "test-key", "LLM_API_PROVIDER": "openrouter"})
    llm._AVAIL_CACHE["key"] = None

    def urlopen(req, timeout=None):
        body = json.loads(req.data.decode())
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        out = responder(system, user)
        if isinstance(out, Exception):
            raise out
        return _Resp(json.dumps({"choices": [{"message": {"content": out}}]}).encode())
    monkeypatch_env["orig"] = llm._urlreq.urlopen
    llm._urlreq.urlopen = urlopen


def restore(monkeypatch_env):
    llm._urlreq.urlopen = monkeypatch_env["orig"]
    os.environ["LLM_PROVIDER"] = "custom"
    os.environ.pop("LLM_API_KEY", None)
    llm._AVAIL_CACHE["key"] = None


# ------------------------------------------------------------------ API contract
def _with_temp_db(fn):
    old = analytics_store.DB_PATH
    with tempfile.TemporaryDirectory() as tmp:
        analytics_store.DB_PATH = Path(tmp) / "a.db"
        try:
            return fn()
        finally:
            analytics_store.DB_PATH = old


def test_customer_response_has_no_technical_labels_but_analytics_does():
    def run():
        c = client()
        r = c.post("/chat", json={"message": f"one way Delhi to Chennai {spoken(9)} 1 adult economy"})
        data = r.get_json()
        assert r.status_code == 200 and data["success"]
        for k in ("intent", "confidence", "source", "stage_timings_ms"):
            assert k not in data
        text = json.dumps(data).lower()
        for label in ("fast nlp", "rag ready", "llama", "ollama", "mbert"):
            assert label not in text
        rows = analytics_store.recent_interactions(5)
        assert rows and rows[0]["intent"] == "flight_search" and rows[0]["source"]
    _with_temp_db(run)


def test_bad_requests_and_internal_errors_return_json():
    c = client()
    assert c.post("/chat", json={}).status_code == 400
    assert c.post("/chat", json={"action": "drop_tables"}).status_code == 400
    orig = O.run_turn
    O.run_turn = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        r = c.post("/chat", json={"message": "hi", "reply_language": "kn", "language_mode": "manual"})
        data = r.get_json()
        assert r.status_code == 500 and data["success"] is False and "ಸರ್ವರ್" in data["reply"]
    finally:
        O.run_turn = orig


def test_i18n_endpoint_welcome_and_reset_keep_language():
    def run():
        c = client()
        kn = c.get("/api/i18n/kn").get_json()
        assert kn["lang"] == "kn" and "ಆರಿಸಿ" in kn["strings"]["select"]
        assert c.get("/api/i18n/zz").get_json()["lang"] == "en"
        w = c.post("/chat", json={"action": "welcome", "reply_language": "kn", "language_mode": "manual"}).get_json()
        assert "ಔರಾ" in w["reply"] and len(w["reply"]) < 80          # short greeting
        c.post("/reset")
        r = c.post("/chat", json={"message": "hello"}).get_json()
        assert r["language"] == "kn"
        assert c.get("/health").get_json()["ok"] is True
    _with_temp_db(run)


def test_http_journey_with_button_actions():
    def run():
        c = client()
        d = c.post("/chat", json={"message": f"one way Bengaluru to Dubai on {spoken(30)} 1 adult economy", "tz": "Asia/Kolkata"}).get_json()
        opt = d["blocks"][0]["legs"][0]["options"][0]
        d = c.post("/chat", json={"action": "select_flight", "payload": {"leg": 0, "id": opt["id"]}}).get_json()
        assert opt["flight_no"] in d["reply"]
        d = c.post("/chat", json={"action": "review"}).get_json()
        assert d["blocks"][0]["total"] == opt["fare_adult"]
        d = c.post("/chat", json={"action": "checkout"}).get_json()
        assert d["blocks"][0]["type"] == "checkout" and d["blocks"][0]["booked"] is False
        d = c.post("/chat", json={"action": "simulate_update"}).get_json()
        assert d["blocks"][0]["simulated"] is True
        d = c.post("/chat", json={"action": "select_flight", "payload": {"leg": 0, "id": "forged"}}).get_json()
        assert "isn't in the current results" in d["reply"]
    _with_temp_db(run)


# ------------------------------------------------------------------ LLM paths
def test_llm_unavailable_without_real_key():
    os.environ.update({"LLM_PROVIDER": "api", "LLM_API_KEY": "your_api_key_here"})
    llm._AVAIL_CACHE["key"] = None
    try:
        assert llm.available_cached() is False
    finally:
        os.environ["LLM_PROVIDER"] = "custom"
        os.environ.pop("LLM_API_KEY", None)
        llm._AVAIL_CACHE["key"] = None


def test_llm_network_failure_degrades_to_rules():
    env = {}
    fake_llm(env, lambda s, u: urllib.error.URLError("no route to host"))
    try:
        c = Chat()
        p = c.say("hmm what do you think would be nice for me")      # no rule-based signal -> LLM tried
        assert c.s["_last"]["source"] == "degraded" and p["intent"] == "fallback"
        p = c.say(f"one way Delhi to Chennai {spoken(9)} 1 adult economy")   # rules still work
        assert c.block("flights") and p["rephrased"] is False
    finally:
        restore(env)


def test_llm_malformed_output_is_ignored():
    env = {}
    fake_llm(env, lambda s, u: "Sure! Here is JSON: {not valid")
    try:
        c = Chat()
        c.say("hmm what do you think would be nice for me")
        assert c.s["_last"]["source"] == "degraded"
    finally:
        restore(env)


def test_llm_extraction_is_validated_not_trusted():
    def responder(system, user):
        if "extract travel details" in system:
            return json.dumps({"intent": "flight_search", "confidence": 0.9, "entities": {
                "origin": "Atlantis", "destination": "Goa", "trip_type": "one_way", "adults": 42}})
        return None
    env = {}
    fake_llm(env, responder)
    try:
        c = Chat()
        p = c.say("I fancy some sunshine by the sea somewhere west")
        F = c.s["flight"]
        assert c.s["_last"]["source"] == "llm" and F["trip_type"] == "one_way"
        assert F["legs"][0]["origin"] is None          # unknown place from the LLM is dropped
        assert F["adults"] is None                     # out-of-range count ignored
        assert set(c.qr_values()) == {"GOI", "GOX"}    # ambiguous Goa still asks
    finally:
        restore(env)


def test_rephrase_guard_keeps_facts():
    env = {}
    fake_llm(env, lambda s, u: "Sure thing! Pick one of these flights for your party." if "Reword" in s else None)
    try:
        c = Chat()
        p = c.say(f"one way Delhi to Chennai {spoken(9)} 2 adults economy")
        assert p["rephrased"] is False and "2 adults" in p["reply"]     # dropped a number -> rejected
    finally:
        restore(env)
    env = {}
    fake_llm(env, lambda s, u: ("Lovely! " + u) if "Reword" in s else None)
    try:
        c = Chat()
        p = c.say(f"one way Delhi to Chennai {spoken(9)} 2 adults economy")
        assert p["rephrased"] is True and p["reply"].startswith("Lovely!")
    finally:
        restore(env)


def test_knowledge_answers_are_localized_offline_and_llm_only_fills_gaps():
    import rag_engine
    c = Chat(lang="kn", mode="manual")                 # no LLM: built-in Kannada answer
    p = c.say("what is the baggage allowance")
    assert "15 kg" in p["reply"] and "ಬ್ಯಾಗೇಜ್" in p["reply"] and "ಇಂಗ್ಲಿಷ್" not in p["reply"]
    doc = next(d for d in rag_engine.RETRIEVER.documents if d["id"] == "baggage-domestic")
    saved = doc.pop("content_kn")                      # simulate an untranslated document
    try:
        env = {}
        fake_llm(env, lambda s, u: ("ಅನುವಾದ: " + u) if "Translate" in s else None)
        try:
            p = Chat(lang="kn", mode="manual").say("what is the baggage allowance")
            assert "ಅನುವಾದ" in p["reply"]                 # LLM translation used for the gap
        finally:
            restore(env)
        p = Chat(lang="kn", mode="manual").say("what is the baggage allowance")
        assert "ಇಂಗ್ಲಿಷ್" in p["reply"]                    # no LLM: English, clearly flagged
    finally:
        doc["content_kn"] = saved


def test_facts_preserved_helper():
    assert llm.facts_preserved("Total ₹12,400 for AU 912 on 6 Oct", "Your total is ₹12,400 for AU 912, 6 Oct")
    assert not llm.facts_preserved("Total ₹12,400 for AU 912", "Your total is ₹12,000 for AU 912")
    assert not llm.facts_preserved("BLR → DEL", "Bengaluru to Delhi")
