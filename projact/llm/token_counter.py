from dataclasses import dataclass
MODEL_TOKEN_LIMITS: dict[str, int] = {'claude-opus': 180000, 'claude-sonnet': 180000, 'claude-haiku': 90000, 'claude': 180000, 'gpt-4': 128000, 'gpt-4o': 128000, 'gpt-3.5': 16000, 'deepseek': 128000, 'default': 128000}

def get_model_token_limit(model: str) -> int:
    model_lower = model.lower()
    for prefix, limit in MODEL_TOKEN_LIMITS.items():
        if prefix in model_lower:
            return limit
    return MODEL_TOKEN_LIMITS['default']

@dataclass
class TokenBudget:
    max_tokens: int = 180000
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used)

    @property
    def usage_ratio(self) -> float:
        return self.used / self.max_tokens if self.max_tokens > 0 else 0

    def near_limit(self, threshold: float=0.85) -> bool:
        return self.usage_ratio >= threshold

    def add(self, tokens: int):
        self.used += tokens

class TokenCounter:

    def __init__(self, provider):
        self._provider = provider

    def count(self, messages: list[dict]) -> int:
        return self._provider.count_tokens(messages)

    @staticmethod
    def estimate_chars(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def estimate_messages(messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += len(str(block)) // 4
        return total
