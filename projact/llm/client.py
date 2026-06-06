import time
from typing import Any
from config.settings import Settings
from .types import LLMResponse
from .providers.anthropic import AnthropicProvider
from .providers.openai_compat import OpenAICompatProvider

class LLMClient:

    def __init__(self, settings: Settings):
        self._settings = settings
        self._providers: dict[str, Any] = {}
        self._default_model = settings.model
        self._max_retries = settings.get('max_llm_retries', 3)

    def complete(self, messages: list[dict], tools: list[dict] | None=None, model: str | None=None, on_token=None) -> LLMResponse:
        model = model or self._default_model
        provider = self._get_provider(model)

        last_error = None
        for attempt in range(self._max_retries):
            try:
                return provider.complete(messages=messages, tools=tools, model=model, on_token=on_token)
            except Exception as e:
                last_error = e
                if not self._is_retryable(e) or attempt >= self._max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise last_error

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        name = type(error).__name__
        msg = str(error)
        combined = f'{name} {msg}'
        # Rate limits
        if 'RateLimit' in combined or 'rate_limit' in combined.lower() or 'rate limit' in combined.lower() or ' 429 ' in combined:
            return True
        # Server errors
        if 'InternalServer' in combined or 'ServiceUnavailable' in combined:
            return True
        # Timeout / connection
        if 'Timeout' in combined or 'Connection' in combined or 'APIConnection' in combined:
            return True
        # HTTP status check
        status = getattr(error, 'status_code', None) or getattr(error, 'http_status', None) or getattr(error, 'status', None)
        if status is not None:
            return status >= 500 or status == 429
        return False

    def count_tokens(self, messages: list[dict]) -> int:
        provider = self._get_provider(self._default_model)
        return provider.count_tokens(messages)

    def _get_provider(self, model: str):
        if self._is_anthropic_model(model):
            return self._get_anthropic()
        return self._get_openai_compat()

    def _get_anthropic(self):
        if 'anthropic' not in self._providers:
            cfg = self._settings.get('providers', {}).get('anthropic', {})
            self._providers['anthropic'] = AnthropicProvider(api_key=cfg.get('api_key'), base_url=cfg.get('base_url'))
        return self._providers['anthropic']

    def _get_openai_compat(self):
        if 'openai_compat' not in self._providers:
            cfg = self._settings.get('providers', {}).get('openai_compat', {})
            self._providers['openai_compat'] = OpenAICompatProvider(api_key=cfg.get('api_key'), base_url=cfg.get('base_url', 'https://api.openai.com/v1'))
        return self._providers['openai_compat']

    @staticmethod
    def _is_anthropic_model(model: str) -> bool:
        return any((prefix in model.lower() for prefix in ['claude', 'anthropic']))
