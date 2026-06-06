from tools.base import BaseTool, ToolResult


class MCPTool(BaseTool):

    def __init__(self, client, server_name: str, tool_def: dict):
        self._client = client
        self._server_name = server_name
        self._tool_name = tool_def['name']
        self.name = 'mcp__{}__{}'.format(server_name, tool_def['name'])
        desc = tool_def.get('description', 'MCP tool from {}'.format(server_name))
        self.description = '[{}] {}'.format(server_name, desc)
        self.parameters = tool_def.get('inputSchema', {
            'type': 'object', 'properties': {},
        })
        self.permission_level = 'needs_approval'
        self.is_read_only = False

    def execute(self, **kwargs) -> ToolResult:
        try:
            output = self._client.call_tool(self._tool_name, kwargs)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))
