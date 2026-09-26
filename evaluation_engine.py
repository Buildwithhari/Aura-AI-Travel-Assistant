"""Repeatable offline evaluation for the intent classifier and RAG retriever."""

from __future__ import annotations

import json
from pathlib import Path

import rag_engine
from intent_classifier import CLASSIFIER

CASES_PATH = Path(__file__).resolve().parent / "data" / "evaluation_cases.json"


def run_evaluation() -> dict:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    intent_details = []
    for case in cases["intent_cases"]:
        predicted, confidence = CLASSIFIER.predict(case["text"])
        passed = predicted == case["expected"]
        intent_details.append({
            **case,
            "predicted": predicted,
            "confidence": round(float(confidence), 3),
            "passed": passed,
        })

    rag_details = []
    reciprocal_ranks = []
    for case in cases["rag_cases"]:
        matches = rag_engine.retrieve(case["text"], top_k=3)
        ids = [match["id"] for match in matches]
        rank = ids.index(case["expected_id"]) + 1 if case["expected_id"] in ids else 0
        reciprocal_ranks.append(1 / rank if rank else 0)
        rag_details.append({
            **case,
            "retrieved": ids,
            "top_score": matches[0]["score"] if matches else 0,
            "rank": rank,
            "passed": rank == 1,
        })

    intent_passed = sum(1 for item in intent_details if item["passed"])
    rag_passed = sum(1 for item in rag_details if item["passed"])
    return {
        "intent": {
            "accuracy": round(intent_passed / len(intent_details), 3),
            "passed": intent_passed,
            "total": len(intent_details),
            "details": intent_details,
        },
        "rag": {
            "top_1_accuracy": round(rag_passed / len(rag_details), 3),
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3),
            "passed": rag_passed,
            "total": len(rag_details),
            "details": rag_details,
        },
    }
