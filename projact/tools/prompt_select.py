from __future__ import annotations
from .base import BaseTool, ToolResult


class SelectPromptTool(BaseTool):
    name = 'SelectPrompt'
    description = (
        'Select a self-evolved prompt to replace the default system prompt for this session. '
        'The available prompts are listed in "## Available Prompts" at the top of context.\n\n'
        'Call with id=0 to switch back to the default system prompt.\n'
        'Call with id=N (1-4) to switch to prompt_N.\n\n'
        'The selected prompt takes effect immediately — all subsequent turns use it. '
        'Choose the prompt whose description best matches the task at hand.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Prompt ID: 0 for default, 1-4 for an evolved prompt.',
            },
        },
        'required': ['id'],
    }
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, prompt_dir=None, context_manager=None):
        self._prompt_dir = prompt_dir
        self._context = context_manager
        self._selected_id: int | None = None

    def execute(self, id: int) -> ToolResult:
        if self._context is None:
            return ToolResult(success=False, output='', error='Context manager not available.')
        if id == 0:
            self._context.system_prompt = None  # restore default
            self._selected_id = 0
            return ToolResult(success=True, output='Switched back to default system prompt.')
        if not self._prompt_dir:
            return ToolResult(success=False, output='', error='TU_Prompt directory not configured.')
        prompt_file = self._prompt_dir / f'prompt_{id}.md'
        idx_file = self._prompt_dir / f'prompt_{id}.idx.md'
        if not prompt_file.exists():
            return ToolResult(success=False, output='', error=f'Prompt {id} not found.')
        try:
            new_prompt = prompt_file.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ToolResult(success=False, output='', error=f'Cannot read prompt_{id}.md.')
        # Read index for the footer
        idx_text = ''
        if idx_file.exists():
            try:
                idx_text = idx_file.read_text(encoding='utf-8', errors='replace').strip()
            except OSError:
                pass
        footer = f'\n\n---\n*当前使用: prompt_{id} | {idx_text}*' if idx_text else f'\n\n---\n*当前使用: 自进化 prompt #{id}*'
        self._context.system_prompt = new_prompt + footer
        self._selected_id = id
        return ToolResult(
            success=True,
            output=f'Switched to prompt_{id}. {idx_text}',
        )
