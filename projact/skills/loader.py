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
    references: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    requires_mcp: list[str] = field(default_factory=list)
    path: Path | None = None
    _body_loaded: bool = False
    _frontmatter_raw: dict | None = None
    _resources_discovered: bool = False

    @property
    def category(self) -> str:
        return self.metadata.get('hermes', {}).get('category', 'general')

    @property
    def tags(self) -> list[str]:
        return self.metadata.get('hermes', {}).get('tags', [])

    @property
    def platforms(self) -> list[str]:
        return self.metadata.get('hermes', {}).get('platforms', [])

    def ensure_body(self):
        if not self._body_loaded and self.path:
            SkillLoader._load_body(self)

    def to_summary(self) -> str:
        return f'**{self.name}**: {self.description}'

    def to_system_prompt(self) -> str:
        self.ensure_body()
        self._ensure_resources()
        lines = [f'# Skill: {self.name}', f'## Description\n{self.description}', f'## Instructions\n{self.body}']
        # Level 3 resources
        resources = []
        if self.references:
            resources.append(f'### References (read with Read tool as needed)\n' + '\n'.join(f'- `{r}`' for r in self.references))
        if self.scripts:
            resources.append(f'### Scripts (execute directly with Bash)\n' + '\n'.join(f'- `{s}`' for s in self.scripts))
        if self.assets:
            resources.append(f'### Assets (copy/use in output)\n' + '\n'.join(f'- `{a}`' for a in self.assets))
        if self.examples:
            resources.append(f'### Examples\n' + '\n'.join(f'- `{e}`' for e in self.examples))
        if self.templates:
            resources.append(f'### Templates\n' + '\n'.join(f'- `{t}`' for t in self.templates))
        if resources:
            lines.append('\n## Bundled Resources (Level 3 — load on demand)\n\n' + '\n\n'.join(resources))
        return '\n\n'.join(lines)

    def _ensure_resources(self):
        """Discover bundled resources once."""
        if not self._resources_discovered and self.path and self.path.is_dir():
            SkillLoader._discover_resources(self)
            self._resources_discovered = True

class SkillLoader:
    FRONTMATTER_RE = re.compile('^---\\s*\\n(.*?)\\n---\\s*\\n?', re.DOTALL)

    @classmethod
    def load_from_dir(cls, skill_dir: Path, body: bool = True) -> Skill | None:
        skill_file = skill_dir / 'SKILL.md'
        if not skill_file.exists():
            return None
        skill = cls.load(skill_file, body=body)
        if skill:
            skill.path = skill_dir
            if body:
                cls._discover_resources(skill)
                skill._resources_discovered = True
        return skill

    @classmethod
    def load_stub(cls, skill_dir: Path) -> Skill | None:
        """Parse only frontmatter, skip body — for fast startup indexing."""
        return cls.load_from_dir(skill_dir, body=False)

    @classmethod
    def load(cls, path: Path, body: bool = True) -> Skill | None:
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except (PermissionError, OSError):
            return None
        frontmatter = {}
        body_text = text
        match = cls.FRONTMATTER_RE.match(text)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
            body_text = text[match.end():].strip()
        name = frontmatter.get('name', '')
        if not name:
            return None
        description = frontmatter.get('description', '')
        requires = frontmatter.get('requires', {}) or {}
        requires_mcp = requires.get('mcp', []) if isinstance(requires, dict) else []
        if isinstance(requires_mcp, str):
            requires_mcp = [requires_mcp]
        # Use parent dir as skill root (path may be SKILL.md file or directory)
        skill_path = path.parent if path.is_file() else path
        skill = Skill(
            name=name,
            description=description,
            body=body_text if body else '',
            version=str(frontmatter.get('version', '1.0.0')),
            license=str(frontmatter.get('license', '')),
            compatibility=str(frontmatter.get('compatibility', '')),
            metadata=frontmatter.get('metadata', {}),
            allowed_tools=cls._parse_allowed_tools(frontmatter.get('allowed-tools', '')),
            requires_mcp=requires_mcp,
            path=skill_path,
            _body_loaded=body,
            _frontmatter_raw=frontmatter if not body else None,
        )
        if body:
            cls._discover_resources(skill)
            skill._resources_discovered = True
        return skill

    @classmethod
    def _load_body(cls, skill: Skill):
        """Load body text for a stub skill."""
        if not skill.path:
            return
        skill_file = skill.path / 'SKILL.md' if skill.path.is_dir() else skill.path
        try:
            text = skill_file.read_text(encoding='utf-8', errors='replace')
        except (PermissionError, OSError):
            return
        match = cls.FRONTMATTER_RE.match(text)
        if match:
            skill.body = text[match.end():].strip()
        else:
            skill.body = text
        skill._body_loaded = True

    @staticmethod
    def _parse_allowed_tools(tools: str) -> list[str]:
        if not tools:
            return []
        return [t.strip() for t in tools.split() if t.strip()]

    @classmethod
    def _discover_resources(cls, skill: Skill):
        """Scan for references/, scripts/, assets/ subdirectories (also reference/ singular)."""
        if not skill.path or not skill.path.is_dir():
            return
        base = skill.path
        dir_map = {
            'references': ('references', 'reference'),
            'scripts': ('scripts',),
            'assets': ('assets',),
            'examples': ('examples',),
            'templates': ('templates',),
        }
        for attr_name, candidates in dir_map.items():
            files = []
            for cand in candidates:
                sub_dir = base / cand
                if sub_dir.is_dir():
                    for f in sub_dir.rglob('*'):
                        if f.is_file():
                            files.append(str(f.relative_to(base)).replace('\\', '/'))
                    break  # Use first match
            if files:
                setattr(skill, attr_name, sorted(files))
