import time
import threading
import json
import urllib.request
import urllib.error

class TokenManager:

    def __init__(self, app_id: str, app_secret: str, base_url: str='https://open.feishu.cn/open-apis'):
        self._app_id = app_id
        self._app_secret = app_secret
        self._tenant_url = f'{base_url}/auth/v3/tenant_access_token/internal'
        self._app_url = f'{base_url}/auth/v3/app_access_token/internal'
        self._tenant_token: str | None = None
        self._tenant_expires: float = 0.0
        self._app_token: str | None = None
        self._app_expires: float = 0.0
        self._lock = threading.Lock()

    @property
    def app_id(self) -> str:
        return self._app_id

    def get_tenant_token(self) -> str:
        with self._lock:
            if self._tenant_token and time.time() < self._tenant_expires - 120:
                return self._tenant_token
            self._refresh(self._tenant_url, 'tenant_access_token')
            if self._tenant_token is None:
                raise RuntimeError('Failed to obtain Feishu tenant_access_token')
            return self._tenant_token

    def get_app_token(self) -> str:
        with self._lock:
            if self._app_token and time.time() < self._app_expires - 120:
                return self._app_token
            self._refresh(self._app_url, 'app_access_token')
            if self._app_token is None:
                raise RuntimeError('Failed to obtain Feishu app_access_token')
            return self._app_token

    def _refresh(self, url: str, key: str):
        body = json.dumps({'app_id': self._app_id, 'app_secret': self._app_secret}).encode()
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if data.get('code') != 0:
                    raise RuntimeError(f'Feishu token error ({key}): code={data.get('code')} msg={data.get('msg')}')
                if key == 'tenant_access_token':
                    self._tenant_token = data['tenant_access_token']
                    self._tenant_expires = time.time() + data.get('expire', 7200)
                else:
                    self._app_token = data['app_access_token']
                    self._app_expires = time.time() + data.get('expire', 7200)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Feishu token HTTP {e.code}: {e.reason}')
