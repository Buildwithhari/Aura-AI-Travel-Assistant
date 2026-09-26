from llm.base import BaseLLMProvider
from intent_classifier import CLASSIFIER, extract_entities

class CustomProvider(BaseLLMProvider):
    def analyze(self, message: str, context: dict) -> dict:
        intent, confidence = CLASSIFIER.predict(message)
        ents = extract_entities(message).as_dict()
        
        return {
            "intent": intent,
            "entities": {
                "origin": ents.get("origin"),
                "destination": ents.get("destination"),
                "departure_date": ents.get("departure_date"),
                "departure_time": None,
                "return_date": ents.get("return_date"),
                "adults": ents.get("adult_count"),
                "children": ents.get("child_count", 0),
                "infants": ents.get("infant_count", 0),
                "cabin_class": ents.get("cabin_class"),
                "trip_type": ents.get("trip_type"),
                "urgency": ents.get("urgency", False)
            },
            "confidence": confidence,
            "needs_human": intent == "human_handoff",
            "natural_reply": ""
        }

    def rewrite_reply(self, reply: str, context: dict) -> str:
        return reply
