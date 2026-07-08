from __future__ import annotations
import json
import subprocess
import threading
import yaml
import re
from pathlib import Path
from .types import HookEvent, Hook


class HookManager:

    def __init__(self, hooks_dir: str | None = None, cwd: str = '.'):
        self._hooks: dict[HookEvent, list[tuple[Hook, str | None]]] = {}
        self._cwd = str(Path(cwd).resolve())
        if hooks_dir:
            self.load_dir(hooks_dir)

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    def load_dir(self, dir_path: str) -> int:
        """Load all .yaml files from *dir_path*. Returns count of loaded hooks."""
        d = Path(dir_path)
        if not d.is_dir():
            return 0
        total = 0
        for yf in sorted(d.glob('*.yaml')):
            total += self._load_file(yf)
        return total

    def _load_file(self, path: Path) -> int:
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
        except Exception:
            return 0
        if not data or 'hooks' not in data:
            return 0

        doing_path = data.get('doing_path')
        if doing_path:
            doing_path = str(Path(str(doing_path).replace('\\\\', '/')).resolve())

        count = 0
        for entry in data['hooks']:
            try:
                event = HookEvent(entry['event'])
                blocking = entry.get('blocking', False)
                command = entry['command']
                timeout = entry.get('timeout', 10)
                hook = Hook(event=event, command=command, blocking=blocking, timeout=timeout)
                self._hooks.setdefault(event, []).append((hook, doing_path))
                count += 1
            except (KeyError, ValueError):
                continue
        return count

    # ------------------------------------------------------------------
    # fire
    # ------------------------------------------------------------------

    def fire(self, event: HookEvent | str, **context) -> bool:
        """Fire all hooks for *event*. Returns False if a blocking hook fails.

        Project-specific hooks (with ``doing_path``) are silently skipped
        when the current working directory does not match.
        """
        if isinstance(event, str):
            event = HookEvent(event)
        entries = self._hooks.get(event, [])
        if not entries:
            return True

        # Filter by doing_path
        active = []
        for hook, doing_path in entries:
            if doing_path and doing_path != self._cwd:
                continue
            active.append(hook)

        if not active:
            return True

        blocking_hooks = [h for h in active if h.blocking]
        nonblocking_hooks = [h for h in active if not h.blocking]

        for hook in nonblocking_hooks:
            t = threading.Thread(target=self._run_hook, args=(hook, context), daemon=True)
            t.start()

        for hook in blocking_hooks:
            if not self._run_hook(hook, context):
                return False

        return True

    def _run_hook(self, hook: Hook, context: dict) -> bool:
        cmd = self._substitute(hook.command, context)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=hook.timeout,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    @staticmethod
    def _substitute(template: str, context: dict) -> str:
        def _replace(m):
            key = m.group(1)
            val = context.get(key, '')
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)
        return re.sub(r'\{(\w+)\}', _replace, template)

    # ------------------------------------------------------------------
    # info
    # ------------------------------------------------------------------

    @property
    def hook_count(self) -> int:
        return sum(len(v) for v in self._hooks.values())
