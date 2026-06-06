import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class Skill:
    name: str
    description: str
    body: str
    version: str = '1.0.0'
    license: str = ''
    compatibility: str = ''
    metadata: dict = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def category(self) -> str:
        return self.metadata.get('hermes', {}).get('category', 'general')

    @property
    def tags(self) -> list[str]:
        return self.metadata.get('hermes', {}).get('tags', [])

    @property
    def platforms(self) -> list[str]:
        return self.metadata.get('hermes', {}).get('platforms', [])

    def to_summary(self) -> str:
        return f'**{self.name}**: {self.description}'

    def to_system_prompt(self) -> str:
        lines = [f'# Skill: {self.name}', f'## Description\n{self.description}', f'## Instructions\n{self.body}']
        return '\n\n'.join(lines)

class SkillLoader:
    FRONTMATTER_RE = re.compile('^---\\s*\\n(.*?)\\n---\\s*\\n?', re.DOTALL)

    @classmethod
    def load_from_dir(cls, skill_dir: Path) -> Skill | None:
        skill_file = skill_dir / 'SKILL.md'
        if not skill_file.exists():
            return None
        return cls.load(skill_file)

    @classmethod
    def load(cls, path: Path) -> Skill | None:
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except (PermissionError, OSError):
            return None
        frontmatter = {}
        body = text
        match = cls.FRONTMATTER_RE.match(text)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
            body = text[match.end():].strip()
        name = frontmatter.get('name', '')
        if not name:
            return None
        description = frontmatter.get('description', '')
        return Skill(name=name, description=description, body=body, version=str(frontmatter.get('version', '1.0.0')), license=str(frontmatter.get('license', '')), compatibility=str(frontmatter.get('compatibility', '')), metadata=frontmatter.get('metadata', {}), allowed_tools=cls._parse_allowed_tools(frontmatter.get('allowed-tools', '')), path=path)

    @staticmethod
    def _parse_allowed_tools(tools: str) -> list[str]:
        if not tools:
            return []
        return [t.strip() for t in tools.split() if t.strip()]
