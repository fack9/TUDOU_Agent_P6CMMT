import json
import os
import threading
from pathlib import Path
from .loader import SkillLoader, Skill

class SkillRegistry:

    def __init__(self, skills_paths: list[str] | None=None):
        self._skills: dict[str, Skill] = {}
        self._search_paths: list[Path] = []
        self._active_skill: str | None = None
        self._cache_path: Path | None = None
        self._lock = threading.Lock()
        for sp in skills_paths or []:
            self.add_search_path(sp)

    def set_cache_path(self, path: Path):
        self._cache_path = path

    def add_search_path(self, path: str):
        p = Path(path).expanduser().resolve()
        if p not in self._search_paths:
            self._search_paths.append(p)

    def get_search_paths(self) -> list[Path]:
        return list(self._search_paths)

    def _get_cache_mtime(self) -> float:
        """Return the latest mtime of all search paths."""
        latest = 0.0
        for sp in self._search_paths:
            try:
                st = sp.stat()
                if st.st_mtime > latest:
                    latest = st.st_mtime
            except OSError:
                pass
        return latest

    def _load_from_cache(self) -> int:
        if not self._cache_path or not self._cache_path.exists():
            return 0
        try:
            data = json.loads(self._cache_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            import sys
            print('[Skills] Cache corrupted, will re-scan', file=sys.stderr)
            return 0
        if data.get('mtime', 0) < self._get_cache_mtime():
            return 0
        count = 0
        for entry in data.get('skills', []):
            name = entry.get('name', '')
            if not name or name in self._skills:
                continue
            skill = Skill(
                name=name,
                description=entry.get('description', ''),
                body='',
                version=entry.get('version', '1.0.0'),
                metadata=entry.get('metadata', {}),
                allowed_tools=entry.get('allowed_tools', []),
                references=entry.get('references', []),
                scripts=entry.get('scripts', []),
                assets=entry.get('assets', []),
                examples=entry.get('examples', []),
                templates=entry.get('templates', []),
                requires_mcp=entry.get('requires_mcp', []),
                path=Path(entry['path']) if entry.get('path') else None,
                _body_loaded=False,
                _resources_discovered=False,
            )
            self._skills[name] = skill
            count += 1
        return count

    def _save_to_cache(self):
        if not self._cache_path:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        for s in self._skills.values():
            s._ensure_resources() if hasattr(s, '_ensure_resources') else None
            entries.append({
                'name': s.name,
                'description': s.description,
                'version': s.version,
                'metadata': s.metadata,
                'allowed_tools': s.allowed_tools,
                'references': s.references,
                'scripts': s.scripts,
                'assets': s.assets,
                'examples': s.examples,
                'templates': s.templates,
                'requires_mcp': s.requires_mcp,
                'path': str(s.path) if s.path else None,
            })
        data = {'mtime': self._get_cache_mtime(), 'skills': entries}
        try:
            self._cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass

    def discover(self) -> int:
        """Fast discover: load from cache if valid, else scan stubs only (no body parsing)."""
        cached = self._load_from_cache()
        if cached > 0:
            return cached

        # Clear stale entries before re-scan so removed skills don't persist
        self._skills.clear()
        count = 0
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            for root, dirs, files in os.walk(search_path):
                if '.archive' in dirs:
                    dirs.remove('.archive')
                if '.hub' in dirs:
                    dirs.remove('.hub')
                for skip in ('.git', '__pycache__', '.mypy_cache', '.pytest_cache',
                             '.tox', '.venv', 'venv', 'node_modules'):
                    if skip in dirs:
                        dirs.remove(skip)
                if 'SKILL.md' in files:
                    skill_dir = Path(root)
                    skill = SkillLoader.load_stub(skill_dir)
                    if skill and skill.name not in self._skills:
                        self._skills[skill.name] = skill
                        count += 1

        if count > 0:
            self._save_to_cache()
        return count

    def register(self, skill: Skill):
        with self._lock:
            self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        with self._lock:
            skill = self._skills.get(name)
        if skill:
            skill.ensure_body()
        return skill

    def list_skills(self) -> list[dict]:
        with self._lock:
            skills = list(self._skills.values())
        return [{
            'name': s.name,
            'description': s.description,
            'has_references': len(s.references) > 0,
            'has_scripts': len(s.scripts) > 0,
            'has_assets': len(s.assets) > 0,
        } for s in skills]

    def view_skill(self, name: str) -> str | None:
        with self._lock:
            skill = self._skills.get(name)
        if not skill:
            return None
        skill.ensure_body()
        return skill.to_system_prompt()

    def view_reference(self, name: str, ref_path: str) -> str | None:
        with self._lock:
            skill = self._skills.get(name)
        if not skill or not skill.path:
            return None
        skill._ensure_resources()
        # Try references/ first, then reference/
        for dirname in ('references', 'reference'):
            ref_file = skill.path / dirname / ref_path
            if ref_file.exists():
                try:
                    return ref_file.read_text(encoding='utf-8', errors='replace')
                except Exception:
                    return None
        return None

    def activate(self, name: str) -> bool:
        with self._lock:
            if name not in self._skills:
                return False
            self._skills[name].ensure_body()
            self._active_skill = name
            return True

    def deactivate(self):
        with self._lock:
            self._active_skill = None

    @property
    def active_skill(self) -> Skill | None:
        with self._lock:
            name = self._active_skill
            skill = self._skills.get(name) if name else None
        if skill:
            skill.ensure_body()
        return skill

    def get_active_prompt(self) -> str:
        skill = self.active_skill
        if not skill:
            return ''
        return skill.to_system_prompt()

    def invalidate_cache(self):
        """Force re-scan on next discover."""
        if self._cache_path and self._cache_path.exists():
            try:
                self._cache_path.unlink()
            except OSError:
                pass

    def save_cache(self):
        """Persist current skills to cache (call after registering new skills)."""
        self._save_to_cache()

    def __len__(self) -> int:
        with self._lock:
            return len(self._skills)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._skills

    def unregister(self, name: str):
        with self._lock:
            self._skills.pop(name, None)

    def items(self):
        """Return list of (name, skill) tuples (safe copy for iteration)."""
        with self._lock:
            return list(self._skills.items())
