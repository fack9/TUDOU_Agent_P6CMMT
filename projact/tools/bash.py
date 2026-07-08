import os
import sys
import subprocess
import threading
from pathlib import Path
from collections.abc import Callable
from .base import BaseTool, ToolResult
from .sandbox import SandboxConfig, run_sandboxed

DENYLIST_PATTERNS = ['rm -rf /', 'mkfs.', 'dd if=', ':(){ :|:& };:', 'chmod 777 /', '> /dev/sda']

# Directory-listing commands — suppress output, just show "Done" on success
_LISTING_CMDS = {'dir', 'ls', 'tree', 'll', 'la', 'gci', 'Get-ChildItem', 'list'}

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

        # Normal execution with streaming (stdout) + separate stderr capture
        try:
            proc = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace', cwd=cwd,
                env={**os.environ, 'PAGER': 'cat', 'PYTHONUNBUFFERED': '1'},
                bufsize=1,
            )
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))

        _is_listing = self._is_listing_cmd(command)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        def _read_stdout():
            try:
                for line in iter(proc.stdout.readline, ''):
                    stdout_parts.append(line)
                    if on_output and not _is_listing:
                        try:
                            on_output(line.rstrip('\n'))
                        except Exception:
                            pass
            except Exception:
                pass

        def _read_stderr():
            try:
                for line in iter(proc.stderr.readline, ''):
                    stderr_parts.append(line)
                    if on_output and not _is_listing:
                        try:
                            on_output(line.rstrip('\n'), 'stderr')
                        except Exception:
                            pass
            except Exception:
                pass

        stdout_reader = threading.Thread(target=_read_stdout, daemon=True)
        stderr_reader = threading.Thread(target=_read_stderr, daemon=True)
        stdout_reader.start()
        stderr_reader.start()

        try:
            proc.wait(timeout=timeout)
            stdout_reader.join(timeout=5)
            stderr_reader.join(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_reader.join(timeout=2)
            stderr_reader.join(timeout=2)
            stdout_parts.append(f'\n[Command timed out after {timeout}s]')
            return ToolResult(success=False, output=''.join(stdout_parts).strip() or '(no output)',
                              error=f'Command timed out after {timeout}s.',
                              metadata={'exit_code': -1})

        stdout_text = ''.join(stdout_parts).strip()
        stderr_text = ''.join(stderr_parts).strip()

        if proc.returncode == 0:
            if self._is_listing_cmd(command):
                return ToolResult(success=True, output='Done.', metadata={'exit_code': 0})
            output = stdout_text or '(no output)'
            if stderr_text:
                output += f'\n\n[stderr]\n{stderr_text}'
            return ToolResult(
                success=True,
                output=output,
                metadata={'exit_code': 0},
            )
        else:
            output = stdout_text or '(no stdout)'
            error_msg = f'Exit code: {proc.returncode}'
            if stderr_text:
                error_msg += f'\n\n[stderr]\n{stderr_text}'
            elif stdout_text:
                error_msg += f'\n\n[stdout]\n{stdout_text[:2000]}'
            return ToolResult(
                success=False,
                output=output,
                error=error_msg,
                metadata={'exit_code': proc.returncode},
            )

    def _is_denylisted(self, command: str) -> bool:
        cmd_clean = command.strip()
        for pattern in DENYLIST_PATTERNS:
            if pattern in cmd_clean:
                return True
        return False

    def _is_listing_cmd(self, command: str) -> bool:
        """Check if command is a directory-listing/search command."""
        first_word = command.strip().split()[0] if command.strip() else ''
        # Handle Windows: cmd /c dir, cmd /c tree
        if first_word in ('cmd',):
            parts = command.strip().split()
            for i, p in enumerate(parts):
                if p in ('/c', '/C') and i + 1 < len(parts):
                    first_word = parts[i + 1]
                    break
        return first_word in _LISTING_CMDS
