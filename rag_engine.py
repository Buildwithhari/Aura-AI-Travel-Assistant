"""Lightweight retrieval-augmented generation for Aura.

The retriever is fitted once and reused for every request. It uses TF-IDF rather
than an external vector database so the academic prototype remains private,
offline-capable and easy to demonstrate. Retrieved passages are used verbatim as
the factual grounding layer; an LLM is not allowed to invent policy details.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent / "data" / "travel_knowledge.json"
DEFAULT_THRESHOLD = 0.17


class TravelKnowledgeRetriever:
    def __init__(self, path: Path = KB_PATH):
        self.documents = json.loads(path.read_text(encoding="utf-8"))
        self._vectorizer = None
        self._matrix = None
        self._build_index()

    @staticmethod
    def _document_text(doc: dict) -> str:
        return " ".join([
            doc.get("title", ""),
            doc.get("category", "").replace("_", " "),
            " ".join(doc.get("keywords", [])),
            doc.get("content", ""),
        ])

    def _build_index(self) -> None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
                sublinear_tf=True,
            )
            self._matrix = self._vectorizer.fit_transform(
                [self._document_text(d) for d in self.documents]
            )
        except ImportError:
            # The project already depends on scikit-learn, but keyword overlap
            # keeps the knowledge layer usable if dependencies are incomplete.
            self._vectorizer = None
            self._matrix = None

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def retrieve(self, query: str, intent_hint: str | None = None, top_k: int = 3) -> list[dict]:
        enriched_query = f"{query} {(intent_hint or '').replace('_', ' ')}".strip()
        if self._vectorizer is not None and self._matrix is not None:
            from sklearn.metrics.pairwise import cosine_similarity

            query_vector = self._vectorizer.transform([enriched_query])
            scores = cosine_similarity(query_vector, self._matrix).ravel()
        else:
            query_tokens = self._tokens(enriched_query)
            scores = []
            for doc in self.documents:
                doc_tokens = self._tokens(self._document_text(doc))
                scores.append(len(query_tokens & doc_tokens) / max(len(query_tokens), 1))

        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)
        matches = []
        for index, score in ranked[:top_k]:
            item = dict(self.documents[index])
            item["score"] = round(float(score), 4)
            matches.append(item)
        return matches

    def answer(self, query: str, intent_hint: str | None = None, threshold: float = DEFAULT_THRESHOLD,
               lang: str = "en") -> dict:
        matches = self.retrieve(expand_query(query), intent_hint=intent_hint, top_k=2)
        if not matches or matches[0]["score"] < threshold:
            return {"used": False, "score": matches[0]["score"] if matches else 0.0, "matches": matches}

        best = matches[0]
        doc = next((d for d in self.documents if d["id"] == best["id"]), {})
        needs_verify = "verify" not in best["content"].lower() and best["category"] in {
            "baggage_info", "visa_enquiry", "modify_booking", "cancel_booking"}
        localized = lang in ("kn", "hi") and bool(doc.get(f"content_{lang}"))
        answer = doc[f"content_{lang}"] if localized else best["content"]
        if needs_verify:
            answer += VERIFY_SUFFIX.get(lang if localized else "en")
        return {
            "used": True,
            "answer": answer,
            "localized": localized or lang == "en",
            "score": best["score"],
            "sources": [{"id": best["id"], "title": best["title"], "source": best["source"]}],
            "matches": matches,
        }


VERIFY_SUFFIX = {
    "en": " Please verify the final rule with the operating airline or relevant authority.",
    "kn": " ಅಂತಿಮ ನಿಯಮವನ್ನು ಏರ್‌ಲೈನ್ ಅಥವಾ ಸಂಬಂಧಿತ ಪ್ರಾಧಿಕಾರದೊಂದಿಗೆ ಪರಿಶೀಲಿಸಿ.",
    "hi": " अंतिम नियम एयरलाइन या संबंधित प्राधिकरण से ज़रूर जाँचें।",
}

# Kannada / Hindi / romanized question words -> English terms the TF-IDF index knows.
# The knowledge base is indexed in English, so without this a Kannada question finds nothing.
QUERY_EXPANSIONS = [
    (r"ಬ್ಯಾಗೇಜ್|ಲಗೇಜ್|ಸಾಮಾನು|ಬ್ಯಾಗ್|बैगेज|लगेज|सामान|बैग|saamaan|samaan|saamanu|samanu", "baggage luggage allowance"),
    (r"ಕೆಜಿ|ಕಿಲೋ|किलो|केजी", "kg allowance"),
    (r"ಪವರ್ ?ಬ್ಯಾಂಕ್|ಬ್ಯಾಟರಿ|पावर ?बैंक|बैटरी", "power bank battery"),
    (r"ಚೆಕ್[- ]?ಇನ್|चेक[- ]?इन|ಬೋರ್ಡಿಂಗ್|बोर्डिंग", "web check-in boarding pass"),
    (r"ಎಷ್ಟು (?:ಮೊದಲು|ಬೇಗ|ಮುಂಚೆ)|कितने? (?:घंटे )?पहले|eshtu (?:mundhe|modalu|bega)|kitne pehle", "how early arrive airport"),
    (r"ವೀಸಾ|वीज़ा|वीजा|ಪಾಸ್‌?ಪೋರ್ಟ್|पासपोर्ट|ದಾಖಲೆ|दस्तावेज़", "visa passport documents"),
    (r"ಹೆಸರು|नाम", "name correction match"),
    (r"ರದ್ದು|ರದ್ದತಿ|ಕ್ಯಾನ್ಸಲ್|रद्द|कैंसिल", "cancel cancellation"),
    (r"ಮರುಪಾವತಿ|ರೀಫಂಡ್|रिफ़?ंड|पैसे वापस|refund", "refund status"),
    (r"ವಿಮೆ|ಇನ್ಶೂರೆನ್ಸ್|बीमा|इंश्योरेंस|bima", "travel insurance"),
    (r"ಶಿಶು|ಮಗು|शिशु|बच्चा|infant|baby", "infant travel"),
    (r"ಗಾಲಿಕುರ್ಚಿ|ವೀಲ್ ?ಚೇರ್|व्हीलचेयर", "wheelchair assistance"),
    (r"ಊಟ|ಆಹಾರ|खाना|भोजन|oota", "special meal"),
    (r"ಬದಲಾಯಿಸ|ಬದಲಾವಣೆ|बदल", "change modify booking"),
]


def expand_query(query: str) -> str:
    import re as _re
    extra = [terms for pat, terms in QUERY_EXPANSIONS if _re.search(pat, query, _re.I)]
    return query + (" " + " ".join(extra) if extra else "")


RETRIEVER = TravelKnowledgeRetriever()


def retrieve(query: str, intent_hint: str | None = None, top_k: int = 3) -> list[dict]:
    return RETRIEVER.retrieve(query, intent_hint=intent_hint, top_k=top_k)


def answer(query: str, intent_hint: str | None = None, threshold: float = DEFAULT_THRESHOLD, lang: str = "en") -> dict:
    return RETRIEVER.answer(query, intent_hint=intent_hint, threshold=threshold, lang=lang)
