from __future__ import annotations
from pathlib import Path
from .base import BaseTool, ToolResult


_MAX_PROMPTS = 4


class WritePromptTool(BaseTool):
    name = 'WritePrompt'
    description = (
        'Write a new self-evolved system prompt to TU_Prompt/. '
        'This creates TWO files: prompt_N.md (the full system prompt) and '
        'prompt_N.idx.md (a one-line description, max 50 characters).\n\n'
        'Call this after a reflection cycle or when the user asks you to save a prompt. '
        f'Maximum {_MAX_PROMPTS} prompts. If all slots are full, delete or merge existing ones first.\n\n'
        'The prompt body should be a COMPLETE system prompt — it replaces the default entirely. '
        'Start from the default prompt and modify it based on what you have learned. '
        'Remove outdated instructions. Add new patterns that work. '
        'The goal is a prompt that would have made past conversations smoother.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'slot': {
                'type': 'integer',
                'description': f'Slot number 1-{_MAX_PROMPTS}. Overwrites if exists.',
            },
            'summary': {
                'type': 'string',
                'description': 'One-line capability summary (max 50 chars). e.g. "代码重构与架构设计 · 偏好Rust/Python · 简短回复"',
            },
            'body': {
                'type': 'string',
                'description': 'The full system prompt text.',
            },
        },
        'required': ['slot', 'summary', 'body'],
    }
    permission_level = 'needs_approval'
    is_read_only = False

    def __init__(self, prompt_dir: Path | None = None):
        self._prompt_dir = prompt_dir

    def execute(self, slot: int, summary: str, body: str) -> ToolResult:
        if not self._prompt_dir:
            return ToolResult(success=False, output='', error='TU_Prompt directory not configured.')
        if slot < 1 or slot > _MAX_PROMPTS:
            return ToolResult(success=False, output='',
                              error=f'Slot must be 1-{_MAX_PROMPTS}.')
        self._prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = self._prompt_dir / f'prompt_{slot}.md'
        idx_file = self._prompt_dir / f'prompt_{slot}.idx.md'
        try:
            prompt_file.write_text(body.strip() + '\n', encoding='utf-8')
            idx_file.write_text(summary.strip()[:50] + '\n', encoding='utf-8')
        except OSError as e:
            return ToolResult(success=False, output='', error=f'Write failed: {e}')
        return ToolResult(
            success=True,
            output=f'Prompt {slot} saved. Summary: {summary[:50]}. '
                    f'Use SelectPrompt(id={slot}) to activate it.',
            metadata={'slot': slot, 'chars': len(body)},
        )


class ReflectTool(BaseTool):
    name = 'Reflect'
    description = (
        'Record a micro-reflection about what worked well or poorly in the current turn. '
        'These accumulate over time and become the raw material for evolving better prompts.\n\n'
        'Call this when:\n'
        '- The user praised or corrected your approach\n'
        '- You discovered a better way to handle a task\n'
        '- Something you tried clearly failed and you know why\n'
        '- A pattern emerged across multiple turns that is worth remembering\n\n'
        'Keep each reflection CONCISE — one sentence. They are stored in memory '
        'and reviewed when writing new prompts.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'reflection': {
                'type': 'string',
                'description': 'One-sentence reflection (max 200 chars).',
            },
        },
        'required': ['reflection'],
    }
    permission_level = 'safe'
    is_read_only = False

    def __init__(self, memory_dir: Path | None = None):
        self._memory_dir = memory_dir

    def execute(self, reflection: str) -> ToolResult:
        if not self._memory_dir:
            return ToolResult(success=False, output='', error='Memory directory not configured.')
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        refl_file = self._memory_dir / 'micro_reflections.md'
        try:
            existing = ''
            if refl_file.exists():
                existing = refl_file.read_text(encoding='utf-8', errors='replace')
            # Keep only last 50 reflections
            lines = [l for l in existing.strip().split('\n') if l.strip()]
            lines.append(f'- {reflection.strip()[:200]}')
            if len(lines) > 50:
                lines = lines[-50:]
            refl_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError as e:
            return ToolResult(success=False, output='', error=f'Write failed: {e}')
        return ToolResult(
            success=True,
            output=f'Reflection recorded ({len(lines)} total).',
            metadata={'count': len(lines)},
        )
