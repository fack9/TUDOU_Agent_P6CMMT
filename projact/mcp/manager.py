import sys
from pathlib import Path
from .client import MCPClient
from .tool_wrapper import MCPTool


class MCPManager:

    def __init__(self, server_configs: list[dict] | None = None):
        self._clients: dict[str, MCPClient] = {}
        self._configs = server_configs or []
        self._discovered = False

    def discover(self, tool_registry) -> int:

        if self._discovered:
            return len(self._clients)

        connected = 0
        for cfg in self._configs:
            name = cfg.get('name', '')
            if not name:
                continue
            try:
                cwd = cfg.get('cwd')
                if cwd:
                    cwd = str(Path(cwd).expanduser())
                command = cfg.get('command', '')
                if not command:
                    print('[MCP] Skipping "{}": missing "command" in config'.format(name), file=sys.stderr)
                    continue
                client = MCPClient(
                    name=name,
                    command=command,
                    args=cfg.get('args', []),
                    env=cfg.get('env', {}),
                    cwd=cwd,
                )
                client.start()
                info = client.initialize()
                server_info = info.get('serverInfo', {})
                ver = server_info.get('version', '?')
                print('[MCP] Connected: {} v{}'.format(name, ver), file=sys.stderr)

                tools = client.list_tools()
                if tools:
                    for tool_def in tools:
                        wrapped = MCPTool(client, name, tool_def)
                        tool_registry.register_tool(wrapped)

                self._clients[name] = client
                connected += 1
                print('[MCP] {}: {} tools loaded'.format(name, len(tools)), file=sys.stderr)

            except Exception as e:
                print('[MCP] Failed to start "{}": {}'.format(name, e), file=sys.stderr)

        self._discovered = True
        return connected

    def shutdown(self):
        for client in self._clients.values():
            try:
                client.stop()
            except Exception:
                pass
        self._clients.clear()
        self._discovered = False

    def is_connected(self, name: str) -> bool:
        return name in self._clients

    @property
    def connected_count(self) -> int:
        return len(self._clients)

    @property
    def server_count(self) -> int:
        return len(self._configs)
