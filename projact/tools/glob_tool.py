from pathlib import Path
from .base import BaseTool, ToolResult

class GlobTool(BaseTool):
    name = 'Glob'
    description = 'Find files matching a glob pattern. Use ** for recursive directory matching. Returns relative file paths.'
    parameters = {'type': 'object', 'properties': {'pattern': {'type': 'string', 'description': "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')"}, 'path': {'type': 'string', 'description': 'Directory to search from (defaults to working directory)'}}, 'required': ['pattern']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, workdir: str='.', max_results: int=500):
        self._workdir = Path(workdir).resolve()
        self._max_results = max_results

    def execute(self, pattern: str, path: str | None=None) -> ToolResult:
        base = Path(path).resolve() if path else self._workdir
        if not base.exists():
            return ToolResult(success=False, output='', error=f'Directory not found: {base}')
        results = []
        for match in base.glob(pattern):
            if len(results) >= self._max_results:
                break
            results.append(str(match.relative_to(base)))
        if not results:
            return ToolResult(success=True, output='No files matched.', metadata={'count': 0, 'pattern': pattern})
        output = '\n'.join(results)
        truncated = ''
        if len(results) >= self._max_results:
            truncated = f'\n... [truncated at {self._max_results} results]'
        return ToolResult(success=True, output=output + truncated, metadata={'count': len(results), 'pattern': pattern})
