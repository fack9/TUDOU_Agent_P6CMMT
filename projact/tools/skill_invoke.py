from .base import BaseTool, ToolResult


class SkillTool(BaseTool):
    name = 'Skill'
    description = (
        'Execute a skill within the main conversation. '
        'When you invoke this tool, the skill is AUTO-ACTIVATED — its body stays in '
        'the system prompt for all subsequent turns of this session.\n\n'
        'Skills use 3-level progressive loading to keep context lean:\n'
        '  Level 1: name + description (always loaded)\n'
        '  Level 2: SKILL.md body (loaded NOW when this tool fires)\n'
        '  Level 3: references/, scripts/, assets/ (loaded on demand with Read/Bash)\n\n'
        'When users ask you to perform tasks, check if any skills match. '
        'Use SkillList to see available skills, SkillSearch to find by keyword, '
        'then use this tool to load a skill and follow its instructions.\n\n'
        'CRITICAL: When a skill matches the user\'s request, invoke Skill BEFORE '
        'generating any other response about the task. '
        'Do NOT mention a skill without actually calling this tool.\n\n'
        'Only invoke skills from SkillList or SkillSearch results. '
        'Do not guess or invent skill names. '
        'Do not use this tool for built-in slash commands (like /help, /clear, /model, etc.).\n\n'
        'You can activate MULTIPLE skills — the most recent one wins.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'skill': {
                'type': 'string',
                'description': 'The exact name of a skill from SkillList or SkillSearch results.',
            },
            'args': {
                'type': 'string',
                'description': 'Optional arguments to pass to the skill.',
            },
        },
        'required': ['skill'],
    }
    is_read_only = True
    permission_level = 'safe'

    def __init__(self, skill_registry):
        self._registry = skill_registry

    def execute(self, skill: str, args: str = '') -> ToolResult:
        sk = self._registry.get(skill)
        if not sk:
            all_names = [s['name'] for s in self._registry.list_skills()]
            hint = f' Use SkillList to see all {len(all_names)} skills or SkillSearch to find by keyword.'
            return ToolResult(
                success=False,
                output='',
                error=f'Skill "{skill}" not found.{hint}',
            )

        body = sk.body or ''
        if not body:
            return ToolResult(
                success=False,
                output='',
                error=f'Skill "{skill}" has no body content.',
            )

        out = f'# Skill Loaded: {sk.name}\n'
        if args:
            out += f'Arguments: {args}\n'
        out += f'\n## Description\n{sk.description}\n\n'
        out += f'## Instructions\n{body}'

        if sk.allowed_tools:
            out += f'\n\n## Allowed Tools\n{", ".join(sk.allowed_tools)}'

        # Level 3 bundled resources
        resources = []
        if sk.references:
            resources.append(f'### References (Level 3 — read with Read tool)\n' + '\n'.join(f'- `{r}`' for r in sk.references))
        if sk.scripts:
            resources.append(f'### Scripts (Level 3 — execute with Bash)\n' + '\n'.join(f'- `{s}`' for s in sk.scripts))
        if sk.assets:
            resources.append(f'### Assets (Level 3 — copy into output)\n' + '\n'.join(f'- `{a}`' for a in sk.assets))
        if sk.examples:
            resources.append(f'### Examples\n' + '\n'.join(f'- `{e}`' for e in sk.examples))
        if sk.templates:
            resources.append(f'### Templates\n' + '\n'.join(f'- `{t}`' for t in sk.templates))
        if resources:
            out += f'\n\n## Bundled Resources\n\n' + '\n\n'.join(resources)

        # Auto-activate: subsequent turns get this skill's body in system prompt
        self._registry.activate(skill)
        out += f'\n\n---\n*Skill "{skill}" is now active for this session.*'

        return ToolResult(success=True, output=out)


