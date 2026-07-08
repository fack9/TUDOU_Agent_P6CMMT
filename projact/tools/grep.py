import re
from pathlib import Path
from .base import BaseTool, ToolResult

class GrepTool(BaseTool):
    name = 'Grep'
    description = 'Search for a regex pattern in file contents. Returns matching lines with file path and line number. Use include to filter by file extension or glob pattern.'
    parameters = {'type': 'object', 'properties': {'pattern': {'type': 'string', 'description': 'Regex pattern to search for'}, 'path': {'type': 'string', 'description': 'Directory or file to search in (defaults to working directory)'}, 'include': {'type': 'string', 'description': "File pattern to include (e.g., '*.py', '*.{ts,tsx}')"}}, 'required': ['pattern']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, workdir: str='.', max_results: int=200):
        self._workdir = Path(workdir).resolve()
        self._max_results = max_results

    def execute(self, pattern: str, path: str | None=None, include: str | None=None, on_output=None) -> ToolResult:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, output='', error=f'Invalid regex: {e}')
        target = Path(path).resolve() if path else self._workdir
        if target.is_file():
            return self._grep_file(target, regex, on_output=on_output)
        results = []
        glob_pattern = include or '*'
        file_count = 0
        _streamed = 0
        for file_path in target.rglob(glob_pattern):
            if not file_path.is_file():
                continue
            if len(results) >= self._max_results:
                break
            file_count += 1
            if on_output and file_count % 10 == 0:
                on_output(f'Searching... {file_count} files scanned, {len(results)} matches')
            try:
                text = file_path.read_text(encoding='utf-8', errors='replace')
            except (PermissionError, OSError):
                continue
            for i, line in enumerate(text.split('\n'), 1):
                if regex.search(line):
                    rel_path = file_path.relative_to(target)
                    results.append(f'{rel_path}:{i}: {line.strip()[:200]}')
                    if on_output and _streamed < 2:
                        on_output(f'{rel_path}:{i}: {line.strip()[:120]}')
                        _streamed += 1
                    if len(results) >= self._max_results:
                        break
        if not results:
            return ToolResult(success=True, output='No matches found.', metadata={'count': 0, 'pattern': pattern})
        output = '\n'.join(results)
        if len(results) >= self._max_results:
            output += f'\n... [max {self._max_results} reached]'
        return ToolResult(success=True, output=output, metadata={'count': len(results), 'pattern': pattern})

    def _grep_file(self, path: Path, regex: re.Pattern, on_output=None) -> ToolResult:
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
        results = []
        _streamed = 0
        for i, line in enumerate(text.split('\n'), 1):
            if regex.search(line):
                results.append(f'{i}: {line.strip()[:200]}')
                if on_output and _streamed < 2:
                    on_output(f'{path.name}:{i}: {line.strip()[:120]}')
                    _streamed += 1
                if len(results) >= self._max_results:
                    break
        if not results:
            return ToolResult(success=True, output='No matches found.', metadata={'count': 0})
        return ToolResult(success=True, output=f'--- {path} ---\n' + '\n'.join(results), metadata={'count': len(results), 'file': str(path)})
