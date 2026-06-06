from __future__ import annotations
import asyncio
import json
import queue
import threading
import urllib.request
import urllib.error
import sys
import lark_oapi as lark
from .auth import TokenManager
MAX_QUEUE_SIZE = 200

class FeishuBot:

    def __init__(self, app_id: str, app_secret: str, base_url: str='https://open.feishu.cn/open-apis'):
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url
        self.token_mgr = TokenManager(app_id, app_secret, base_url)
        self._send_url = f'{base_url}/im/v1/messages?receive_id_type=open_id'
        self._ws_client: lark.ws.Client | None = None
        self._ws_thread: threading.Thread | None = None
        self._running = False
        self._connected = threading.Event()
        self._msg_queue: queue.Queue[dict] = queue.Queue(maxsize=MAX_QUEUE_SIZE)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        if self._ws_client is None:
            return False
        if self._ws_thread is None or not self._ws_thread.is_alive():
            return False
        return self._connected.is_set()

    def connect(self):
        if self._running:
            return
        self._running = True
        self._connected.clear()
        handler = lark.EventDispatcherHandler.builder('', '').register_p2_im_message_receive_v1(self._on_message_receive).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(self._on_chat_entered).register_p2_im_message_message_read_v1(self._on_message_read).build()
        self._ws_client = lark.ws.Client(app_id=self._app_id, app_secret=self._app_secret, event_handler=handler, domain=self._base_url.replace('/open-apis', ''), log_level=lark.LogLevel.WARNING)
        self._ws_thread = threading.Thread(target=self._ws_runner, daemon=True)
        self._ws_thread.start()

    def _ws_runner(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._connected.set()
            self._ws_client.start()
        except Exception as e:
            print(f'[feishu] WS runner error: {e}', file=sys.stderr)
        finally:
            self._connected.clear()

    def disconnect(self):
        self._running = False
        self._connected.clear()
        ws = self._ws_client
        if ws is not None:
            try:
                ws.stop()
            except Exception:
                pass
            self._ws_client = None

    def get_message(self, timeout: float | None=None) -> dict | None:
        try:
            return self._msg_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_message(self, open_id: str, content: str) -> bool:
        token = self.token_mgr.get_tenant_token()
        body = json.dumps({'receive_id': open_id, 'msg_type': 'text', 'content': json.dumps({'text': content}, ensure_ascii=False)}, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(self._send_url, data=body, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if data.get('code') != 0:
                    print(f'[feishu] send error: code={data.get('code')} msg={data.get('msg')}', file=sys.stderr)
                    return False
                return True
        except Exception as e:
            print(f'[feishu] send exception: {e}', file=sys.stderr)
            return False

    def _on_message_receive(self, data: lark.im.v1.P2ImMessageReceiveV1):
        print('[feishu] RECEIVED v2 message event', file=sys.stderr)
        self._on_message_event(data)

    def _on_chat_entered(self, data):
        print('[feishu] Bot entered P2P chat', file=sys.stderr)

    def _on_message_read(self, data):
        pass

    def _on_message_event(self, data):
        self._connected.set()
        try:
            evt = data.event
            sender = evt.sender.sender_id
            open_id = getattr(sender, 'open_id', '') or ''
            msg = evt.message
            print(f'[feishu] msg from {open_id}: type={msg.message_type} raw_content={(msg.content[:100] if msg.content else 'None')}', file=sys.stderr)
            if msg.message_type == 'text' and open_id:
                content_str = msg.content or '{}'
                text = json.loads(content_str).get('text', '')
                if text:
                    try:
                        self._msg_queue.put_nowait({'open_id': open_id, 'text': text, 'chat_id': msg.chat_id or ''})
                    except queue.Full:
                        pass
        except Exception as e:
            print(f'[feishu] event parse error: {e}', file=sys.stderr)
