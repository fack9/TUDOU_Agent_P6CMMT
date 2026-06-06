import json
import time
import uuid
import secrets
from pathlib import Path
from dataclasses import dataclass, asdict
from threading import Lock
BINDING_FILE = Path.home() / '.tudou_agent' / 'remote_binding.json'
PAIRING_TIMEOUT = 300

@dataclass
class Binding:
    token: str
    paired_at: float
    device_name: str = ''

class PairingManager:

    def __init__(self):
        self._lock = Lock()
        self._pairing_code: str | None = None
        self._pairing_deadline: float = 0
        self._binding: Binding | None = None
        self._load_binding()

    def generate_code(self) -> str:
        with self._lock:
            self._pairing_code = str(secrets.randbelow(900000) + 100000)
            self._pairing_deadline = time.time() + PAIRING_TIMEOUT
            return self._pairing_code

    def verify_code(self, code: str) -> str | None:
        with self._lock:
            if self._pairing_code is None:
                return None
            if time.time() > self._pairing_deadline:
                self._pairing_code = None
                return None
            if code == self._pairing_code:
                self._pairing_code = None
                token = uuid.uuid4().hex
                self._binding = Binding(token=token, paired_at=time.time())
                self._save_binding()
                return token
            return None

    @property
    def pairing_active(self) -> bool:
        with self._lock:
            if self._pairing_code is None:
                return False
            if time.time() > self._pairing_deadline:
                self._pairing_code = None
                return False
            return True

    @property
    def pairing_code(self) -> str | None:
        if self.pairing_active:
            return self._pairing_code
        return None

    @property
    def pairing_remaining(self) -> int:
        return max(0, int(self._pairing_deadline - time.time()))

    @property
    def is_bound(self) -> bool:
        return self._binding is not None

    @property
    def binding_info(self) -> dict | None:
        if self._binding:
            return asdict(self._binding)
        return None

    def validate_token(self, token: str) -> bool:
        if self._binding is None:
            return False
        return self._binding.token == token

    def unpair(self) -> None:
        with self._lock:
            self._binding = None
            self._save_binding()

    def _save_binding(self):
        BINDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        if self._binding:
            data = asdict(self._binding)
            BINDING_FILE.write_text(json.dumps(data))
        elif BINDING_FILE.exists():
            BINDING_FILE.unlink()

    def _load_binding(self):
        if BINDING_FILE.exists():
            try:
                data = json.loads(BINDING_FILE.read_text())
                self._binding = Binding(token=data['token'], paired_at=data['paired_at'], device_name=data.get('device_name', ''))
            except (json.JSONDecodeError, KeyError):
                self._binding = None
