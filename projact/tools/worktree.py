import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from .base import BaseTool, ToolResult


class WorkdirRef:
    """Mutable reference to the active working directory."""

    def __init__(self, path: Path):
        self.path = path

    def __str__(self) -> str:
        return str(self.path)

    def __fspath__(self) -> str:
        return str(self.path)


@dataclass
class WorktreeInfo:
    path: str
    branch: str
    bare: bool = False
    locked: bool = False
    prunable: str = ''


class WorktreeManager:
    """Manages git worktree lifecycle for isolated operations."""

    def __init__(self, repo_root: Path, worktrees_dir: Path):
        self._repo_root = Path(repo_root).resolve()
        self._worktrees_dir = Path(worktrees_dir).resolve()
        self._original_path = self._repo_root
        self._active_worktree: Path | None = None
        self._active_branch: str | None = None

    @property
    def is_active(self) -> bool:
        return self._active_worktree is not None

    @property
    def active_path(self) -> Path | None:
        return self._active_worktree

    @property
    def original_path(self) -> Path:
        return self._original_path

    def _git(self, *args, cwd=None) -> tuple[int, str, str]:
        """Run a git command. Returns (returncode, stdout, stderr)."""
        cmd = ['git'] + list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
                                  cwd=cwd or str(self._repo_root))
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, '', 'Git command timed out'
        except FileNotFoundError:
            return -1, '', 'git not found on PATH'

    def _get_current_branch(self) -> str:
        code, out, _ = self._git('rev-parse', '--abbrev-ref', 'HEAD')
        return out if code == 0 else 'main'

    def create(self, name: str, base_branch: str | None = None) -> tuple[bool, str, Path | None]:
        """Create a new git worktree. Returns (success, message, worktree_path)."""
        sanitized = ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)
        if sanitized != name:
            name = sanitized

        self._worktrees_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = self._worktrees_dir / name

        if worktree_path.exists():
            return False, f'Worktree path already exists: {worktree_path}', None

        existing = self.list_worktrees()
        for wt in existing:
            if Path(wt.path).resolve() == worktree_path.resolve():
                return False, f'Worktree already exists at: {worktree_path}', None
            if wt.branch == name.replace('_', '-') or wt.branch == name:
                return False, f'Branch "{name}" already exists in another worktree', None

        branch = base_branch or self._get_current_branch()
        branch_name = name.replace('_', '-')

        # Ensure the base branch exists locally
        code, _, _ = self._git('rev-parse', '--verify', branch)
        if code != 0:
            return False, f'Base branch not found: {branch}', None

        code, out, err = self._git('worktree', 'add', '--no-checkout',
                                   '-b', branch_name, str(worktree_path), branch)
        if code != 0:
            # Fall back: try without -b (use existing branch or detached head)
            code2, out2, err2 = self._git('worktree', 'add', '--no-checkout',
                                           str(worktree_path), branch)
            if code2 != 0:
                return False, f'Failed to create worktree:\n{err}\n{err2}', None
            # Get the actual branch name
            code3, actual_branch, _ = self._git('rev-parse', '--abbrev-ref', 'HEAD',
                                                 cwd=str(worktree_path))
            if code3 == 0 and actual_branch != 'HEAD':
                branch_name = actual_branch

        return True, f'Worktree created on branch [{branch_name}]', worktree_path

    def enter(self, name_or_path: str) -> tuple[bool, str, Path | None]:
        """Enter an existing worktree. Returns (success, message, worktree_path)."""
        if self._active_worktree is not None:
            return False, f'Already in a worktree: {self._active_worktree}. Use /worktree exit first.', None

        # Try as name under worktrees_dir
        candidate = self._worktrees_dir / name_or_path
        if not candidate.exists():
            # Try as absolute or relative path
            candidate = Path(name_or_path).resolve()
            if not candidate.exists():
                return False, f'Worktree not found: {name_or_path}', None

        # Verify it is a git worktree
        code, out, _ = self._git('rev-parse', '--git-dir', cwd=str(candidate))
        if code != 0:
            return False, f'Not a valid git worktree: {candidate}', None

        self._active_worktree = candidate
        code, branch, _ = self._git('rev-parse', '--abbrev-ref', 'HEAD', cwd=str(candidate))
        if code == 0 and branch != 'HEAD':
            self._active_branch = branch
        else:
            self._active_branch = os.path.basename(str(candidate))

        return True, f'Entered worktree [{self._active_branch}]: {candidate}', candidate

    def exit(self, remove: bool = False, discard_changes: bool = False) -> tuple[bool, str]:
        """Exit current worktree. Returns (success, message)."""
        if self._active_worktree is None:
            return False, 'Not in a worktree. Use /worktree enter <name> first.'

        wt_path = self._active_worktree
        if not wt_path.exists():
            self._active_worktree = None
            self._active_branch = None
            return True, 'Worktree path no longer exists. Reset to original directory.'

        if remove:
            if not discard_changes:
                code, out, _ = self._git('-C', str(wt_path), 'status', '--porcelain')
                if code == 0 and out.strip():
                    return False, f'Worktree has uncommitted changes. Use /worktree exit --remove --discard-changes to force.\n\nChanges:\n{out[:1000]}'

            # Remove the worktree
            code, out, err = self._git('worktree', 'remove', str(wt_path), '--force')
            if code != 0:
                return False, f'Failed to remove worktree: {err}'
            self._git('worktree', 'prune')
            msg = f'Removed worktree: {wt_path}'
            if self._active_branch:
                self._git('branch', '-D', self._active_branch)
                msg += f' (branch {self._active_branch} deleted)'
        else:
            msg = f'Exited worktree (kept): {wt_path}'

        self._active_worktree = None
        self._active_branch = None
        return True, msg

    def list_worktrees(self) -> list[WorktreeInfo]:
        """List all git worktrees."""
        code, out, _ = self._git('worktree', 'list', '--porcelain')
        if code != 0:
            return []

        worktrees = []
        current = {}
        for line in out.split('\n'):
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(WorktreeInfo(
                        path=current.get('worktree', ''),
                        branch=current.get('branch', '').replace('refs/heads/', ''),
                        bare=current.get('bare', '') == 'true',
                        locked=current.get('locked', '') != '',
                        prunable=current.get('prunable', ''),
                    ))
                    current = {}
                continue
            if ' ' in line:
                key, _, val = line.partition(' ')
                current[key] = val
        if current:
            worktrees.append(WorktreeInfo(
                path=current.get('worktree', ''),
                branch=current.get('branch', '').replace('refs/heads/', ''),
                bare=current.get('bare', '') == 'true',
                locked=current.get('locked', '') != '',
                prunable=current.get('prunable', ''),
            ))
        return worktrees


