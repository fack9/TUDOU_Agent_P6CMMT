from abc import ABC, abstractmethod
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict | None = None
    images: list[dict] | None = None

class BaseTool(ABC):
    name: str = ''
    description: str = ''
    parameters: dict = None
    permission_level: str = 'safe'
    is_read_only: bool = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.parameters is None:
            cls.parameters = {'type': 'object', 'properties': {}}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...

    def to_openai_schema(self) -> dict:
        return {'type': 'function', 'function': {'name': self.name, 'description': self.description, 'parameters': self.parameters}}

    def to_anthropic_schema(self) -> dict:
        return {'name': self.name, 'description': self.description, 'input_schema': self.parameters}
