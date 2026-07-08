from __future__ import annotations
from .base import BaseTool, ToolResult


class ContextRecallTool(BaseTool):
    name = 'ContextRecall'
    description = (
        'Retrieve the FULL original conversation history that was replaced by a compressed summary. '
        'Look for `<conversation_summary id=N>` in the context — the id is the archive number. '
        'Call this when you need the exact details, code, or tool outputs that were removed '
        'during compression. The compressed summary gives you the gist; this gives you the source.\n\n'
        'Use this sparingly — only when the summary lacks detail you genuinely need.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'The archive ID from the <conversation_summary id=N> tag.',
            },
        },
        'required': ['id'],
    }
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, compressor=None):
        self._compressor = compressor

    def execute(self, id: int) -> ToolResult:
        if self._compressor is None:
            return ToolResult(
                success=False, output='',
                error='Context archive not available.')
        messages = self._compressor.retrieve_archive(id)
        if messages is None:
            return ToolResult(
                success=False, output='',
                error=f'Archive {id} not found. It may have been evicted (only last 5 archives kept).')
        # Format as readable conversation (no truncation — the LLM explicitly asked for this)
        lines = [f'# Context Archive {id} ({len(messages)} messages)\n']
        for m in messages:
            role = m.get('role', '?')
            content = m.get('content', '')
            if not isinstance(content, str):
                content = str(content)
            tool_calls = m.get('tool_calls', [])
            if role == 'tool':
                lines.append(f'\n### [{role}]')
                lines.append(content)
            elif tool_calls:
                names = [tc.get('function', {}).get('name', '?') for tc in tool_calls]
                lines.append(f'\n### [{role} → called {", ".join(names)}]')
                if content:
                    lines.append(content)
            else:
                lines.append(f'\n### [{role}]')
                lines.append(content)
        return ToolResult(
            success=True,
            output='\n'.join(lines),
            metadata={'id': id, 'message_count': len(messages)},
        )
