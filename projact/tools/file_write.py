from pathlib import Path
from .base import BaseTool, ToolResult

class WriteTool(BaseTool):
    name = 'Write'
    description = 'Write a file to the local filesystem. Creates parent directories as needed. Overwrites existing files.'
    parameters = {'type': 'object', 'properties': {'file_path': {'type': 'string', 'description': 'Absolute path to write the file to'}, 'content': {'type': 'string', 'description': 'Content to write to the file'}}, 'required': ['file_path', 'content']}
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, workdir: str='.'):
        self._workdir = Path(workdir).resolve()

    def execute(self, file_path: str, content: str) -> ToolResult:
        path = Path(file_path)
        if not path.is_absolute():
            path = self._workdir / path
        path = path.resolve()
        existed = path.exists()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
        verb = 'Updated' if existed else 'Created'
        line_count = content.count('\n') + 1
        return ToolResult(success=True, output=f'{verb} {path} ({line_count} lines, {len(content)} chars)', metadata={'path': str(path), 'lines': line_count, 'chars': len(content), 'existed': existed})
