import json
import os
import subprocess
import sys
import threading
from utils.constants import VERSION


class MCPClient:
   

    def __init__(self, name: str, command: str, args: list[str] | None = None,
                 env: dict[str, str] | None = None, cwd: str | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self._process = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._pending: dict[int, tuple[threading.Event, dict]] = {}
        self._reader_thread = None
        self._running = False
        self._capabilities = {}
        self._server_info = {}

    def start(self):
        full_env = dict(os.environ)
        full_env.update(self.env)
        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                cwd=self.cwd or os.getcwd(),
                env=full_env,
            )
        except FileNotFoundError:
            raise RuntimeError(
                'MCP server "{}" command not found: {}. '
                'Is the required runtime (node, python, etc.) installed?'.format(
                    self.name, self.command))

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        def _drain_stderr():
            while self._running:
                try:
                    line = self._process.stderr.readline()
                except (ValueError, OSError):
                    break
                if not line:
                    break
                print('[MCP:{}] {}'.format(self.name, line.rstrip()), file=sys.stderr)

        self._stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_loop(self):
        while self._running:
            try:
                line = self._process.stdout.readline()
            except (ValueError, OSError):
                break  # pipe closed during shutdown
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print('[MCP:{}] JSON decode error: {}'.format(
                    self.name, line[:200].rstrip()), file=sys.stderr)
                continue
            msg_id = msg.get('id')
            if msg_id is not None:
                with self._lock:
                    pending_entry = self._pending.pop(msg_id, None)
                if pending_entry is not None:
                    event, holder = pending_entry
                    if 'error' in msg:
                        holder['error'] = msg['error']
                    else:
                        holder['result'] = msg.get('result', {})
                    event.set()

    def _send_request(self, method: str, params: dict | None = None, timeout: int = 30) -> dict:
        with self._lock:
            self._request_id += 1
            req_id = self._request_id
            event = threading.Event()
            holder = {}
            self._pending[req_id] = (event, holder)
            req = {'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params or {}}
            try:
                self._process.stdin.write(json.dumps(req, ensure_ascii=False) + '\n')
                self._process.stdin.flush()
            except (OSError, BrokenPipeError):
                self._pending.pop(req_id, None)
                raise ConnectionError('MCP server "{}" process has died'.format(self.name))
        if not event.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(
                'MCP server "{}" timed out on {} ({}s)'.format(self.name, method, timeout))
        if 'error' in holder:
            err = holder['error']
            raise RuntimeError('MCP error [{} {}]: {}'.format(
                err.get('code', -1), err.get('message', 'unknown'), method))
        return holder.get('result', {})

    def _send_notification(self, method: str, params: dict | None = None):
        with self._lock:
            notif = {'jsonrpc': '2.0', 'method': method, 'params': params or {}}
            try:
                self._process.stdin.write(json.dumps(notif, ensure_ascii=False) + '\n')
                self._process.stdin.flush()
            except (OSError, BrokenPipeError):
                pass  # server already dead, notification is best-effort

    def initialize(self) -> dict:
        result = self._send_request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'TUDOU_agent', 'version': VERSION},
        })
        self._capabilities = result.get('capabilities', {})
        self._server_info = result.get('serverInfo', {})
        self._send_notification('initialized', {})
        return result

    def list_tools(self) -> list[dict]:
        result = self._send_request('tools/list', {})
        return result.get('tools', [])

    def list_resources(self) -> list[dict]:
        result = self._send_request('resources/list', {})
        return result.get('resources', [])

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        result = self._send_request('tools/call', {
            'name': tool_name,
            'arguments': arguments,
        })
        content = result.get('content', [])
        is_error = result.get('isError', False)
        parts = []
        for block in content:
            t = block.get('type', '')
            if t == 'text':
                parts.append(block.get('text', ''))
            elif t == 'image':
                parts.append('[Image: {} {}]'.format(
                    block.get('mimeType', 'image'), block.get('data', '')[:50]))
            elif t == 'resource':
                resource = block.get('resource', {})
                parts.append('[Resource: {}]'.format(resource.get('uri', '')))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        output = '\n'.join(parts)
        if is_error:
            raise RuntimeError(output)
        return output

    def stop(self):
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                    self._process.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    pass
            except OSError:
                pass  # process already dead
