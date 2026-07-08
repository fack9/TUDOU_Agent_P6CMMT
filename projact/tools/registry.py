import json
from dataclasses import dataclass
from typing import Any, Callable
from .base import BaseTool, ToolResult

@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., ToolResult]
    permission_level: str = 'safe'
    is_read_only: bool = True

    def to_openai_schema(self) -> dict:
        return {'type': 'function', 'function': {'name': self.name, 'description': self.description, 'parameters': self.parameters}}

class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable[..., ToolResult], permission_level: str='safe', is_read_only: bool=True):
        self._tools[name] = ToolDef(name=name, description=description, parameters=parameters, handler=handler, permission_level=permission_level, is_read_only=is_read_only)

    def register_tool(self, tool: BaseTool):
        if tool.name in self._tools:
            import sys
            print('[WARN] Tool "{}" is being overwritten by a newer registration'.format(tool.name), file=sys.stderr)
        self._tools[tool.name] = ToolDef(name=tool.name, description=tool.description, parameters=tool.parameters, handler=tool.execute, permission_level=tool.permission_level, is_read_only=tool.is_read_only)

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict, on_output=None) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, output='', error=f'Unknown tool: {name}')
        try:
            try:
                return tool.handler(**arguments, on_output=on_output)
            except TypeError:
                return tool.handler(**arguments)
        except Exception as e:
            args_preview = json.dumps(arguments, ensure_ascii=False, default=str)
            if len(args_preview) > 500:
                args_preview = args_preview[:500] + '...'
            return ToolResult(
                success=False,
                output='',
                error=f'{type(e).__name__}: {e}\n\n[Called: {name}({args_preview})]',
            )

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def tool_count(self) -> int:
        return len(self._tools)
