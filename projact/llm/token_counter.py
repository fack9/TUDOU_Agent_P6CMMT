from dataclasses import dataclass
from functools import lru_cache

# Known model context limits. Prefer API-based detection when available.
# Values are the maximum input tokens (context window size).
MODEL_TOKEN_LIMITS: dict[str, int] = {
    # Anthropic Claude
    'claude-opus-4-7': 200000, 'claude-opus-4-6': 200000, 'claude-opus-4-5': 200000,
    'claude-opus-4': 200000, 'claude-opus': 200000,
    'claude-sonnet-4-6': 200000, 'claude-sonnet-4-5': 200000,
    'claude-sonnet-4': 200000, 'claude-sonnet': 200000,
    'claude-haiku-4-5': 200000, 'claude-haiku': 200000,
    'claude-3.5-sonnet': 200000, 'claude-3.5-haiku': 200000,
    'claude-3-opus': 200000, 'claude-3-sonnet': 200000, 'claude-3-haiku': 200000,
    'claude': 200000,
    # OpenAI
    'gpt-5': 128000, 'gpt-4.1': 1048576, 'gpt-4o': 128000, 'gpt-4-turbo': 128000,
    'gpt-4': 8192, 'gpt-3.5-turbo': 16385, 'gpt-3.5': 16385,
    # DeepSeek
    'deepseek-v4': 1000000, 'deepseek-v3': 128000, 'deepseek-r1': 128000,
    'deepseek-r1-0528': 128000, 'deepseek': 128000,
    # Gemini
    'gemini-2.5-pro': 1048576, 'gemini-2.5-flash': 1048576,
    'gemini-2.0-flash': 1048576, 'gemini': 128000,
    # Qwen
    'qwen3': 262144, 'qwen2.5': 128000, 'qwen': 128000,
    # Llama / Mistral / Other
    'llama-4': 262144, 'llama-3': 128000, 'llama': 128000,
    'mistral': 128000, 'mixtral': 128000,
    # Fallback
    'default': 128000,
}

def get_model_token_limit(model: str) -> int:
    """Get the context window size for a model. Tries exact match, then prefix match."""
    model_lower = model.lower()
    # Try exact match first (longest key wins if overlapping)
    for prefix in sorted(MODEL_TOKEN_LIMITS.keys(), key=len, reverse=True):
        if prefix == 'default':
            continue
        if prefix in model_lower:
            return MODEL_TOKEN_LIMITS[prefix]
    return MODEL_TOKEN_LIMITS['default']

@lru_cache(maxsize=8)
def _cached_api_limit(base_url: str, api_key: str, model: str) -> int | None:
    """Try to query the API for the model's actual context limit. Returns None if unavailable."""
    try:
        import urllib.request, json, ssl
        url = f'{base_url.rstrip("/")}/models'
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'TUDOU_agent',
        })
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=5)
        data = json.loads(resp.read().decode())
        # Response format: {"data": [{"id": "model-name", "max_tokens": 128000}, ...]}
        models = data.get('data', []) if isinstance(data, dict) else []
        if not models and isinstance(data, list):
            models = data
        for m in models:
            if m.get('id', '') == model:
                limit = m.get('max_tokens') or m.get('context_window') or m.get('max_input_tokens')
                if limit and isinstance(limit, (int, float)) and limit > 0:
                    return int(limit)
    except Exception:
        pass
    return None

def try_get_model_limit(model: str, provider: str = 'openai_compat', base_url: str = '',
                         api_key: str = '') -> int:
    """Get model limit: API query first, then hardcoded fallback."""
    if provider == 'openai_compat' and base_url and api_key:
        api_limit = _cached_api_limit(base_url, api_key, model)
        if api_limit:
            return api_limit
    return get_model_token_limit(model)

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
