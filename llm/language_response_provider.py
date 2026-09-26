import os
import json
import urllib.request
import urllib.error
import logging

log = logging.getLogger("aura.llm.language")

class LanguageResponseProvider:
    def __init__(self):
        self.provider_type = os.environ.get("LLM_API_PROVIDER", "openrouter").lower()
        self.api_key = os.environ.get("LLM_API_KEY", "").strip()
        self.model = os.environ.get("LLM_MODEL", "qwen/qwen-2.5-7b-instruct").strip()

        if self.provider_type == "groq":
            self.url = "https://api.groq.com/openai/v1/chat/completions"
        else:
            self.url = "https://openrouter.ai/api/v1/chat/completions"

    def process_reply(self, user_message: str, bot_reply: str, current_language: str, intent: str, state: dict) -> dict:
        if not self.api_key:
            return {
                "language": current_language,
                "reply": bot_reply,
                "language_switched": False
            }

        system_prompt = (
            "You are Aura's language response controller for a flight-focused chatbot.\n\n"
            "Your job:\n"
            "1. Detect the language/style the user wants.\n"
            "2. Detect if the user is asking to switch language.\n"
            "3. Rewrite the provided bot reply in the user's preferred language.\n"
            "4. Keep the meaning exactly the same.\n"
            "5. Do not change intent, entities, flight data, prices, dates, passengers, or booking state.\n"
            "6. Do not answer outside the flight domain.\n"
            "7. Return only valid JSON.\n\n"
            "Supported languages:\n"
            "- en = English\n"
            "- ta = Tamil script\n"
            "- ta-en = Tanglish\n"
            "- hi = Hindi script\n"
            "- hi-en = Hinglish\n"
            "- kn = Kannada script\n"
            "- kn-en = Kannada-English\n"
            "- te = Telugu script\n"
            "- te-en = Telugu-English\n"
            "- ml = Malayalam script\n"
            "- ml-en = Malayalam-English\n\n"
            "If user asks to change language, set language_switched=true.\n"
            "If user does not ask to change language, keep current language preference unless user clearly types in another language.\n\n"
            "Return JSON only:\n"
            "{\n"
            '  "language": "...",\n'
            '  "reply": "...",\n'
            '  "language_switched": true/false\n'
            "}"
        )

        user_content = json.dumps({
            "user_message": user_message,
            "current_language": current_language,
            "intent": intent,
            "bot_reply": bot_reply,
            "workflow_state": state
        })

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

            timeout = float(os.environ.get("API_TIMEOUT_SECONDS", "3.0"))
            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))

            content = response_data["choices"][0]["message"]["content"].strip()
            # Handle potential markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            
            # Fallback for missing keys
            return {
                "language": parsed.get("language", current_language),
                "reply": parsed.get("reply", bot_reply),
                "language_switched": bool(parsed.get("language_switched", False))
            }
        except Exception as e:
            log.error("Language API failed: %s", e)
            return {
                "language": current_language,
                "reply": bot_reply,
                "language_switched": False
            }
