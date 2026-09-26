class BaseLLMProvider:
    def analyze(self, message: str, context: dict) -> dict:
        raise NotImplementedError

    def rewrite_reply(self, reply: str, context: dict) -> str:
        raise NotImplementedError
