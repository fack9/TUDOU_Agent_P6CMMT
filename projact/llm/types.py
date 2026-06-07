from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

StreamCallback = Callable[[str], None]

@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ''
    finish_reason: str = ''
    reasoning_content: str = ''

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
