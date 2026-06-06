from pathlib import Path
from .base import BaseTool, ToolResult

class EditTool(BaseTool):
    name = 'Edit'
    description = 'Perform exact string replacement in an existing file. When replace_all=False (default), old_string must be unique in the file. When replace_all=True, all occurrences are replaced.'
    parameters = {'type': 'object', 'properties': {'file_path': {'type': 'string', 'description': 'Absolute path to the file to edit'}, 'old_string': {'type': 'string', 'description': 'The exact text to replace'}, 'new_string': {'type': 'string', 'description': 'The text to replace it with'}, 'replace_all': {'type': 'boolean', 'description': 'Replace all occurrences (default false)', 'default': False}}, 'required': ['file_path', 'old_string', 'new_string']}
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, workdir: str='.'):
        self._workdir = Path(workdir).resolve()

    def execute(self, file_path: str, old_string: str, new_string: str, replace_all: bool=False) -> ToolResult:
        if old_string == new_string:
            return ToolResult(success=False, output='', error='old_string and new_string are identical')
        path = Path(file_path)
        if not path.is_absolute():
            path = self._workdir / path
        path = path.resolve()
        if not path.exists():
            return ToolResult(success=False, output='', error=f'File not found: {path}')
        try:
            text = path.read_text(encoding='utf-8')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
        count = text.count(old_string)
        if count == 0:
            return ToolResult(success=False, output='', error='old_string not found in file')
        if count > 1 and (not replace_all):
            return ToolResult(success=False, output='', error=f'old_string appears {count} times in the file. Use replace_all=True to replace all occurrences, or provide more context to make it unique.')
        new_text = text.replace(old_string, new_string)
        try:
            path.write_text(new_text, encoding='utf-8')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
        occurrences = count if replace_all else 1
        return ToolResult(success=True, output=f'Replaced {occurrences} occurrence(s) in {path}', metadata={'path': str(path), 'occurrences': occurrences})
