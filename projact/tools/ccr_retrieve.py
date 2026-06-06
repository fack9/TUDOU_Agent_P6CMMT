from __future__ import annotations
from .base import BaseTool, ToolResult


class RetrieveTool(BaseTool):
    name = 'Retrieve'
    description = 'Retrieve the full original content of a previously truncated tool result. Use the CCR ID shown in brackets (e.g. [CCR:abc123]) after a compressed output. Call this when you need details that were cut out.'
    parameters = {'type': 'object', 'properties': {'rid': {'type': 'string', 'description': 'The CCR ID shown in brackets in the truncated output (e.g. "abc123")'}}, 'required': ['rid']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, ccr_store=None):
        self._ccr = ccr_store

    def execute(self, rid: str) -> ToolResult:
        if self._ccr is None:
            return ToolResult(success=False, output='',
                              error='CCR store not available — original content has been discarded.')
        content = self._ccr.retrieve(rid.strip())
        if content is None:
            return ToolResult(success=False, output='',
                              error=f'CCR entry not found: {rid}. It may have been evicted or never existed.')
        return ToolResult(success=True, output=content,
                          metadata={'rid': rid, 'chars': len(content)})
