import json
import urllib.request
import urllib.error
from llm.base import BaseLLMProvider

class OllamaProvider(BaseLLMProvider):
    def __init__(self):
        self.url = "http://localhost:11434/api/generate"
        self.model = "llama3.2:3b"

    def analyze(self, message: str, context: dict) -> dict:
        system_prompt = (
            "You are Aura's travel NLU engine. Extract travel intent and entities from user message. "
            "Return only valid JSON. Do not write explanation. Do not confirm booking. Do not invent flights. "
            "If information is missing, keep value as null.\n"
            "Supported intents:\n"
            "greeting, flight_search, hotel_search, visa_enquiry, insurance, baggage_info, web_checkin, "
            "modify_booking, cancel_booking, refund_status, human_handoff, goodbye, fallback.\n"
            "Supported trip types:\n"
            "one_way, round_trip, multi_city."
        )
        
        prompt = (
            f"{system_prompt}\n\n"
            f"Context: {json.dumps(context)}\n"
            f"Message: {message}\n"
            f"JSON Response:"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 300}
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            
            raw = body.get("response", "").strip()
            parsed = json.loads(raw)
            
            intent = parsed.get("intent", "fallback")
            conf = 0.90 if intent != "fallback" else 0.20
            
            return {
                "intent": intent,
                "entities": {
                    "origin": parsed.get("origin"),
                    "destination": parsed.get("destination"),
                    "departure_date": parsed.get("departure_date") or parsed.get("date"),
                    "departure_time": parsed.get("departure_time") or parsed.get("time"),
                    "return_date": parsed.get("return_date"),
                    "adults": parsed.get("adult_count") or parsed.get("adults"),
                    "children": parsed.get("child_count", 0) or parsed.get("children", 0),
                    "infants": parsed.get("infant_count", 0) or parsed.get("infants", 0),
                    "cabin_class": parsed.get("cabin_class"),
                    "trip_type": parsed.get("trip_type"),
                    "urgency": parsed.get("urgency", False)
                },
                "confidence": conf,
                "needs_human": intent == "human_handoff",
                "natural_reply": parsed.get("natural_reply") or ""
            }
        except Exception:
            from llm.custom_provider import CustomProvider
            return CustomProvider().analyze(message, context)

    def rewrite_reply(self, reply: str, context: dict) -> str:
        return reply
