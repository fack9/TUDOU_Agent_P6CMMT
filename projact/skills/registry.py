import os
from pathlib import Path
from .loader import SkillLoader, Skill

class SkillRegistry:

    def __init__(self, skills_paths: list[str] | None=None):
        self._skills: dict[str, Skill] = {}
        self._search_paths: list[Path] = []
        self._active_skill: str | None = None
        for sp in skills_paths or []:
            self.add_search_path(sp)

    def add_search_path(self, path: str):
        p = Path(path).expanduser().resolve()
        if p not in self._search_paths:
            self._search_paths.append(p)

    def discover(self) -> int:
        count = 0
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            for root, dirs, files in os.walk(search_path):
                if '.archive' in dirs:
                    dirs.remove('.archive')
                if '.hub' in dirs:
                    dirs.remove('.hub')
                if 'SKILL.md' in files:
                    skill_dir = Path(root)
                    skill = SkillLoader.load_from_dir(skill_dir)
                    if skill and skill.name not in self._skills:
                        self._skills[skill.name] = skill
                        count += 1
        return count

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        return [{'name': s.name, 'description': s.description} for s in self._skills.values()]

    def view_skill(self, name: str) -> str | None:
        skill = self._skills.get(name)
        if not skill:
            return None
        return skill.to_system_prompt()

    def view_reference(self, name: str, ref_path: str) -> str | None:
        skill = self._skills.get(name)
        if not skill or not skill.path:
            return None
        ref_file = skill.path / 'references' / ref_path
        if not ref_file.exists():
            return None
        try:
            return ref_file.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return None

    def activate(self, name: str) -> bool:
        if name not in self._skills:
            return False
        self._active_skill = name
        return True

    def deactivate(self):
        self._active_skill = None

    @property
    def active_skill(self) -> Skill | None:
        if self._active_skill:
            return self._skills.get(self._active_skill)
        return None

    def get_active_prompt(self) -> str:
        skill = self.active_skill
        if not skill:
            return ''
        return skill.to_system_prompt()

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills
