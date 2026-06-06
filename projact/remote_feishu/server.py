from __future__ import annotations
import json
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any
from .bot import FeishuBot
BINDING_FILE = Path.home() / '.tudou_agent' / 'remote_binding.json'
PAIRING_TIMEOUT = 300

class FeishuRelay:

    def __init__(self, agent: Any=None, app_id: str='', app_secret: str='', base_url: str='https://open.feishu.cn/open-apis'):
        self._agent = agent
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url
        self._bot: FeishuBot | None = None
        self._running = False
        self._process_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pairing_code: str | None = None
        self._pairing_deadline: float = 0.0
        self._nocode: bool = False
        self._authorized_open_id: str | None = None
        self._paired_at: float = 0.0
        self._load_binding()

    @property
    def is_running(self) -> bool:
        return self._running

    def set_agent(self, agent: Any):
        self._agent = agent

    def start(self, nocode: bool=False) -> dict:
        if self._running:
            return {'ok': False, 'error': 'already running'}
        if not self._app_id or not self._app_secret:
            return {'ok': False, 'error': 'Feishu app_id/app_secret not configured. Set remote.feishu.app_id and remote.feishu.app_secret in config.yaml'}
        bot = FeishuBot(self._app_id, self._app_secret, self._base_url)
        try:
            bot.token_mgr.get_tenant_token()
        except Exception as e:
            return {'ok': False, 'error': f'Feishu auth failed: {e}'}
        self._bot = bot
        self._nocode = nocode
        if not nocode:
            self._pairing_code = str(secrets.randbelow(900000) + 100000)
            self._pairing_deadline = time.time() + PAIRING_TIMEOUT
        else:
            self._pairing_code = None
            self._pairing_deadline = 0.0
        bot.connect()
        self._running = True
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()
        if nocode:
            if self._authorized_open_id:
                return {'ok': True, 'provider': 'feishu', 'nocode': True, 'paired': True, 'status_note': 'No-code mode: using existing binding.'}
            else:
                return {'ok': True, 'provider': 'feishu', 'nocode': True, 'paired': False, 'status_note': 'No-code mode: first person to send a message will be auto-bound.'}
        else:
            status = ' (re-connected)' if self._authorized_open_id else ''
            return {'ok': True, 'provider': 'feishu', 'pairing_code': self._pairing_code, 'paired': self._authorized_open_id is not None, 'status_note': f'Open Feishu on your phone, find your bot, and send the pairing code.{status}'}

    def stop(self) -> dict:
        if not self._running:
            return {'ok': False, 'error': 'not running'}
        self._running = False
        bot = self._bot
        if bot:
            bot.disconnect()
        self._bot = None
        return {'ok': True}

    def unpair(self) -> dict:
        with self._lock:
            self._authorized_open_id = None
            self._paired_at = 0.0
            self._save_binding()
        return {'ok': True}

    def status(self) -> dict:
        bot_connected = self._bot.is_connected if self._bot else False
        pairing_active = self._pairing_code is not None and time.time() < self._pairing_deadline
        return {'running': self._running, 'provider': 'feishu', 'ws_connected': bot_connected, 'bound': self._authorized_open_id is not None, 'nocode': self._nocode, 'pairing_active': pairing_active, 'pairing_code': self._pairing_code if pairing_active else None, 'pairing_remaining': max(0, int(self._pairing_deadline - time.time())) if pairing_active else 0}

    def _process_loop(self):
        print('[feishu] Process loop started', file=sys.stderr)
        while self._running:
            msg = self._bot.get_message(timeout=1.0) if self._bot else None
            if msg is None:
                continue
            open_id = msg['open_id']
            text = msg['text']
            print(f'[feishu] Processing: open_id={open_id[:15]}... text="{text}"', file=sys.stderr)
            pairing_active = self._pairing_code is not None and time.time() < self._pairing_deadline
            if self._nocode and (not self._authorized_open_id):
                self._auto_bind(open_id, text)
            elif not self._authorized_open_id or pairing_active:
                self._handle_pairing(open_id, text)
            elif open_id == self._authorized_open_id:
                self._handle_chat(open_id, text)
            else:
                print(f'[feishu] Ignored: open_id={open_id[:15]}... != authorized (use /remote unpair to reset)', file=sys.stderr)

    def _handle_pairing(self, open_id: str, text: str):
        with self._lock:
            print(f'[feishu] Pairing check: code={self._pairing_code}, input="{text.strip()}"', file=sys.stderr)
            if self._pairing_code is None:
                self._send(open_id, 'No pairing code active. Run /remote start on your PC first.')
                return
            if time.time() > self._pairing_deadline:
                self._pairing_code = None
                self._send(open_id, 'Pairing code expired. Run /remote start to generate a new one.')
                return
            if text.strip() == self._pairing_code:
                self._pairing_code = None
                self._authorized_open_id = open_id
                self._paired_at = time.time()
                self._save_binding()
                self._send(open_id, "Pairing successful! I'm now connected to TUDOU_agent. Send me any message to start.")
            else:
                self._send(open_id, 'Wrong pairing code. Please try again.')

    def _auto_bind(self, open_id: str, text: str):
        with self._lock:
            self._authorized_open_id = open_id
            self._paired_at = time.time()
            self._save_binding()
            print(f'[feishu] No-code auto-bound to open_id={open_id[:15]}...', file=sys.stderr)
        self._send(open_id, "Auto-paired! I'm now connected to TUDOU_agent. Send me any message to start.")
        self._handle_chat(open_id, text)

    def _handle_chat(self, open_id: str, text: str):
        print(f'[feishu] Chat: open_id={open_id[:15]}... text="{text[:50]}"', file=sys.stderr)
        if self._agent is None:
            self._send(open_id, 'Agent not available right now.')
            return
        self._send(open_id, 'Thinking...')
        try:
            response = self._agent.run_conversation(text)
            reply = response.final_message or '(no response)'
        except Exception as e:
            reply = f'Error: {e}'
        if len(reply) > 4000:
            reply = reply[:4000] + '\n\n... (truncated)'
        self._send(open_id, reply)

    def _send(self, open_id: str, text: str):
        if self._bot:
            ok = self._bot.send_message(open_id, text)
            print(f'[feishu] Send to {open_id[:15]}...: ok={ok} text="{text[:80]}"', file=sys.stderr)
        else:
            print('[feishu] Send failed: bot is None', file=sys.stderr)

    def _save_binding(self):
        BINDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {'provider': 'feishu', 'open_id': self._authorized_open_id, 'paired_at': self._paired_at}
        BINDING_FILE.write_text(json.dumps(data))

    def _load_binding(self):
        if not BINDING_FILE.exists():
            return
        try:
            data = json.loads(BINDING_FILE.read_text())
            if data.get('provider') == 'feishu':
                self._authorized_open_id = data.get('open_id')
                self._paired_at = data.get('paired_at', 0.0)
        except (json.JSONDecodeError, KeyError):
            pass
