import copy
import os
import yaml
from pathlib import Path
from typing import Any
from .defaults import DEFAULTS
from .paths import get_config_paths, find_project_config

class Settings:

    def __init__(self, cli_overrides: dict | None=None):
        self._data = copy.deepcopy(DEFAULTS)
        self._deep_merge(self._data, copy.deepcopy(DEFAULTS))
        self._load_user_config()
        self._load_project_config()
        self._load_projact_config()
        self._apply_env_overrides()
        if cli_overrides:
            self._deep_merge(self._data, cli_overrides)

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No setting '{name}'")

    def get(self, key: str, default: Any=None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> dict:
        return dict(self._data)

    def reload(self):
        self._data = copy.deepcopy(DEFAULTS)
        self._deep_merge(self._data, copy.deepcopy(DEFAULTS))
        self._load_user_config()
        self._load_project_config()
        self._load_projact_config()
        self._apply_env_overrides()

    def save_projact_config(self, key_path: str, value: str):
        self._set_nested(self._data, key_path, value)
        paths = get_config_paths()
        cfg_file = paths.get('projact_config_file')
        if not cfg_file:
            return
        existing = {}
        if cfg_file.exists():
            existing = yaml.safe_load(cfg_file.read_text(encoding='utf-8')) or {}
        self._set_nested(existing, key_path, value)
        cfg_file.write_text(yaml.dump(existing, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding='utf-8')

    def _load_user_config(self):
        paths = get_config_paths()
        cfg_file = paths['user_config_file']
        if cfg_file.exists():
            with open(cfg_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self._deep_merge(self._data, data)

    def _load_project_config(self):
        cfg_file = find_project_config()
        if cfg_file:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self._deep_merge(self._data, data)

    def _load_projact_config(self):
        paths = get_config_paths()
        cfg_file = paths.get('projact_config_file')
        if cfg_file and cfg_file.exists():
            with open(cfg_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self._deep_merge(self._data, data)

    def _apply_env_overrides(self):
        env_map = {'TUDOU_AGENT_MODEL': 'model', 'TUDOU_AGENT_PERMISSION_MODE': 'permission_mode', 'ANTHROPIC_API_KEY': 'providers.anthropic.api_key', 'OPENAI_API_KEY': 'providers.openai_compat.api_key', 'TUDOU_AGENT_BING_API_KEY': 'tools.web_search.bing_api_key'}
        for env_var, setting_path in env_map.items():
            val = os.environ.get(env_var)
            if val:
                self._set_nested(self._data, setting_path, val)

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Settings._deep_merge(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _set_nested(d: dict, path: str, value: Any):
        keys = path.split('.')
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
