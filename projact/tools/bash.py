import os
import sys
import subprocess
import threading
from pathlib import Path
from collections.abc import Callable
from .base import BaseTool, ToolResult
from .sandbox import SandboxConfig, run_sandboxed

DENYLIST_PATTERNS = ['rm -rf /', 'mkfs.', 'dd if=', ':(){ :|:& };:', 'chmod 777 /', '> /dev/sda']

class BashTool(BaseTool):
    name = 'Bash'
    description = 'Execute a shell command. Returns stdout and stderr. Commands run with a configurable timeout. Use for file operations, git commands, running scripts, etc.'
    parameters = {'type': 'object', 'properties': {'command': {'type': 'string', 'description': 'The shell command to execute'}, 'timeout': {'type': 'integer', 'description': 'Timeout in seconds (default 120)', 'default': 120}, 'workdir': {'type': 'string', 'description': 'Working directory for the command'}}, 'required': ['command']}
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, timeout: int=120, workdir: str='.', sandbox_config: SandboxConfig | None=None):
        self._timeout = timeout
        self._workdir = str(Path(workdir).resolve())
        self._sandbox = sandbox_config

    def execute(self, command: str, timeout: int | None=None, workdir: str | None=None, on_output: Callable[[str], None] | None=None) -> ToolResult:
        if self._is_denylisted(command):
            return ToolResult(success=False, output='', error='Command blocked by security policy.')
        timeout = timeout or self._timeout
        cwd = workdir or self._workdir

        # Sandbox path
        if self._sandbox and self._sandbox.enabled:
            exit_code, output = run_sandboxed(command, cwd=cwd, timeout=timeout, config=self._sandbox)
            return ToolResult(
                success=exit_code == 0,
                output=output.strip() or '(no output)',
                error=f'Exit code: {exit_code}' if exit_code != 0 else None,
                metadata={'exit_code': exit_code, 'sandboxed': True},
            )

        # Normal execution with streaming
        try:
            proc = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=cwd, env={**os.environ, 'PAGER': 'cat', 'PYTHONUNBUFFERED': '1'},
                bufsize=1,
            )
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))

        output_parts: list[str] = []

        def _read_stream():
            for line in iter(proc.stdout.readline, ''):
                output_parts.append(line)
                if on_output:
                    try:
                        on_output(line.rstrip('\n'))
                    except Exception:
                        pass

        reader = threading.Thread(target=_read_stream, daemon=True)
        reader.start()

        try:
            proc.wait(timeout=timeout)
            reader.join(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            reader.join(timeout=2)
            output_parts.append(f'\n[Command timed out after {timeout}s]')
            return ToolResult(success=False, output=''.join(output_parts).strip() or '(no output)',
                              error=f'Command timed out after {timeout}s.',
                              metadata={'exit_code': -1})

        output = ''.join(output_parts)
        return ToolResult(
            success=proc.returncode == 0,
            output=output.strip() or '(no output)',
            error=f'Exit code: {proc.returncode}' if proc.returncode != 0 else None,
            metadata={'exit_code': proc.returncode},
        )

    def _is_denylisted(self, command: str) -> bool:
        cmd_clean = command.strip()
        for pattern in DENYLIST_PATTERNS:
            if pattern in cmd_clean:
                return True
        return False
