"""Tests for the RAG, analytics and evaluation upgrade."""

import tempfile
from pathlib import Path

import analytics_store
import rag_engine


def test_rag_retrieves_power_bank_policy():
    result = rag_engine.answer("Can I keep a power bank in checked luggage?")
    assert result["used"] is True
    assert result["sources"][0]["id"] == "baggage-restricted"


def test_rag_rejects_unrelated_query():
    result = rag_engine.answer("Write a Python sorting algorithm")
    assert result["used"] is False


def test_analytics_log_feedback_and_metrics():
    old_path = analytics_store.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            analytics_store.DB_PATH = Path(tmp) / "analytics.db"
            interaction_id = analytics_store.log_interaction(
                session_id="test-session",
                message="baggage allowance",
                payload={
                    "intent": "baggage_info", "confidence": 0.91,
                    "source": "rag", "language": "en",
                    "rag_used": True, "rag_score": 0.76,
                },
                response_ms=24.5,
            )
            assert analytics_store.record_feedback(interaction_id, 1)
            metrics = analytics_store.dashboard_metrics()["summary"]
            assert metrics["total_interactions"] == 1
            assert metrics["rag_usage_rate"] == 100.0
            assert metrics["positive_feedback_rate"] == 100.0
    finally:
        analytics_store.DB_PATH = old_path
