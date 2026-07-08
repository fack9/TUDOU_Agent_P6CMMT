import yaml
from pathlib import Path
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from config.defaults import DEFAULTS

CONFIG_DESCRIPTIONS = {
    'model': 'LLM model identifier (e.g. deepseek-v4-pro, gpt-4o, claude-sonnet-4-6)',
    'permission_mode': 'Tool execution mode: default (ask), auto (no prompt), plan (plan-first)',
    'max_iterations': 'Maximum tool-call iterations per conversation turn',
    'bash_timeout_seconds': 'Timeout for Bash tool commands',
    'web_fetch_timeout_seconds': 'Timeout for WebFetch tool requests',
    'providers.anthropic.api_key': 'Anthropic API key (sk-ant-xxx). Leave empty to use ANTHROPIC_API_KEY env var.',
    'providers.anthropic.base_url': 'Anthropic API base URL override (leave empty for default)',
    'providers.openai_compat.api_key': 'OpenAI-compatible API key. Leave empty to use OPENAI_API_KEY env var.',
    'providers.openai_compat.base_url': 'OpenAI-compatible API base URL (e.g. https://api.deepseek.com/v1)',
    'context.max_tokens': 'Override context window size (null = use model default)',
    'context.compress_threshold': 'Trigger normal compression at this fraction of budget',
    'context.compress_urgent_threshold': 'Trigger aggressive compression at this fraction of budget',
    'context.max_tool_result_chars': 'Truncate tool results longer than this many characters',
    'context.max_history_turns': 'Maximum conversation turns kept in history',
    'context.show_usage_on_turn': 'Show context usage percentage after each response',
    'context.summary_model': 'Model used for context compression summaries (null = use main model)',
    'remote.provider': 'Remote control provider (currently only feishu is supported)',
    'remote.feishu.app_id': 'Feishu Bot App ID',
    'remote.feishu.app_secret': 'Feishu Bot App Secret',
    'remote.feishu.base_url': 'Feishu Open API base URL',
    'sandbox.enabled': 'Enable sandbox mode for Bash commands',
}


def _get_default(key_path: str) -> str:
    d = DEFAULTS
    for part in key_path.split('.'):
        if isinstance(d, dict) and part in d:
            d = d[part]
        else:
            return 'N/A'
    if d is None:
        return 'null'
    if isinstance(d, bool):
        return str(d).lower()
    if isinstance(d, (int, float)):
        return str(d)
    if isinstance(d, list):
        return str(d) if d else '[]'
    if isinstance(d, dict):
        return '{}'
    return str(d)


def _build_commented_yaml(data: dict, prefix: str = '') -> str:
    lines = []
    for key, value in data.items():
        full_key = f'{prefix}{key}' if prefix else key
        if isinstance(value, dict):
            lines.append(f'{key}:')
            for sub_line in _build_commented_yaml(value, f'{full_key}.').split('\n'):
                lines.append(f'  {sub_line}')
        elif isinstance(value, list):
            desc = CONFIG_DESCRIPTIONS.get(full_key, '')
            default = _get_default(full_key)
            lines.append(f'# {desc}')
            lines.append(f'# Default: {default}')
            lines.append(f'{key}:')
            if value:
                for item in value:
                    lines.append(f'  - {yaml.dump(item, default_flow_style=True, allow_unicode=True).strip()}')
            else:
                lines.append(f'  []')
        else:
            desc = CONFIG_DESCRIPTIONS.get(full_key, '')
            default = _get_default(full_key)
            lines.append(f'# {desc}')
            lines.append(f'# Default: {default}')
            if value is None:
                lines.append(f'{key}: null')
            elif isinstance(value, bool):
                lines.append(f'{key}: {str(value).lower()}')
            elif isinstance(value, (int, float)):
                lines.append(f'{key}: {value}')
            else:
                escaped = yaml.dump(value, default_flow_style=True, allow_unicode=True).strip()
                lines.append(f'{key}: {escaped}')
    return '\n'.join(lines)


def _diff_against_defaults(new_config: dict) -> dict:
    result = {}

    def walk(new, default, output):
        for key, default_val in default.items():
            if key not in new:
                continue
            new_val = new[key]
            if isinstance(default_val, dict) and isinstance(new_val, dict):
                sub = {}
                walk(new_val, default_val, sub)
                if sub:
                    output[key] = sub
            elif new_val != default_val:
                output[key] = new_val

    walk(new_config, DEFAULTS, result)
    return result


_CONFIG_STYLE = Style.from_dict({
    'status': 'reverse',
    'status.error': 'bg:#cc0000 #ffffff',
    'status.saved': 'bg:#00aa00 #000000',
})


class ConfigEditor:

    def __init__(self, settings_dict: dict):
        self._settings = dict(settings_dict)

    def edit(self) -> dict | None:
        yaml_text = self._build_ui_yaml()
        text_area = TextArea(text=yaml_text, multiline=True, scrollbar=True, line_numbers=False, style='class:text-area')
        text_area.text = yaml_text

        kb = KeyBindings()

        @kb.add('c-s')
        def _save(event):
            event.app.exit(result='save')

        @kb.add('c-x')
        @kb.add('escape')
        def _cancel(event):
            event.app.exit(result='cancel')

        saved_flag = [False]
        error_msg = ['']

        def get_status():
            if error_msg[0]:
                return [('class:status.error', f'  YAML Error: {error_msg[0]}  ')]
            if saved_flag[0]:
                return [('class:status.saved', '  Saved! Restart may be needed for some settings.  ')]
            return [('class:status', '  Ctrl+S: Save & Apply  |  Ctrl+X / Esc: Exit without saving  |  Arrow keys / PgUp / PgDn: Navigate  ')]

        status_win = Window(height=1, content=FormattedTextControl(text=get_status), style='class:status')

        root_container = HSplit([
            text_area,
            status_win,
        ])

        layout = Layout(root_container)
        app = Application(layout=layout, key_bindings=kb, full_screen=True, style=_CONFIG_STYLE)

        result = app.run()

        if result == 'cancel':
            return None

        edited_text = text_area.text
        try:
            new_config = yaml.safe_load(edited_text) or {}
        except yaml.YAMLError as e:
            error_msg[0] = str(e)
            return None

        return new_config

    def _build_ui_yaml(self) -> str:
        header = (
            '# ============================================================\n'
            '#  TUDOU Agent Configuration\n'
            '# ============================================================\n'
            '#  Ctrl+S : Save and apply    Ctrl+X / Esc : Exit without saving\n'
            '#\n'
            '#  This editor shows the FULL merged configuration.\n'
            '#  Only values that differ from defaults are saved.\n'
            '#\n'
        )
        body = _build_commented_yaml(self._settings)
        return header + '\n' + body


def save_config(new_config: dict, projact_config_file: Path) -> bool:
    overrides = _diff_against_defaults(new_config)
    projact_config_file.parent.mkdir(parents=True, exist_ok=True)
    projact_config_file.write_text(
        yaml.dump(overrides, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding='utf-8')
    return True
