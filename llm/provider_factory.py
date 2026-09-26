import os
from llm.custom_provider import CustomProvider
from llm.ollama_provider import OllamaProvider
from llm.api_provider import APIProvider

def get_provider():
    provider_type = os.environ.get("LLM_PROVIDER", "custom").lower().strip()
    if provider_type == "api":
        return APIProvider()
    elif provider_type == "ollama":
        return OllamaProvider()
    else:
        return CustomProvider()
