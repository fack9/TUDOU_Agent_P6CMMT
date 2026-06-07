from __future__ import annotations
from .base import BaseTool, ToolResult


class AskUserQuestionTool(BaseTool):
    name = 'AskUserQuestion'
    description = 'Pause plan mode to ask the user clarifying questions. Use this when you have multiple valid approaches, need to resolve ambiguity, or require user preference before proceeding. Ask ALL your questions in one call — the user can only respond once. After getting answers, resume writing the plan with the user\'s choices locked in.'
    parameters = {'type': 'object', 'properties': {'questions': {'type': 'string', 'description': 'JSON array of questions. Each question: {"question": "...", "header": "short label", "options": ["A", "B"]}. Max 4 questions.'}}, 'required': ['questions']}
    permission_level = 'needs_approval'
    is_read_only = True

    def execute(self, questions: str) -> ToolResult:
        import json
        try:
            parsed = json.loads(questions)
            if not isinstance(parsed, list):
                return ToolResult(success=False, output='', error='questions must be a JSON array')
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output='', error=f'Invalid JSON: {e}')

        # Build formatted prompt for the CLI to display
        lines = ['\n--- User Questions ---\n']
        for i, q in enumerate(parsed):
            header = q.get('header', f'Q{i+1}')
            question = q.get('question', '')
            options = q.get('options', [])
            lines.append(f'[{header}] {question}')
            if options:
                for j, opt in enumerate(options):
                    label = opt.get('label', opt) if isinstance(opt, dict) else str(opt)
                    lines.append(f'  {j+1}. {label}')
            lines.append('')
        lines.append('---\n')

        prompt_text = '\n'.join(lines)
        return ToolResult(success=True, output=prompt_text, metadata={'raw': parsed, 'awaiting_response': True})
