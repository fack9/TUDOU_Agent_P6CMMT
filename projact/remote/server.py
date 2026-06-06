from __future__ import annotations
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any
import qrcode
from flask import Flask
from .auth import PairingManager
from .handlers import create_api_blueprint
WEB_UI_DIR = Path(__file__).resolve().parent / 'web_ui'

def _ensure_firewall_rule(port: int) -> str | None:
    import subprocess
    rule_name = f'TUDOU_Agent_Remote_{port}'
    try:
        check = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
        if check.returncode == 0 and 'No rules match' not in check.stdout:
            return None
    except Exception:
        pass
    try:
        result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', f'name={rule_name}', 'dir=in', 'action=allow', 'protocol=TCP', f'localport={port}'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        if result.returncode == 0:
            return None
        err = result.stderr.strip() or result.stdout.strip()
        return f'not-admin: {err}' if '提升' in err or 'elevat' in err.lower() else err or 'firewall rule failed'
    except Exception as e:
        return str(e)

def _self_test(ip: str, port: int) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(f'http://{ip}:{port}/api/status', method='GET')
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False

def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return '127.0.0.1'

def _gen_qrcode_ascii(url: str) -> str:
    qr = qrcode.QRCode(border=2, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    lines = []
    for row in matrix:
        line = ''.join(('██' if cell else '  ' for cell in row))
        lines.append(line)
    return '\n'.join(lines)

class RemoteServer:

    def __init__(self, agent: Any=None, port: int=9877):
        self._agent = agent
        self.port = port
        self.pairing = PairingManager()
        self._flask: Flask | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._startup_error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_agent(self, agent: Any):
        self._agent = agent

    def start(self) -> dict:
        if self._running:
            return {'ok': False, 'error': 'already running'}
        app = Flask(__name__, static_folder=str(WEB_UI_DIR), static_url_path='')

        @app.route('/')
        def index():
            return app.send_static_file('index.html')
        api = create_api_blueprint(self.pairing, lambda: self._agent)
        app.register_blueprint(api)
        self._flask = app
        self._startup_error = None
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        time.sleep(0.8)
        if not self._running:
            err = self._startup_error or 'unknown error'
            return {'ok': False, 'error': f'Server failed to start: {err}'}
        fw_result = _ensure_firewall_rule(self.port)
        pairing_code = self.pairing.generate_code()
        ip = _get_local_ip()
        url = f'http://{ip}:{self.port}'
        qr_ascii = _gen_qrcode_ascii(url)
        reachable = _self_test(ip, self.port)
        return {'ok': True, 'url': url, 'port': self.port, 'pairing_code': pairing_code, 'qr_ascii': qr_ascii, 'ip': ip, 'fw_error': fw_result, 'self_test_ok': reachable}

    def stop(self) -> dict:
        if not self._running:
            return {'ok': False, 'error': 'not running'}
        self._running = False
        return {'ok': True}

    def status(self) -> dict:
        ip = _get_local_ip()
        return {'running': self._running, 'url': f'http://{ip}:{self.port}' if self._running else None, 'port': self.port, 'bound': self.pairing.is_bound, 'pairing_active': self.pairing.pairing_active, 'pairing_code': self.pairing.pairing_code, 'pairing_remaining': self.pairing.pairing_remaining}

    def _run_server(self):
        try:
            self._flask.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False, threaded=True)
        except Exception as e:
            self._running = False
            self._startup_error = str(e)
            print(f'[remote] Flask server error: {e}', file=sys.stderr)