class EnterWorktreeTool(BaseTool):
    name = 'EnterWorktree'
    description = 'Create or enter a git worktree for isolated, reversible operations. Use before risky refactoring or dependency changes so you can discard the worktree if things go wrong. The worktree gets its own branch and working directory.'
    parameters = {
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'description': 'Name for the new worktree, or name/path of an existing worktree to enter'},
            'base_branch': {'type': 'string', 'description': 'Base branch for new worktree (defaults to current branch). Only used when creating a new worktree.'},
        },
        'required': ['name'],
    }
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, manager: WorktreeManager, on_switch_workdir=None):
        self._manager = manager
        self._on_switch_workdir = on_switch_workdir

    def execute(self, name: str, base_branch: str | None = None) -> ToolResult:
        if self._manager.is_active:
            return ToolResult(success=False, output='',
                              error=f'Already in a worktree: {self._manager.active_path}. Use ExitWorktree first.')

        existing = self._manager.list_worktrees()
        existing_paths = {Path(wt.path).resolve() for wt in existing}
        candidate = self._manager._worktrees_dir / name

        if candidate.resolve() in existing_paths:
            ok, msg, wpath = self._manager.enter(name)
            if ok and self._on_switch_workdir:
                self._on_switch_workdir(str(wpath))
            return ToolResult(success=ok, output=msg, error='' if ok else msg,
                              metadata={'worktree_path': str(wpath) if wpath else None})
        elif Path(name).resolve() in existing_paths:
            ok, msg, wpath = self._manager.enter(name)
            if ok and self._on_switch_workdir:
                self._on_switch_workdir(str(wpath))
            return ToolResult(success=ok, output=msg, error='' if ok else msg,
                              metadata={'worktree_path': str(wpath) if wpath else None})

        # Create new worktree
        ok, msg, wpath = self._manager.create(name, base_branch=base_branch)
        if not ok:
            return ToolResult(success=False, output='', error=msg)

        ok2, msg2, _ = self._manager.enter(str(wpath))
        if not ok2:
            return ToolResult(success=False, output='', error=f'Created but failed to enter: {msg2}')

        if self._on_switch_workdir:
            self._on_switch_workdir(str(wpath))

        return ToolResult(success=True,
                          output=f'Created and entered worktree: {wpath}\nBranch: {self._manager._active_branch}\nAll file and bash operations are now isolated to this worktree. Use ExitWorktree to leave.',
                          metadata={'worktree_path': str(wpath)})


class ExitWorktreeTool(BaseTool):
    name = 'ExitWorktree'
    description = 'Exit the current git worktree and return to the original working directory. Use remove=true to delete the worktree, discard_changes=true to force-delete even with uncommitted changes.'
    parameters = {
        'type': 'object',
        'properties': {
            'remove': {'type': 'boolean', 'description': 'If true, delete the worktree after exiting. Default: false (keep worktree).'},
            'discard_changes': {'type': 'boolean', 'description': 'If true, force removal even with uncommitted changes. Only relevant when remove=true. Default: false.'},
        },
        'required': [],
    }
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, manager: WorktreeManager, on_switch_workdir=None):
        self._manager = manager
        self._on_switch_workdir = on_switch_workdir

    def execute(self, remove: bool = False, discard_changes: bool = False) -> ToolResult:
        if not self._manager.is_active:
            return ToolResult(success=False, output='',
                              error='Not currently in a worktree. Use EnterWorktree first.')

        ok, msg = self._manager.exit(remove=remove, discard_changes=discard_changes)
        if ok and self._on_switch_workdir:
            self._on_switch_workdir(str(self._manager.original_path))

        return ToolResult(success=ok, output=msg if ok else '', error='' if ok else msg,
                          metadata={'original_path': str(self._manager.original_path)})
