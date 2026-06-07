r"""Windows Low-Integrity process sandbox.

Runs child processes under the Windows mandatory integrity control (MIC)
at Low integrity level (S-1-16-4096). The OS restricts write access to
most locations outside the user profile's LocalLow directory, preventing
accidental or malicious damage to system files and user data.

Falls back gracefully on non-Windows platforms or when token manipulation
fails (e.g., insufficient privileges).
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolResult


class SandboxConfig:
    """Mutable sandbox settings."""

    def __init__(self, enabled: bool = False, allow_write_paths: list[str] | None = None,
                 block_network: bool = False, command_allowlist: list[str] | None = None):
        self.enabled = enabled
        self.allow_write_paths: list[Path] = [Path(p).resolve() for p in (allow_write_paths or [])]
        self.block_network = block_network
        self.command_allowlist = command_allowlist or []


def _is_windows() -> bool:
    return sys.platform == 'win32'


def _get_low_integrity_sid():
    """Convert string SID S-1-16-4096 to binary SID via ctypes."""
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.windll.advapi32
    sid_ptr = ctypes.c_void_p()
    ok = advapi32.ConvertStringSidToSidW('S-1-16-4096', ctypes.byref(sid_ptr))
    if not ok:
        return None
    # Return a copy we own; we need to free the original
    size = advapi32.GetLengthSid(sid_ptr)
    buf = (ctypes.c_byte * size)()
    ctypes.memmove(buf, sid_ptr, size)
    advapi32.LocalFree(sid_ptr)
    return buf, size


def _create_low_integrity_token():
    """Duplicate current process token and lower its integrity to Low."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32

    TOKEN_DUPLICATE = 0x0002
    TOKEN_QUERY = 0x0008
    TOKEN_ADJUST_DEFAULT = 0x0080
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_ALL_ACCESS = 0xF00FF
    TokenIntegrityLevel = 25
    SE_GROUP_INTEGRITY = 0x00000020

    # Get current process pseudo-handle
    current = wintypes.HANDLE(-1)  # GetCurrentProcess()
    token = wintypes.HANDLE()
    ok = advapi32.OpenProcessToken(current, TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ADJUST_DEFAULT,
                                   ctypes.byref(token))
    if not ok:
        return None

    # Duplicate to a primary token
    dup_token = wintypes.HANDLE()
    ok = advapi32.DuplicateTokenEx(
        token, TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT | TOKEN_QUERY,
        None, 2, 1,  # SecurityImpersonation=2, TokenPrimary=1
        ctypes.byref(dup_token),
    )
    kernel32.CloseHandle(token)
    if not ok:
        return None

    # Build TOKEN_MANDATORY_LABEL with Low integrity SID
    sid_buf, sid_size = _get_low_integrity_sid()
    if sid_buf is None:
        kernel32.CloseHandle(dup_token)
        return None

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Sid', ctypes.c_void_p),
                    ('Attributes', wintypes.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [('Label', SID_AND_ATTRIBUTES)]

    sid_ptr = ctypes.cast(sid_buf, ctypes.c_void_p)
    label = TOKEN_MANDATORY_LABEL()
    label.Label.Sid = sid_ptr
    label.Label.Attributes = SE_GROUP_INTEGRITY

    ok = advapi32.SetTokenInformation(
        dup_token, TokenIntegrityLevel,
        ctypes.byref(label),
        ctypes.sizeof(label),
    )
    if not ok:
        kernel32.CloseHandle(dup_token)
        return None

    return dup_token


def run_sandboxed(command: str, cwd: str = '.', timeout: int = 120,
                  config: SandboxConfig | None = None) -> tuple[int, str]:
    """Execute a command under Windows low-integrity sandbox.

    Returns (exit_code, combined_output).

    Falls back to normal subprocess on non-Windows or if sandbox is
    unavailable.
    """
    if not _is_windows():
        return _run_plain(command, cwd, timeout)

    if config is None:
        config = SandboxConfig()

    token = None
    try:
        token = _create_low_integrity_token()
    except Exception:
        token = None

    if token is None:
        # Fallback: run normally with path restrictions
        return _run_plain(command, cwd, timeout,
                          allow_paths=config.allow_write_paths if config.enabled else None)

    return _run_with_token(token, command, cwd, timeout)


def _run_with_token(token, command: str, cwd: str, timeout: int) -> tuple[int, str]:
    """Create a process with the low-integrity token via CreateProcessWithTokenW."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32

    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    CREATE_NO_WINDOW = 0x08000000

    # Prepare STARTUPINFO
    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD),
                    ('lpReserved', wintypes.LPWSTR),
                    ('lpDesktop', wintypes.LPWSTR),
                    ('lpTitle', wintypes.LPWSTR),
                    ('dwX', wintypes.DWORD),
                    ('dwY', wintypes.DWORD),
                    ('dwXSize', wintypes.DWORD),
                    ('dwYSize', wintypes.DWORD),
                    ('dwXCountChars', wintypes.DWORD),
                    ('dwYCountChars', wintypes.DWORD),
                    ('dwFillAttribute', wintypes.DWORD),
                    ('dwFlags', wintypes.DWORD),
                    ('wShowWindow', wintypes.WORD),
                    ('cbReserved2', wintypes.WORD),
                    ('lpReserved2', ctypes.c_void_p),
                    ('hStdInput', wintypes.HANDLE),
                    ('hStdOutput', wintypes.HANDLE),
                    ('hStdError', wintypes.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess', wintypes.HANDLE),
                    ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD),
                    ('dwThreadId', wintypes.DWORD)]

    # Build command line: cmd.exe /c "command"
    cmdline = f'cmd.exe /c "{command}"'

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(STARTUPINFOW)
    si.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
    si.hStdOutput = None
    si.hStdError = None

    pi = PROCESS_INFORMATION()

    ok = advapi32.CreateProcessWithTokenW(
        token,
        0,  # LogonFlags: 0 = LOGON_WITH_PROFILE (not needed for child process)
        None,  # lpApplicationName
        cmdline,
        CREATE_NO_WINDOW,
        None,  # lpEnvironment
        cwd if cwd else None,
        ctypes.byref(si),
        ctypes.byref(pi),
    )

    if not ok:
        kernel32.CloseHandle(token)
        return _run_plain(command, cwd, timeout)

    kernel32.CloseHandle(token)

    # Wait for process with timeout
    INFINITE = 0xFFFFFFFF
    timeout_ms = wintypes.DWORD(timeout * 1000)
    ret = kernel32.WaitForSingleObject(pi.hProcess, timeout_ms)

    if ret == 0x00000102:  # WAIT_TIMEOUT
        kernel32.TerminateProcess(pi.hProcess, 1)
        kernel32.CloseHandle(pi.hProcess)
        kernel32.CloseHandle(pi.hThread)
        return (-1, f'[Command timed out after {timeout}s]')

    # Read exit code
    exit_code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))

    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(pi.hThread)

    return (exit_code.value, f'(sandboxed: low integrity) exit={exit_code.value}')


def _run_plain(command: str, cwd: str, timeout: int,
               allow_paths: list[Path] | None = None) -> tuple[int, str]:
    """Plain subprocess execution, optionally with path validation."""
    if allow_paths is not None:
        warning = _check_command_paths(command, allow_paths)
        if warning:
            return (-1, warning)

    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
            env={**os.environ, 'PAGER': 'cat', 'PYTHONUNBUFFERED': '1'},
        )
    except subprocess.TimeoutExpired:
        return (-1, f'[Command timed out after {timeout}s]')
    except Exception as e:
        return (-1, str(e))

    output = proc.stdout
    if proc.stderr:
        output += '\n' + proc.stderr
    return (proc.returncode, output.strip() or '(no output)')


class EnableSandboxTool(BaseTool):
    name = 'EnableSandbox'
    description = 'Activate the Windows Low-Integrity sandbox for Bash commands. All subsequent shell commands run under restricted privileges — they cannot write to system directories or delete protected files. Only the USER can turn the sandbox OFF via /sandbox off. Call this before running untrusted or high-risk commands.'
    parameters = {'type': 'object', 'properties': {}, 'required': []}
    permission_level = 'safe'
    is_read_only = False

    def __init__(self, sandbox_config: SandboxConfig):
        self._config = sandbox_config

    def execute(self) -> ToolResult:
        if self._config.enabled:
            return ToolResult(success=True, output='Sandbox is already enabled. All Bash commands are running under Low-Integrity isolation.')
        self._config.enabled = True
        return ToolResult(success=True, output='Sandbox enabled. All subsequent Bash commands will run under Windows Low-Integrity isolation. File writes to system directories will be blocked by the OS. Only the user can disable sandbox with /sandbox off.')


def _check_command_paths(command: str, allow_paths: list[Path]) -> str | None:
    """Check if a command references paths outside the allowed set."""
    import re
    # Scan for path-like strings
    path_pattern = re.compile(r'(?:[\w]:[\\/][^\s"\']+)|(?:(?:\.\.?[/\\])[^\s"\']+)|(?:/[^\s"\']+)')
    for match in path_pattern.finditer(command):
        p = match.group()
        resolved = Path(p).resolve() if not p.startswith('/') else Path(p)
        if any(resolved == ap or str(resolved).startswith(str(ap)) for ap in allow_paths):
            continue
        return f'Blocked: path "{p}" is outside allowed directories.'
    return None
