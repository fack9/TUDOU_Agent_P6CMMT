import shutil
import subprocess
import os
from pathlib import Path
from .base import BaseTool, ToolResult


class SoftwareCLITool(BaseTool):
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, software_name: str, command_spec: str, exe_path: str | None = None):
        self._software = software_name
        self._exe = exe_path or shutil.which(software_name) or software_name
        self._spec = command_spec
        self.name = f'{software_name}_cli'
        self.description = (
            f'Execute {software_name} commands via CLI. '
            f'This tool wraps the "{software_name}" command-line program. '
            f'{command_spec}'
        )
        self.parameters = {
            'type': 'object',
            'properties': {
                'command': {
                    'type': 'string',
                    'description': f'The {software_name} command to execute (e.g. "{software_name} --help")',
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Timeout in seconds (default 120)',
                    'default': 120,
                },
            },
            'required': ['command'],
        }

    def execute(self, command: str, timeout: int = 120) -> ToolResult:
        if not Path(self._exe).is_file():
            return ToolResult(success=False, output='', error=f'{self._software}: executable not found at {self._exe}. It may have been moved or the session was restarted.')

        cmd = f'{self._exe} {command}' if not command.startswith(self._exe) else command
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env={**os.environ, 'PAGER': 'cat'})
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output='', error=f'Command timed out after {timeout}s.')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))

        output = proc.stdout
        if proc.stderr:
            output += f'\n[stderr]\n{proc.stderr}'
        return ToolResult(
            success=proc.returncode == 0,
            output=output.strip() or '(no output)',
            error=f'Exit code: {proc.returncode}' if proc.returncode != 0 else None,
            metadata={'exit_code': proc.returncode},
        )
