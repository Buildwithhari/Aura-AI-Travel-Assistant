"""
Aura - Flask backend.

Endpoints
  GET  /                    chat UI
  POST /chat                {"message" | "action"+"payload", "reply_language", "language_mode", "tz", "via_button"}
  POST /reset               clear this browser session's conversation
  GET  /api/i18n/<lang>     UI labels for the selected reply language
  GET  /health              liveness + component status (for admins / monitoring)
  GET  /admin               analytics dashboard (+ /api/admin/* JSON, CSV export, evaluation)
  POST /api/feedback        thumbs up/down for an interaction
  GET  /seat-selection      sample seat map (opened from the chat)

Customer-facing responses never include technical labels (intent, confidence,
model/route names, timings). Those are written to the server log and the
SQLite analytics store, where the admin dashboard reads them. Set
EXPOSE_DEBUG=true to include them in /chat responses while developing.
"""

from __future__ import annotations

import logging
import os
import time
import traceback
import uuid

from flask import Flask, Response, jsonify, render_template, request, session

import analytics_store
import i18n
import llm
import orchestrator
import rag_engine
from intent_classifier import CLASSIFIER

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
log = logging.getLogger("aura.app")

SESSIONS: dict[str, dict] = {}   # in-memory; swap for Redis to run multiple workers
INTERNAL_KEYS = {"intent", "confidence", "source", "stage_timings_ms", "rephrased", "rag_score"}
ACTIONS = {"select_flight", "select_hotel", "review", "checkout", "simulate_update", "open_seats",
           "seats_selected", "back_from_seat_selection", "welcome", "reset"}


def _get_state() -> dict:
    sid = session.get("sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["sid"] = sid
    if sid not in SESSIONS:
        SESSIONS[sid] = orchestrator.new_state(sid)
    return SESSIONS[sid]


def _public(payload: dict) -> dict:
    """Customer-safe response: drop technical labels unless debugging."""
    out = dict(payload)
    if os.environ.get("EXPOSE_DEBUG", "false").lower() != "true":
        for k in INTERNAL_KEYS:
            out.pop(k, None)
    out["assistant"] = "Aura"
    return out


def _error(lang: str, code: str, status: int):
    return jsonify({"success": False, "assistant": "Aura", "reply": i18n.t("server_error", lang),
                    "blocks": [], "quick_replies": [], "error": code, "language": lang}), status


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/seat-selection")
def seat_selection():
    return render_template("seat_selection.html")


@app.route("/admin")
def admin_dashboard():
    return render_template("admin.html")


@app.route("/api/i18n/<lang>")
def ui_strings(lang):
    lang = lang if lang in i18n.LANGS else "en"
    return jsonify({"lang": lang, "languages": i18n.LANGS, "strings": i18n.ui_strings(lang)})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    lang_req = data.get("reply_language")
    try:
        state = _get_state()
        text = str(data.get("message") or "").strip()[:1000]
        action = data.get("action")
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        if action and action not in ACTIONS:
            return _error(state.get("lang", "en"), "unknown_action", 400)
        if not text and not action:
            return _error(state.get("lang", "en"), "empty_message", 400)

        t0 = time.perf_counter()
        state = orchestrator.run_turn(
            state, text, action=action, payload=payload,
            lang=lang_req if lang_req in i18n.LANGS else None,
            lang_mode=data.get("language_mode") if data.get("language_mode") in ("auto", "manual") else None,
            tz=data.get("tz"), from_button=bool(data.get("via_button")),
        )
        total = round((time.perf_counter() - t0) * 1000, 1)
        last = state["_last"]
        log.info("turn intent=%s source=%s conf=%s lang=%s ms=%s", last.get("intent"), last.get("source"),
                 last.get("confidence"), last.get("language"), total)
        if action == "welcome":
            return jsonify(_public(last))
        interaction_id = analytics_store.log_interaction(
            session_id=state["session_id"], message=text or f"[{action}]", payload=last, response_ms=total)
        last["interaction_id"] = interaction_id
        return jsonify(_public(last))
    except Exception:  # always return a valid JSON envelope
        app.logger.error("chat() failed:\n%s", traceback.format_exc())
        return _error(lang_req if lang_req in i18n.LANGS else "en", "internal_error", 500)


@app.route("/reset", methods=["POST"])
def reset():
    sid = session.get("sid")
    if sid and sid in SESSIONS:
        old = SESSIONS[sid]
        SESSIONS[sid] = orchestrator.new_state(sid)
        SESSIONS[sid].update({k: old[k] for k in ("lang", "lang_mode", "tz")})
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok", "ok": True, "service": "aura",
        "classifier_model": CLASSIFIER.selected, "classifier_macro_f1": round(CLASSIFIER.macro_f1, 3),
        "llm_provider": os.environ.get("LLM_PROVIDER", "custom"),
        "llm_available": llm.available_cached(),
        "mbert_enabled": os.environ.get("USE_MBERT", "false").lower() == "true",
        "knowledge_documents": len(rag_engine.RETRIEVER.documents),
        "active_sessions": len(SESSIONS),
        "reply_languages": list(i18n.LANGS),
    })


@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.get_json(force=True, silent=True) or {}
    try:
        interaction_id = int(data.get("interaction_id"))
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_feedback"}), 400
    if not analytics_store.record_feedback(interaction_id, rating):
        return jsonify({"ok": False, "error": "interaction_not_found_or_invalid_rating"}), 400
    return jsonify({"ok": True})


@app.route("/api/admin/metrics")
def admin_metrics():
    return jsonify(analytics_store.dashboard_metrics())


@app.route("/api/admin/recent")
def admin_recent():
    return jsonify({"items": analytics_store.recent_interactions(request.args.get("limit", 50))})


@app.route("/api/admin/evaluate", methods=["POST"])
def admin_evaluate():
    from evaluation_engine import run_evaluation
    return jsonify(run_evaluation())


@app.route("/api/admin/export.csv")
def admin_export():
    return Response(analytics_store.export_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=aura_analytics.csv"})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    print("Aura ready -> http://localhost:5000   (admin: /admin)")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
