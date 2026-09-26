"""Persistent analytics and feedback store for the Aura prototype."""

from __future__ import annotations

import csv
import io
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "aura_analytics.db"
_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with _LOCK, _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message TEXT NOT NULL,
                intent TEXT,
                confidence REAL,
                source TEXT,
                language TEXT,
                response_ms REAL,
                success INTEGER NOT NULL DEFAULT 1,
                rag_used INTEGER NOT NULL DEFAULT 0,
                rag_score REAL NOT NULL DEFAULT 0,
                feedback INTEGER
            )
            """
        )


def log_interaction(*, session_id: str, message: str, payload: dict, response_ms: float, success: bool = True) -> int:
    initialize()
    safe_message = " ".join(message.split())[:500]
    with _LOCK, _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO interactions (
                created_at, session_id, message, intent, confidence, source,
                language, response_ms, success, rag_used, rag_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                session_id,
                safe_message,
                payload.get("intent"),
                payload.get("confidence"),
                payload.get("source"),
                payload.get("language", "en"),
                float(response_ms),
                1 if success else 0,
                1 if payload.get("rag_used") else 0,
                float(payload.get("rag_score") or 0),
            ),
        )
        return int(cursor.lastrowid)


def record_feedback(interaction_id: int, rating: int) -> bool:
    if rating not in (-1, 1):
        return False
    initialize()
    with _LOCK, _connect() as connection:
        cursor = connection.execute(
            "UPDATE interactions SET feedback = ? WHERE id = ?",
            (rating, interaction_id),
        )
        return cursor.rowcount == 1


def _percent(numerator: float, denominator: float) -> float:
    return round((numerator / denominator * 100), 1) if denominator else 0.0


def dashboard_metrics() -> dict:
    initialize()
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM interactions ORDER BY id").fetchall()

    total = len(rows)
    latencies = sorted(float(r["response_ms"] or 0) for r in rows)
    p95_index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.95) - 1)) if latencies else 0
    feedback_rows = [r for r in rows if r["feedback"] is not None]

    def breakdown(field: str) -> list[dict]:
        counts: dict[str, int] = {}
        for row in rows:
            key = str(row[field] or "unknown")
            counts[key] = counts.get(key, 0) + 1
        return [
            {"label": key, "count": value, "percent": _percent(value, total)}
            for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]

    fallback_count = sum(1 for r in rows if r["intent"] == "fallback" or r["source"] in ("degraded", "custom_fallback"))
    rag_count = sum(int(r["rag_used"] or 0) for r in rows)
    positive = sum(1 for r in feedback_rows if r["feedback"] == 1)
    return {
        "summary": {
            "total_interactions": total,
            "unique_sessions": len({r["session_id"] for r in rows}),
            "average_confidence": round(sum(float(r["confidence"] or 0) for r in rows) / total, 3) if total else 0,
            "average_response_ms": round(sum(latencies) / total, 1) if total else 0,
            "p95_response_ms": round(latencies[p95_index], 1) if latencies else 0,
            "fallback_rate": _percent(fallback_count, total),
            "rag_usage_rate": _percent(rag_count, total),
            "positive_feedback_rate": _percent(positive, len(feedback_rows)),
            "feedback_count": len(feedback_rows),
        },
        "intents": breakdown("intent"),
        "sources": breakdown("source"),
        "languages": breakdown("language"),
    }


def recent_interactions(limit: int = 50) -> list[dict]:
    initialize()
    limit = max(1, min(int(limit), 200))
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM interactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def export_csv() -> str:
    rows = recent_interactions(200)
    output = io.StringIO()
    fields = list(rows[0].keys()) if rows else [
        "id", "created_at", "session_id", "message", "intent", "confidence",
        "source", "language", "response_ms", "success", "rag_used", "rag_score", "feedback"
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


initialize()
