from llm.token_counter import TokenBudget, get_model_token_limit
from llm.types import TokenUsage

class TokenTracker:

    def __init__(self, model: str='default', max_tokens: int | None=None, compress_threshold: float=0.75, urgent_threshold: float=0.9, max_tool_result_chars: int=15000, max_history_turns: int=50):
        self.model = model
        effective_max = max_tokens or get_model_token_limit(model)
        self.budget = TokenBudget(max_tokens=effective_max)
        self.compress_threshold = compress_threshold
        self.urgent_threshold = urgent_threshold
        self.max_tool_result_chars = max_tool_result_chars
        self.max_history_turns = max_history_turns
        self.cumulative_input = 0
        self.cumulative_output = 0
        self.cumulative_cache_read = 0
        self.cumulative_cache_write = 0
        self.compression_count = 0
        self._msg_hash: int = -1
        self._cached_estimate: int = 0
        self._last_ratio: float = 0.0

    def update_after_llm_call(self, usage: TokenUsage):
        self.cumulative_input += usage.input
        self.cumulative_output += usage.output
        self.cumulative_cache_read += usage.cache_read
        self.cumulative_cache_write += usage.cache_write
        self.budget.add(usage.input)

    def estimate_messages(self, messages: list[dict]) -> int:
        h = self._hash_messages(messages)
        if h == self._msg_hash:
            return self._cached_estimate
        self._msg_hash = h
        self._cached_estimate = self._rough_estimate(messages)
        return self._cached_estimate

    def invalidate_cache(self):
        self._msg_hash = -1

    def remaining(self) -> int:
        return max(0, self.budget.remaining)

    def usage_ratio(self) -> float:
        # Return the latest per-turn estimate ratio (not cumulative)
        return self._last_ratio

    def should_compress(self, messages: list[dict], turn_count: int) -> tuple[bool, bool]:
        est = self.estimate_messages(messages)
        ratio = est / self.budget.max_tokens if self.budget.max_tokens else 0
        self._last_ratio = ratio  # per-turn ratio for accurate display
        urgent = ratio >= self.urgent_threshold
        if urgent:
            return (True, True)
        if ratio >= self.compress_threshold:
            return (True, False)
        if len(messages) > self.max_history_turns * 2:
            return (True, False)
        return (False, False)

    @staticmethod
    def truncate_tool_result(content: str, max_chars: int=15000) -> str:
        if len(content) <= max_chars:
            return content
        from .content_compressor import compress_content
        return compress_content(content, max_chars)

    @staticmethod
    def _hash_messages(messages: list[dict]) -> int:
        parts: list[int] = []
        for m in messages:
            parts.append(hash(m.get('role', '')))
            content = m.get('content', '')
            if isinstance(content, str):
                parts.append(len(content))
            elif isinstance(content, list):
                parts.append(len(content))
            else:
                parts.append(0)
            if m.get('tool_calls'):
                parts.append(1)
        return hash(tuple(parts))

    @staticmethod
    def _rough_estimate(messages: list[dict]) -> int:
        total = 0
        for m in messages:
            content = m.get('content', '')
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += len(str(block))
            if m.get('tool_calls'):
                total += 200
        return total // 4
