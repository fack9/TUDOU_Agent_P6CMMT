from tools.base import BaseTool, ToolResult


class MCPTool(BaseTool):

    _READ_KEYWORDS = ('read', 'list', 'get', 'search', 'find', 'query', 'view',
                      'show', 'fetch', 'look', 'cat', 'head', 'tail', 'ls', 'dir')

    def __init__(self, client, server_name: str, tool_def: dict):
        self._client = client
        self._server_name = server_name
        tool_name = tool_def.get('name', '')
        if not tool_name:
            raise ValueError('MCP tool from "{}" has no name field'.format(server_name))
        self._tool_name = tool_name
        self.name = 'mcp__{}__{}'.format(server_name, tool_name)
        desc = tool_def.get('description', 'MCP tool from {}'.format(server_name))
        self.description = '[{}] {}'.format(server_name, desc)
        self.parameters = tool_def.get('inputSchema', {
            'type': 'object', 'properties': {},
        })
        name_lower = tool_name.lower()
        is_read = any(kw in name_lower for kw in self._READ_KEYWORDS)
        self.permission_level = 'safe' if is_read else 'needs_approval'
        self.is_read_only = is_read

    def execute(self, **kwargs) -> ToolResult:
        try:
            output = self._client.call_tool(self._tool_name, kwargs)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
