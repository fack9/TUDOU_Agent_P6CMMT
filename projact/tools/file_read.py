from pathlib import Path
from .base import BaseTool, ToolResult

class ReadTool(BaseTool):
    name = 'Read'
    description = 'Read a file from the local filesystem. Returns file contents with line numbers (cat -n format). Use offset and limit for reading large files in chunks.'
    parameters = {'type': 'object', 'properties': {'file_path': {'type': 'string', 'description': 'Absolute path to the file to read'}, 'offset': {'type': 'integer', 'description': 'Line number to start reading from (1-based)'}, 'limit': {'type': 'integer', 'description': 'Maximum number of lines to read'}}, 'required': ['file_path']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, max_lines: int=2000, workdir: str='.'):
        self._max_lines = max_lines
        self._workdir = Path(workdir).resolve()

    def execute(self, file_path: str, offset: int | None=None, limit: int | None=None) -> ToolResult:
        path = Path(file_path)
        if not path.is_absolute():
            path = self._workdir / path
        path = path.resolve()
        if not path.exists():
            return ToolResult(success=False, output='', error=f'File not found: {path}')
        if path.is_dir():
            return ToolResult(success=False, output='', error=f'Path is a directory: {path}')
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
        lines = text.split('\n')
        total_lines = len(lines)
        start = offset - 1 if offset else 0
        end = start + limit if limit else len(lines) if offset else self._max_lines
        selected = lines[start:end]
        if not selected:
            return ToolResult(success=True, output='(empty selection or file)', metadata={'lines': 0, 'total_lines': total_lines})
        max_line = min(end, total_lines)
        width = len(str(max_line))
        output = '\n'.join((f'{i + start + 1:>{width}}\t{line}' for i, line in enumerate(selected)))
        truncated = ''
        if end < total_lines:
            remaining = total_lines - end
            truncated = f'\n... [truncated {remaining} lines]'
        return ToolResult(success=True, output=output + truncated, metadata={'lines': len(selected), 'total_lines': total_lines, 'start_line': start + 1, 'end_line': min(end, total_lines), 'path': str(path)})