class SkillListTool(BaseTool):
    name = 'SkillList'
    description = (
        'List all available skills. Use this to discover what specialized capabilities '
        'are available before deciding which skill to load with the Skill tool.\n\n'
        'Call this when you need to know what skills exist, or when the user asks '
        '"what skills do you have?".'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'page': {
                'type': 'integer',
                'description': 'Page number for pagination (1-based, default 1). 50 skills per page.',
            },
        },
        'required': [],
    }
    is_read_only = True
    permission_level = 'safe'

    def __init__(self, skill_registry):
        self._registry = skill_registry

    def execute(self, page: int = 1) -> ToolResult:
        all_skills = self._registry.list_skills()
        total = len(all_skills)
        active_name = self._registry.active_skill.name if self._registry.active_skill else None
        per_page = 50
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        chunk = all_skills[start:start + per_page]

        lines = [f'# Available Skills ({total} total, page {page}/{total_pages})\n']
        if active_name:
            lines.append(f'*Active skill: **{active_name}** (already loaded in context)*\n')
        for s in chunk:
            marker = ' **[ACTIVE]**' if s['name'] == active_name else ''
            lines.append(f'- **{s["name"]}**{marker}: {s["description"]}')
        if total_pages > 1:
            lines.append(f'\nUse page={page+1} for next page.' if page < total_pages else '')
        return ToolResult(success=True, output='\n'.join(lines))


class SkillSearchTool(BaseTool):
    name = 'SkillSearch'
    description = (
        'Search available skills by keyword. Matches against skill name, description, '
        'and tags. Use this to find relevant skills for a task when you don\'t know '
        'the exact skill name.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Keyword to search for (e.g. "security", "git", "review", "test").',
            },
        },
        'required': ['query'],
    }
    is_read_only = True
    permission_level = 'safe'

    def __init__(self, skill_registry):
        self._registry = skill_registry

    def execute(self, query: str) -> ToolResult:
        keyword = query.lower().strip()
        matches = []
        for _, s in self._registry.items():
            score = 0
            if keyword in s.name.lower():
                score += 10
            if keyword in s.description.lower():
                score += 5
            if s.tags:
                for t in s.tags:
                    if keyword in t.lower():
                        score += 3
            if score > 0:
                matches.append((score, s))

        matches.sort(key=lambda x: x[0], reverse=True)
        if not matches:
            return ToolResult(
                success=True,
                output=f'No skills found matching "{query}". Try a different keyword, or use SkillList to browse all {len(self._registry)} skills.',
            )

        active_name = self._registry.active_skill.name if self._registry.active_skill else None
        lines = [f'# Skills matching "{query}" ({len(matches)} found)\n']
        if active_name:
            lines.append(f'*Active skill: **{active_name}** (already loaded in context)*\n')
        for score, s in matches[:30]:
            tag_str = f' [tags: {", ".join(s.tags[:5])}]' if s.tags else ''
            marker = ' **[ACTIVE]**' if s.name == active_name else ''
            lines.append(f'- **{s.name}**{marker}: {s.description}{tag_str}')
        if len(matches) > 30:
            lines.append(f'\n(Showing top 30 of {len(matches)} matches. Use a more specific keyword to narrow results.)')
        lines.append('\nUse Skill(skill="<name>") to load a skill from these results.')
        return ToolResult(success=True, output='\n'.join(lines))


class SkillRegisterTool(BaseTool):
    name = 'SkillRegister'
    description = (
        'Register a newly created or modified skill so it appears in SkillList/SkillSearch '
        'immediately without restarting. Use this after creating, editing, or merging skills '
        'in TU_skills/.\n\n'
        'Call with no arguments to re-scan all search paths, or pass a skill name to register '
        'a specific skill.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Optional skill name to register. If omitted, re-scans all search paths.',
            },
        },
        'required': [],
    }
    is_read_only = True
    permission_level = 'safe'

    def __init__(self, skill_registry):
        self._registry = skill_registry

    def execute(self, name: str = '') -> ToolResult:
        if name:
            # Try to find and register a specific skill
            from skills.loader import SkillLoader
            for sp in self._registry.get_search_paths():
                skill_dir = sp / name
                if skill_dir.is_dir():
                    skill = SkillLoader.load_from_dir(skill_dir)
                    if skill:
                        self._registry.register(skill)
                        self._registry.save_cache()
                        return ToolResult(
                            success=True,
                            output=f'Skill "{name}" registered successfully from {skill_dir}.',
                        )
            return ToolResult(
                success=False,
                output='',
                error=f'Skill "{name}" not found in any search path. Create the SKILL.md file first.',
            )
        else:
            # Re-scan all search paths
            self._registry.invalidate_cache()
            count = self._registry.discover()
            return ToolResult(
                success=True,
                output=f'Re-scanned skill directories. {count} skills loaded.',
            )
