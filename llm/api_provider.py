import os
import json
import urllib.request
import urllib.error
from llm.base import BaseLLMProvider

class APIProvider(BaseLLMProvider):
    def __init__(self):
        self.provider_type = os.environ.get("LLM_API_PROVIDER", "openrouter").lower()
        self.api_key = os.environ.get("LLM_API_KEY", "").strip()
        self.model = os.environ.get("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct").strip()

        if self.provider_type == "groq":
            self.url = "https://api.groq.com/openai/v1/chat/completions"
            if not self.model or self.model == "meta-llama/llama-3.1-8b-instruct":
                self.model = "llama-3.1-8b-instant"
        else:
            self.url = "https://openrouter.ai/api/v1/chat/completions"

    def analyze(self, message: str, context: dict) -> dict:
        if not self.api_key:
            from llm.custom_provider import CustomProvider
            return CustomProvider().analyze(message, context)

        system_prompt = (
            "You are Aura's travel NLU engine. You are a FLIGHT-FOCUSED assistant.\n"
            "Extract travel intent and entities from user message.\n"
            "Return only valid JSON. Do not write explanation or markdown code block wrapper.\n"
            "Do not confirm booking. Do not invent flights.\n"
            "If information is missing, keep value as null.\n"
            "IMPORTANT: Only help with flight search, flight booking flow, passenger details, "
            "cabin class, seat selection, baggage, web check-in, cancellation/refund and flight support.\n"
            "If user asks unrelated questions (jokes, code, general knowledge, personal chat), "
            "set intent to 'fallback' and natural_reply to a polite redirect to flight help.\n\n"
            "Supported intents:\n"
            "greeting, flight_search, hotel_search, visa_enquiry, insurance, baggage_info, web_checkin, "
            "modify_booking, cancel_booking, refund_status, human_handoff, goodbye, fallback.\n"
            "Supported trip types:\n"
            "one_way, round_trip, multi_city.\n\n"
            "Expected JSON format:\n"
            "{\n"
            '  "intent": "flight_search",\n'
            '  "entities": {\n'
            '    "origin": null,\n'
            '    "destination": null,\n'
            '    "departure_date": null,\n'
            '    "departure_time": null,\n'
            '    "return_date": null,\n'
            '    "adults": null,\n'
            '    "children": 0,\n'
            '    "infants": 0,\n'
            '    "cabin_class": null,\n'
            '    "trip_type": null,\n'
            '    "urgency": false\n'
            "  },\n"
            '  "confidence": 0.0,\n'
            '  "needs_human": false,\n'
            '  "natural_reply": ""\n'
            "}"
        )

        user_content = (
            f"Context: {json.dumps(context)}\n"
            f"User message: {message}\n"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            if self.provider_type != "groq":
                headers["HTTP-Referer"] = "http://localhost:5000"
                headers["X-Title"] = "Aura Travel Assistant"

            timeout = float(os.environ.get("API_TIMEOUT_SECONDS", "4.0"))
            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))

            content = response_data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(content)

            intent = parsed.get("intent", "fallback")
            entities = parsed.get("entities") or {}

            mapped_entities = {
                "origin": entities.get("origin"),
                "destination": entities.get("destination"),
                "departure_date": entities.get("departure_date") or entities.get("date"),
                "departure_time": entities.get("departure_time") or entities.get("time"),
                "return_date": entities.get("return_date"),
                "adults": entities.get("adults") or entities.get("adult_count"),
                "children": entities.get("children", 0) or entities.get("child_count", 0),
                "infants": entities.get("infants", 0) or entities.get("infant_count", 0),
                "cabin_class": entities.get("cabin_class"),
                "trip_type": entities.get("trip_type"),
                "urgency": entities.get("urgency", False)
            }

            return {
                "intent": intent,
                "entities": mapped_entities,
                "confidence": float(parsed.get("confidence", 0.90)),
                "needs_human": parsed.get("needs_human", intent == "human_handoff"),
                "natural_reply": parsed.get("natural_reply") or ""
            }
        except Exception as e:
            print(f"API Provider failed, falling back to CustomProvider: {e}")
            from llm.custom_provider import CustomProvider
            return CustomProvider().analyze(message, context)

    def rewrite_reply(self, reply: str, context: dict) -> str:
        if not self.api_key:
            return reply

        system_prompt = (
            "You are Aura, a flight-focused travel assistant. Rewrite the given plain reply to sound "
            "warm, helpful, concise, and professional. Keep the original facts and values intact. "
            "Do not answer questions outside flight domain. Do not explain your changes."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": reply}
            ],
            "temperature": 0.3
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            if self.provider_type != "groq":
                headers["HTTP-Referer"] = "http://localhost:5000"
                headers["X-Title"] = "Aura Travel Assistant"

            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
            return response_data["choices"][0]["message"]["content"].strip()
        except Exception:
            return reply
