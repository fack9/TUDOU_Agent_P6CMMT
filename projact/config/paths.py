import os
import sys
from pathlib import Path

def _is_project_root(path: Path) -> bool:
    return (path / 'config.yaml').exists() or (path / 'builtin_skills').is_dir()


def get_projact_dir() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
        if _is_project_root(base):
            return base
        internal = base / '_internal'
        if _is_project_root(internal):
            return internal
        parent = base.parent
        if _is_project_root(parent):
            return parent
        return base
    return Path(__file__).resolve().parent.parent
_PROJACT_DIR = get_projact_dir()

def get_config_paths() -> dict:
    home = Path.home()
    return {'user_config_dir': home / '.tudou_agent', 'user_config_file': home / '.tudou_agent' / 'config.yaml', 'user_permissions_file': home / '.tudou_agent' / 'permissions.json', 'user_history_file': home / '.tudou_agent' / 'history', 'user_sessions_db': home / '.tudou_agent' / 'sessions.db', 'hermes_skills_dir': home / '.hermes' / 'skills', 'projact_config_file': _PROJACT_DIR / 'config.yaml', 'project_config_file': '.tudou_agent.yaml'}

def find_project_root(start: Path | None=None) -> Path:
    if start is None:
        start = Path.cwd()
    start = start.resolve()
    for parent in [start, *start.parents]:
        if (parent / '.git').exists():
            return parent
    return start

def find_project_config(start: Path | None=None) -> Path | None:
    if start is None:
        start = Path.cwd()
    start = start.resolve()
    for parent in [start, *start.parents]:
        cfg = parent / '.tudou_agent.yaml'
        if cfg.exists():
            return cfg
    return None
