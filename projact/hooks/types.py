from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field


class HookEvent(Enum):
    ON_AGENT_START = 'on_agent_start'
    ON_AGENT_STOP = 'on_agent_stop'
    ON_TOOL_BEFORE = 'on_tool_before'
    ON_TOOL_AFTER = 'on_tool_after'
    ON_COMPRESS = 'on_compress'


@dataclass
class Hook:
    event: HookEvent
    command: str
    blocking: bool = False  # True = can block the triggering action
    timeout: int = 10       # seconds
