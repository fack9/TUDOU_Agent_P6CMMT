import math
import shutil
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path
from config.settings import Settings
from config.paths import get_config_paths, get_projact_dir
from llm.client import LLMClient
from tools.registry import ToolRegistry
from tools.plan_mode import EnterPlanModeTool, ExitPlanModeTool
from tools.bash import BashTool
from tools.file_read import ReadTool
from tools.file_write import WriteTool
from tools.file_edit import EditTool
from tools.glob_tool import GlobTool
from tools.grep import GrepTool
from tools.web_search import WebSearchTool
from tools.web_fetch import WebFetchTool
from tools.browser_fetch import BrowserFetchTool
from tools.ccr_retrieve import RetrieveTool
from tools.agent_delegate import AgentTool
from tools.software_cli import SoftwareCLITool
from tools.task_manager import TaskManager, TaskCreateTool, TaskUpdateTool, TaskListTool
from context.manager import ContextManager
from context.ccr import CCRStore
from hooks.manager import HookManager
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from agent import TUDOU_Agent
from session.memory import MemoryManager
from session.store import SessionStore
from permissions.enforcer import PermissionEnforcer
from permissions.modes import PermissionMode
from permissions.rules import load_rules, save_rules
from mcp import MCPManager
from ui.renderer import Renderer
from ui.spinner import TUDOU_spinner
from ui.input_handler import InputHandler
from ui.effects import typewriter2
from ui.config_editor import ConfigEditor, save_config
from remote_feishu import FeishuRelay
PROJACT_DIR = get_projact_dir()
HISTORY_MD_FILE = PROJACT_DIR / 'history.md'
LANG_MAP = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript', '.html': 'html', '.css': 'css', '.scss': 'scss', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.md': 'markdown', '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash', '.java': 'java', '.kt': 'kotlin', '.swift': 'swift', '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.rs': 'rust', '.go': 'go', '.sql': 'sql', '.xml': 'xml', '.cfg': 'ini', '.rb': 'ruby', '.php': 'php', '.lua': 'lua', '.r': 'r', '.dockerfile': 'dockerfile', '.gitignore': 'gitignore'}

def _guess_lang(file_path: str) -> str:
    p = Path(file_path)
    suffix = p.suffix.lower()
    if suffix:
        return LANG_MAP.get(suffix, '')
    name = p.name.lower()
    return LANG_MAP.get(f'.{name}', '')

def _read_file_if_exists(file_path: str) -> str | None:
    if not file_path:
        return None
    try:
        return Path(file_path).read_text(encoding='utf-8', errors='replace')
    except (OSError, PermissionError):
        return None

def _find_upward(name: str, max_depth: int=5) -> Path | None:
    root = PROJACT_DIR
    for _ in range(max_depth):
        candidate = root / name
        if candidate.exists():
            return candidate
        for child in root.iterdir():
            if child.is_dir():
                candidate = child / name
                if candidate.exists():
                    return candidate
        root = root.parent
    return None
BUILTIN_SKILLS_DIR = PROJACT_DIR / 'builtin_skills'
SPLASH_TEXT_FILE = _find_upward('TUDOU_effect.txt') or Path('TUDOU_effect.txt')
DANGERSKILLS_DIR = _find_upward('dangerskills') or PROJACT_DIR.parent / 'dangerskills'
MEMORY_DIR = _find_upward('memory') or PROJACT_DIR / 'memory'

class TUDOU_CLI:

    def __init__(self, cli_args: dict | None=None):
        self.settings = Settings(cli_args)
        paths = get_config_paths()
        ctx_cfg = self.settings.get('context', {})
        self.context = ContextManager(max_history_turns=ctx_cfg.get('max_history_turns', 50), max_tool_result_chars=ctx_cfg.get('max_tool_result_chars', 15000), memory_dir=MEMORY_DIR)
        self.memory_manager = MemoryManager(MEMORY_DIR)
        self.session_store = SessionStore(paths['user_sessions_db'])
        self._conv_id = uuid.uuid4().hex[:12]
        self.task_manager = TaskManager(self._conv_id, paths['user_config_dir'])
        self.permission_enforcer = PermissionEnforcer()
        self._permissions_file = paths['user_permissions_file']
        self._load_permission_rules()
        self.renderer = Renderer()
        self._plans_dir = PROJACT_DIR / 'plans'
        self._plan_state: dict = {'active': False, 'plan_file': None}
        self._live_tools_file = paths['user_config_dir'] / 'live_tools.json'
        self.ccr = CCRStore()
        hooks_dir = PROJACT_DIR.parent / 'hook'
        self.hooks = HookManager(str(hooks_dir), cwd=str(self.context.working_dir))
        self.llm = LLMClient(self.settings)
        self.tools = ToolRegistry()
        self._register_tools()
        self._load_live_tools()
        self.agent = TUDOU_Agent(settings=self.settings, llm_client=self.llm, tool_registry=self.tools, context_manager=self.context, plan_state=self._plan_state, ccr_store=self.ccr, hook_manager=self.hooks)
        remote_cfg = self.settings.get('remote', {})
        feishu_cfg = remote_cfg.get('feishu', {})
        self.remote = FeishuRelay(agent=self.agent, app_id=feishu_cfg.get('app_id', ''), app_secret=feishu_cfg.get('app_secret', ''), base_url=feishu_cfg.get('base_url', 'https://open.feishu.cn/open-apis'))
        self._code_mode = False
        self._shell_active = False
        self._shell_cwd = str(Path.cwd())
        self.input_handler = InputHandler(history_file=paths.get('user_history_file'), get_plan_state=lambda: self._plan_state.get('active', False), get_code_mode=lambda: self._code_mode, get_shell_mode=lambda: self._shell_active)
        self._running = False
        self._root_mode = False
        self._auto_approve = False
        self._quiet_ui = False
        self._subagent_mode = False
        self._title_generated = False
        self._conv_created = False
        self._last_panel_lines = 0
        self._panel_rendered = False
        self._panel_running = False
        self._panel_thread = None
        self.skills = SkillRegistry()
        self.skills.add_search_path(str(BUILTIN_SKILLS_DIR))
        discovered = self.skills.discover()
        if discovered > 0:
            self.renderer.render_text(f'[dim]Loaded {discovered} skills from builtin_skills/[/dim]')
        mcp_cfg = self.settings.get('mcp', {})
        self.mcp_manager = MCPManager(mcp_cfg.get('servers', []))
        mcp_connected = self.mcp_manager.discover(self.tools)
        if mcp_connected > 0:
            self.renderer.render_text(f'[dim]MCP: {mcp_connected} server(s), {self.tools.tool_count()} total tools[/dim]')
        DANGERSKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_permission_rules(self):
        for rule in load_rules(self._permissions_file):
            tool = rule.get('tool', '*')
            pattern = rule.get('pattern', '*')
            action = rule.get('action', 'deny')
            self.permission_enforcer.add_rule(tool, pattern, action)
        mode_str = self.settings.get('permission_mode', 'default')
        try:
            self.permission_enforcer.mode = PermissionMode(mode_str)
        except ValueError:
            self.permission_enforcer.mode = PermissionMode.DEFAULT

    def _save_permission_rules(self):
        rules = [{'tool': t, 'pattern': p, 'action': a} for t, p, a in self.permission_enforcer._rules]
        save_rules(rules, self._permissions_file)

    def _save_to_history_md(self, user_input: str, response):
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines = [f'## {now} | conv: `{self._conv_id}` | model: `{self.settings.model}`', '', f'**User:** ', f'{user_input}', '', f'**Agent:** ', f'{response.final_message}', '']
        if response.tool_stats:
            stats_parts = [f'{k}: {v}' for k, v in response.tool_stats.items()]
            tok = response.token_usage
            lines.append(f'**Stats:** tools: {", ".join(stats_parts)} | tokens: {tok.input}+{tok.output} | {response.duration_ms}ms')
        else:
            tok = response.token_usage
            lines.append(f'**Stats:** tokens: {tok.input}+{tok.output} | {response.duration_ms}ms')
        lines.append('')
        lines.append('---')
        lines.append('')
        try:
            with open(HISTORY_MD_FILE, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except (OSError, PermissionError):
            pass

    def _pass_to_llm(self, parts: list[str]) -> bool:
        text = ' '.join(parts)
        if text.startswith('/'):
            text = text[1:]
        self._process_input(text)
        return True

    def _register_tools(self):
        workdir = str(self.context.working_dir)
        timeout = self.settings.get('bash_timeout_seconds', 120)
        self.tools.register_tool(BashTool(timeout=timeout, workdir=workdir))
        self.tools.register_tool(ReadTool(workdir=workdir))
        self.tools.register_tool(WriteTool(workdir=workdir))
        self.tools.register_tool(EditTool(workdir=workdir))
        self.tools.register_tool(GlobTool(workdir=workdir))
        self.tools.register_tool(GrepTool(workdir=workdir))
        tools_cfg = self.settings.get('tools', {})
        ws_cfg = tools_cfg.get('web_search', {})
        wf_cfg = tools_cfg.get('web_fetch', {})
        self.tools.register_tool(WebSearchTool(bing_api_key=ws_cfg.get('bing_api_key')))
        self.tools.register_tool(WebFetchTool(llm_client=self.llm, extraction_model=wf_cfg.get('extraction_model'), extraction_api_key=wf_cfg.get('extraction_api_key'), extraction_base_url=wf_cfg.get('extraction_base_url')))
        self.tools.register_tool(BrowserFetchTool())
        self.tools.register_tool(RetrieveTool(ccr_store=self.ccr))
        self._agent_tool = AgentTool(llm_client=self.llm, tool_registry=self.tools, settings=self.settings)
        self.tools.register_tool(EnterPlanModeTool(self._plan_state, self._plans_dir))
        self.tools.register_tool(ExitPlanModeTool(self._plan_state))
        self.tools.register_tool(TaskCreateTool(self.task_manager))
        self.tools.register_tool(TaskUpdateTool(self.task_manager))
        self.tools.register_tool(TaskListTool(self.task_manager))

    def run(self):
        self._show_splash()
        self.renderer.welcome()
        self._running = True
        while self._running:
            try:
                user_input = self.input_handler.get_input()
                if not user_input:
                    continue
                if user_input.startswith('!'):
                    self._shell_active = True
                    self._shell_cwd = str(Path.cwd())
                    cmd = user_input[1:].strip()
                    if cmd:
                        self._handle_shell(cmd)
                    continue
                if self._shell_active:
                    if user_input.lower() == '/downshell':
                        self._shell_active = False
                        self.renderer.render_text('[dim]Shell mode exited. Type normally to chat with the agent.[/dim]')
                        continue
                    self._handle_shell(user_input)
                    continue
                if self._handle_slash_command(user_input):
                    continue
                self._panel_rendered = False
                self._last_panel_lines = 0
                self._auto_approve = False
                self._process_input(user_input)
            except KeyboardInterrupt:
                self.renderer.render_text('\n[dim]Interrupted. Type /help for available commands.[/dim]')
                self._code_mode = False
                self.agent.code_mode = False
                continue

    def _handle_shell(self, cmd: str):
        import subprocess
        import shlex
        stripped = cmd.strip()
        if stripped.startswith('cd ') or stripped == 'cd':
            try:
                parts = shlex.split(stripped, posix=False)
            except ValueError:
                parts = stripped.split()
            if len(parts) == 1:
                target = str(Path.home())
            else:
                target = parts[1]
            new_dir = Path(target)
            if not new_dir.is_absolute():
                new_dir = (Path(self._shell_cwd) / target).resolve()
            else:
                new_dir = new_dir.resolve()
            if new_dir.is_dir():
                self._shell_cwd = str(new_dir)
                self.renderer.render_text(f'[dim]cwd: {self._shell_cwd}[/dim]')
            else:
                self.renderer.render_error(f'cd: no such directory: {target}')
            return
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=self._shell_cwd)
            if result.stdout:
                self.renderer.render_text(result.stdout.rstrip())
            if result.stderr:
                self.renderer.render_error(result.stderr.rstrip())
            if result.returncode != 0 and not result.stderr:
                self.renderer.render_text(f'[dim]exit: {result.returncode}[/dim]')
        except KeyboardInterrupt:
            self.renderer.render_text('\n[dim]Shell command interrupted.[/dim]')
        except subprocess.TimeoutExpired:
            self.renderer.render_error('Command timed out (60s)')
        except Exception as e:
            self.renderer.render_error(str(e))

    def _show_splash(self):
        if not SPLASH_TEXT_FILE.exists():
            return
        text = SPLASH_TEXT_FILE.read_text(encoding='utf-8', errors='replace').strip()
        if text:
            typewriter2(text, char_time=0.0023, glitch_chars=1, scramble_color='cyan', char_color='cyan')

    def _handle_slash_command(self, text: str) -> bool:
        parts = text.split()
        cmd = parts[0].lower()
        if cmd in ('/exit', '/quit'):
            self._running = False
            self.mcp_manager.shutdown()
            self.renderer.render_text('Goodbye!')
            return True
        if cmd == '/help':
            self._show_help()
            return True
        if cmd == '/clear':
            self.context.clear_history()
            self.renderer.render_text('[cleared conversation history]')
            return True
        if cmd == '/model':
            if len(parts) > 1:
                new_model = parts[1]
                self.settings.save_projact_config('model', new_model)
                self.llm._default_model = new_model
                self.agent.tracker.model = new_model
                self.renderer.render_text(f'[green]Model set to:[/green] [cyan]{new_model}[/cyan]')
            else:
                self.renderer.render_text(f'Current model: [cyan]{self.settings.model}[/cyan]')
            return True
        if cmd == '/tools':
            names = self.tools.list_tools()
            if names:
                self.renderer.render_text('Available tools:\n' + '\n'.join((f'  - {n}' for n in names)))
            else:
                self.renderer.render_text('No tools registered.')
            return True
        if cmd == '/tasks':
            self._show_tasks()
            return True
        if cmd == '/tudou':
            self._show_tudou_info()
            return True
        if cmd == '/context':
            self._show_context()
            return True
        if cmd == '/setmapi':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /setMAPI <api_key>')
                return True
            self.settings.save_projact_config('providers.openai_compat.api_key', parts[1])
            self.renderer.render_text(f'[green]API key saved:[/green] {self._mask(parts[1])}')
            return True
        if cmd == '/setmurl':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /setMURL <base_url>')
                return True
            self.settings.save_projact_config('providers.openai_compat.base_url', parts[1])
            self.renderer.render_text(f'[green]API base URL saved:[/green] {parts[1]}')
            return True
        if cmd == '/setfid':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /setFID <app_id>')
                return True
            self.settings.save_projact_config('remote.feishu.app_id', parts[1])
            self.renderer.render_text(f'[green]Feishu App ID saved:[/green] {parts[1]}')
            return True
        if cmd == '/setfas':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /setFAS <app_secret>')
                return True
            self.settings.save_projact_config('remote.feishu.app_secret', parts[1])
            self.renderer.render_text(f'[green]Feishu App Secret saved:[/green] {self._mask(parts[1])}')
            return True
        if cmd == '/remote':
            sub = parts[1] if len(parts) > 1 else 'status'
            nocode = len(parts) > 2 and parts[2] == 'nocode'
            if sub == 'start':
                self._remote_start(nocode=nocode)
            elif sub == 'stop':
                self._remote_stop()
            elif sub == 'status':
                self._remote_status()
            elif sub == 'unpair':
                self._remote_unpair()
            else:
                self.renderer.render_text('Usage: /remote [start|stop|status|unpair]  (start also accepts: start nocode)')
            return True
        if cmd == '/skills':
            skill_list = self.skills.list_skills()
            if skill_list:
                lines = [f'Available skills ({len(skill_list)}):']
                for s in skill_list:
                    marker = ' [active]' if self.skills.active_skill and self.skills.active_skill.name == s['name'] else ''
                    lines.append(f'  - {s['name']}: {s['description']}{marker}')
                self.renderer.render_text('\n'.join(lines))
            else:
                self.renderer.render_text('No skills loaded.')
            return True
        if cmd == '/activate':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /activate <skill_name>')
                return True
            name = parts[1]
            if self.skills.activate(name):
                self.renderer.render_text(f'Activated skill: {name}')
            else:
                self.renderer.render_text(f'Skill not found: {name}')
            return True
        if cmd == '/deactivate':
            current = self.skills.active_skill.name if self.skills.active_skill else None
            self.skills.deactivate()
            if current:
                self.renderer.render_text(f'Deactivated skill: {current}')
            else:
                self.renderer.render_text('No skill was active.')
            return True
        if cmd == '/importdangerskills':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /importdangerskills <folder_name>')
                return True
            folder_name = parts[1]
            result = self._import_danger_skill(folder_name)
            self.renderer.render_text(result)
            return True
        if cmd == '/removeskills':
            if len(parts) < 2:
                self.renderer.render_text('Usage: /removeskills <folder_name>')
                return True
            folder_name = parts[1]
            result = self._remove_skill(folder_name)
            self.renderer.render_text(result)
            return True
        if cmd == '/rootmodel':
            self._root_mode = not self._root_mode
            self.agent.root_mode = self._root_mode
            status = '[bold green]ON[/bold green]' if self._root_mode else '[dim]OFF[/dim]'
            self.renderer.render_text(f'Root mode: {status}  — Agent will {"" if self._root_mode else "NOT "}auto-execute without asking.')
            return True
        if cmd == '/betterui':
            self._quiet_ui = not self._quiet_ui
            status = '[bold green]ON[/bold green]' if self._quiet_ui else '[dim]OFF[/dim]'
            self.renderer.render_text(f'Better UI: {status}  — Noise reduction {"enabled" if self._quiet_ui else "disabled"}.')
            return

        if cmd == '/subagent':
            self._subagent_mode = not self._subagent_mode
            if self._subagent_mode:
                self.tools.register_tool(self._agent_tool)
            else:
                self.tools._tools.pop('Agent', None)
            status = '[bold green]ON[/bold green]' if self._subagent_mode else '[dim]OFF[/dim]'
            self.renderer.render_text(f'Sub-agent mode: {status}  — Agent {"can" if self._subagent_mode else "CANNOT"} spawn sub-agents for parallel task delegation.')
            return True
        if cmd == '/memory':
            return self._handle_memory(parts)
        if cmd == '/history':
            return self._handle_history(parts)
        if cmd == '/resume':
            return self._handle_resume(parts)
        if cmd in ('/permissions', '/permission'):
            return self._handle_permissions(parts)
        if cmd == '/mcp':
            self._handle_mcp()
            return True
        if cmd == '/config':
            self._handle_config()
            return True
        if cmd == '/buildcli':
            self._handle_buildcli(parts)
            return True
        if cmd == '/export':
            return self._handle_export(parts)
        return False

    def _handle_export(self, parts: list[str]) -> bool:
        conv_id = parts[1] if len(parts) > 1 else self._conv_id
        msgs = self.session_store.load_messages(conv_id)
        if not msgs:
            self.renderer.render_text(f'[yellow]Session not found: {conv_id}[/yellow]')
            return True
        import datetime
        sessions = {s['id']: s for s in self.session_store.get_conversations()}
        session_info = sessions.get(conv_id, {})
        created_ts = session_info.get('created_at', 0)
        created_str = datetime.datetime.fromtimestamp(created_ts).strftime('%Y-%m-%d_%H%M') if created_ts else 'unknown'
        model = session_info.get('model', '?')
        title = session_info.get('summary', '') or 'conversation'
        safe_title = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in title)[:40].strip()
        filename = f'TUDOU_export_{safe_title}_{created_str}.md'
        filepath = Path.cwd() / filename
        lines = [
            f'# TUDOU_agent — 会话导出',
            f'',
            f'- **会话 ID**: `{conv_id}`',
            f'- **日期**: {datetime.datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M") if created_ts else "未知"}',
            f'- **模型**: {model}',
            f'- **消息数**: {len(msgs)}',
            f'- **LLM 标题**: {title}',
            f'',
            f'---',
            f'',
        ]
        for i, m in enumerate(msgs):
            if m['role'] == 'user':
                lines.append(f'### [{i+1}] User')
            else:
                lines.append(f'### [{i+1}] Assistant')
            lines.append('')
            lines.append(m['content'])
            lines.append('')
            lines.append('---')
            lines.append('')
        try:
            filepath.write_text('\n'.join(lines), encoding='utf-8')
            self.renderer.render_text(f'[green]Exported {len(msgs)} messages to:[/green] [cyan]{filepath}[/cyan]')
        except OSError as e:
            self.renderer.render_error(f'Failed to write export file: {e}')
        return True

    def _import_danger_skill(self, folder_name: str) -> str:
        src = DANGERSKILLS_DIR / folder_name
        if not src.exists():
            return f"Error: '{folder_name}' not found in {DANGERSKILLS_DIR}"
        if not (src / 'SKILL.md').exists():
            return f"Error: '{folder_name}' does not contain a SKILL.md file"
        dst = BUILTIN_SKILLS_DIR / folder_name
        if dst.exists():
            return f"Error: '{folder_name}' already exists in builtin_skills/"
        shutil.copytree(str(src), str(dst))
        skill = SkillLoader.load_from_dir(dst)
        if skill:
            self.skills.register(skill)
            return f'Imported and registered: {skill.name} — {skill.description}'
        return f"Imported '{folder_name}' to builtin_skills/ (SKILL.md parsing failed)"

    def _remove_skill(self, folder_name: str) -> str:
        src = BUILTIN_SKILLS_DIR / folder_name
        if not src.exists():
            return f"Error: '{folder_name}' not found in builtin_skills/"
        if self.skills.active_skill and self.skills.active_skill.name == folder_name:
            self.skills.deactivate()
        dst = DANGERSKILLS_DIR / folder_name
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.move(str(src), str(dst))
        self.skills = SkillRegistry()
        self.skills.add_search_path(str(BUILTIN_SKILLS_DIR))
        self.skills.discover()
        return f"Moved '{folder_name}' from builtin_skills/ to dangerskills/"

    def _handle_memory(self, parts: list[str]) -> bool:
        if len(parts) > 1 and parts[1].upper() == 'LLM':
            return self._pass_to_llm(parts)
        sub = parts[1] if len(parts) > 1 else 'list'
        if sub == 'list':
            files = self.memory_manager.list_files()
            if not files:
                self.renderer.render_text('[dim]No memories found.[/dim]')
                return True
            lines = ['[bold]Memories:[/bold]']
            for f in files:
                mem = self.memory_manager.load(f.name)
                if mem:
                    lines.append(f'  [cyan]{f.name}[/cyan] — {mem["name"]} [{mem["type"]}]')
            self.renderer.render_text('\n'.join(lines))
            return True
        if sub == 'show':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /memory show <filename>')
                return True
            mem = self.memory_manager.load(parts[2])
            if not mem:
                self.renderer.render_text(f'[yellow]Memory not found: {parts[2]}[/yellow]')
                return True
            self.renderer.render_text(f'[bold]{mem["name"]}[/bold] [{mem["type"]}]\n[dim]{mem["description"]}[/dim]\n\n{mem["content"]}')
            return True
        if sub == 'delete':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /memory delete <filename>')
                return True
            if self.memory_manager.delete(parts[2]):
                self.memory_manager.remove_from_index(parts[2])
                self.renderer.render_text(f'[green]Deleted: {parts[2]}[/green]')
            else:
                self.renderer.render_text(f'[yellow]Memory not found: {parts[2]}[/yellow]')
            return True
        self.renderer.render_text('Usage: /memory [list|show <file>|delete <file>|LLM <query>]')
        return True

    def _handle_history(self, parts: list[str]) -> bool:
        if len(parts) > 1 and parts[1].upper() == 'LLM':
            return self._pass_to_llm(parts)
        sub = parts[1] if len(parts) > 1 else 'list'
        if sub == 'list':
            sessions = self.session_store.get_conversations()
            if not sessions:
                self.renderer.render_text('[dim]No saved conversations.[/dim]')
                return True
            import datetime
            lines = [f'[bold]Saved conversations ({len(sessions)}):[/bold]']
            for s in sessions:
                dt = datetime.datetime.fromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M')
                conv_id = s['id']
                marker = ' [cyan](current)[/cyan]' if conv_id == self._conv_id else ''
                title = s.get('summary') or ''
                if not title:
                    msgs = self.session_store.load_messages(conv_id)
                    for m in msgs:
                        if m['role'] == 'user':
                            title = m['content'].replace('\n', ' ')[:60]
                            break
                    if title:
                        title = f'(untitled) "{title}..."'
                    else:
                        title = '(empty)'
                msg_count = len(self.session_store.load_messages(conv_id))
                lines.append(f'  ID={conv_id}{marker} — {dt} — {msg_count}msgs — LLM title: {title}')
            lines.append('\n[dim]/history recent — current session  |  /history show <id> — view session  |  /history LLM <query>[/dim]')
            self.renderer.render_text('\n'.join(lines))
            return True
        if sub == 'recent':
            messages = self.context._history
            if not messages:
                self.renderer.render_text('[dim]No conversation history in current session.[/dim]')
                return True
            lines = [f'[bold]Current session — {len(messages)} messages:[/bold]']
            for i, msg in enumerate(messages[-20:]):
                role = '[bold cyan]You[/bold cyan]' if msg['role'] == 'user' else '[bold yellow]Agent[/bold yellow]'
                content = msg.get('content', '')
                if len(content) > 200:
                    content = content[:200] + '...'
                content = content.replace('\n', ' ')
                lines.append(f'  [{i+1}] {role}: {content}')
            self.renderer.render_text('\n'.join(lines))
            return True
        if sub == 'show':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /history show <conv_id>')
                return True
            msgs = self.session_store.load_messages(parts[2])
            if not msgs:
                self.renderer.render_text(f'[yellow]Session not found: {parts[2]}[/yellow]')
                return True
            lines = [f'[bold]Session {parts[2]} ({len(msgs)} messages):[/bold]']
            for i, m in enumerate(msgs):
                role = '[bold cyan]You[/bold cyan]' if m['role'] == 'user' else '[bold yellow]Agent[/bold yellow]'
                content = m.get('content', '')[:300]
                lines.append(f'  [{i+1}] {role}: {content}')
            self.renderer.render_text('\n'.join(lines))
            return True
        self.renderer.render_text('Usage: /history [list|recent|show <id>|LLM <query>]')
        return True

    def _handle_resume(self, parts: list[str]) -> bool:
        if not parts[1:]:
            self.renderer.render_text('Usage: /resume [list|list all|clear|<conv_id>]')
            return True
        sub = parts[1]
        if sub == 'delete':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /resume delete <conv_id>')
                return True
            target_id = parts[2]
            msgs = self.session_store.load_messages(target_id)
            msg_count = len(msgs)
            self.session_store.delete_conversation(target_id)
            if target_id == self._conv_id:
                import uuid
                self.context.clear_history()
                self._conv_id = uuid.uuid4().hex[:12]
                self._conv_created = False
                self.task_manager.switch_conversation(self._conv_id)
                self._last_panel_lines = 0
            self.renderer.render_text(f'[green]Deleted session [cyan]{target_id}[/cyan] ({msg_count} messages)[/green]')
            return True
        if sub == 'import':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /resume import <file.md>')
                return True
            filepath = Path(parts[2])
            if not filepath.is_absolute():
                filepath = Path.cwd() / filepath
            if not filepath.exists():
                self.renderer.render_text(f'[yellow]File not found: {filepath}[/yellow]')
                return True
            try:
                content = filepath.read_text(encoding='utf-8')
            except OSError as e:
                self.renderer.render_error(f'Failed to read file: {e}')
                return True
            import re
            import uuid
            import datetime
            pattern = r'### \[(\d+)\] (User|Assistant)\s*\n(.*?)(?=\n### \[|\Z)'
            matches = re.findall(pattern, content, re.DOTALL)
            if not matches:
                self.renderer.render_text('[yellow]No valid conversation messages found in file.[/yellow]')
                return True
            new_id = uuid.uuid4().hex[:12]
            now = time.time()
            with sqlite3.connect(str(self.session_store.db_path)) as conn:
                conn.execute('INSERT INTO conversations (id, created_at, model, summary) VALUES (?, ?, ?, ?)',
                             (new_id, now, '', f'Imported from {filepath.name}'))
                for i, (idx, role, text) in enumerate(matches):
                    conn.execute('INSERT INTO messages (conv_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
                                 (new_id, role.lower(), text.strip(), now + i))
                conn.commit()
            self.context.clear_history()
            for m in matches:
                self.context.add_to_history({'role': m[1].lower(), 'content': m[2].strip()})
            self._conv_id = new_id
            self._conv_created = True
            self._title_generated = True
            self.task_manager.switch_conversation(self._conv_id)
            self._last_panel_lines = 0
            self.renderer.render_text(f'[green]Imported {len(matches)} messages as new session:[/green] [cyan]{new_id}[/cyan]')
            return True
        if sub == 'clear':
            count = len(self.session_store.get_conversations())
            if count == 0:
                self.renderer.render_text('[dim]No saved conversations to clear.[/dim]')
                return True
            self.session_store.delete_all_conversations()
            import uuid
            self.context.clear_history()
            self._conv_id = uuid.uuid4().hex[:12]
            self._title_generated = False
            self._conv_created = True
            self._last_panel_lines = 0
            self.task_manager.switch_conversation(self._conv_id)
            self.session_store.create_conversation(self._conv_id, model=self.settings.model)
            self.renderer.render_text(f'[green]Cleared {count} conversation(s). New session: [cyan]{self._conv_id}[/cyan][/green]')
            return True
        if sub == 'list':
            show_all = len(parts) > 2 and parts[2] == 'all'
            sessions = self.session_store.get_conversations()
            if not sessions:
                self.renderer.render_text('[dim]No saved conversations.[/dim]')
                return True
            import datetime
            lines = [f'[bold]Saved conversations ({len(sessions)}):[/bold]']
            for s in sessions:
                dt = datetime.datetime.fromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M')
                conv_id = s['id']
                marker = ' [cyan](current)[/cyan]' if conv_id == self._conv_id else ''
                title = s.get('summary') or ''
                msgs = self.session_store.load_messages(conv_id)
                msg_count = len(msgs)
                if not title:
                    for m in msgs:
                        if m['role'] == 'user':
                            title = m['content'].replace('\n', ' ')[:60]
                            break
                    if title:
                        title = f'(untitled) "{title}..."'
                    else:
                        title = '(empty)'
                lines.append(f'  ID={conv_id}{marker} — {dt} — {msg_count}msgs — LLM title: {title}')
                if show_all:
                    user_count = 0
                    for m in msgs:
                        if m['role'] == 'user':
                            user_count += 1
                            content = m['content'].replace('\n', '\\n')
                            lines.append(f'    [{user_count}] {content}')
                            if user_count >= 2:
                                break
            hint = 'Use /resume <id> to switch.  /resume list all — show first 2 messages'
            lines.append(f'\n[dim]{hint}[/dim]')
            self.renderer.render_text('\n'.join(lines))
            return True
        conv_id = sub
        msgs = self.session_store.load_messages(conv_id)
        if not msgs:
            self.renderer.render_text(f'[yellow]Session not found: {conv_id}[/yellow]')
            return True
        self.context.clear_history()
        for m in msgs:
            self.context.add_to_history(m)
        old_conv_id = self._conv_id
        self._conv_id = conv_id
        self._conv_created = True
        self._last_panel_lines = 0
        self.task_manager.switch_conversation(self._conv_id)
        import datetime
        sessions = {s['id']: s for s in self.session_store.get_conversations()}
        dt = ''
        if conv_id in sessions:
            dt = datetime.datetime.fromtimestamp(sessions[conv_id]['created_at']).strftime('%Y-%m-%d %H:%M')
            dt = f' from {dt}'
        self.renderer.render_text(f'[green]Resumed session[/green] [cyan]{conv_id}[/cyan]{dt} — {len(msgs)} messages loaded (was {old_conv_id})')
        return True

    def _handle_permissions(self, parts: list[str]) -> bool:
        if len(parts) > 1 and parts[1].upper() == 'LLM':
            return self._pass_to_llm(parts)
        sub = parts[1] if len(parts) > 1 else 'status'
        if sub == 'status':
            mode = self.permission_enforcer.mode.value
            rules = self.permission_enforcer._rules
            lines = [f'[bold]Permission Mode:[/bold] [cyan]{mode}[/cyan]']
            if rules:
                lines.append('[bold]Rules:[/bold]')
                for t, p, a in rules:
                    action_color = '[green]' if a == 'allow' else '[red]'
                    lines.append(f'  {action_color}{a:5}[/]  tool={t:15}  pattern={p}')
            else:
                lines.append('[dim]No custom rules.[/dim]')
            lines.append('\n[dim]Usage: /permissions [status|mode <auto|default|plan>|allow <tool> <pattern>|deny <tool> <pattern>|remove <tool> <pattern>|LLM <query>][/dim]')
            self.renderer.render_text('\n'.join(lines))
            return True
        if sub == 'mode':
            if len(parts) < 3:
                self.renderer.render_text('Usage: /permissions mode <auto|default|plan>')
                return True
            try:
                self.permission_enforcer.mode = PermissionMode(parts[2].lower())
                self.settings.save_projact_config('permission_mode', parts[2].lower())
                self.renderer.render_text(f'[green]Permission mode set to:[/green] [cyan]{parts[2].lower()}[/cyan]')
            except ValueError:
                self.renderer.render_text(f'[yellow]Invalid mode: {parts[2]}. Use: auto, default, plan[/yellow]')
            return True
        if sub in ('allow', 'deny'):
            if len(parts) < 4:
                self.renderer.render_text(f'Usage: /permissions {sub} <tool> <pattern>')
                return True
            self.permission_enforcer.add_rule(parts[2], parts[3], sub)
            self._save_permission_rules()
            action_color = '[green]' if sub == 'allow' else '[red]'
            self.renderer.render_text(f'{action_color}Rule added:[/] {sub} tool={parts[2]} pattern={parts[3]}')
            return True
        if sub == 'remove':
            if len(parts) < 4:
                self.renderer.render_text('Usage: /permissions remove <tool> <pattern>')
                return True
            self.permission_enforcer.remove_rule(parts[2], parts[3])
            self._save_permission_rules()
            self.renderer.render_text(f'[green]Rule removed:[/green] tool={parts[2]} pattern={parts[3]}')
            return True
        self.renderer.render_text('Usage: /permissions [status|mode <auto|default|plan>|allow <tool> <pattern>|deny <tool> <pattern>|remove <tool> <pattern>|LLM <query>]')
        return True

    def _handle_mcp(self):
        count = self.mcp_manager.server_count
        if count == 0:
            self.renderer.render_text('[dim]No MCP servers configured. Add servers under `mcp.servers` in config.yaml[/dim]')
            return
        self.renderer.render_text('[bold]MCP Servers ({} connected):[/bold]'.format(count))
        mcp_cfg = self.settings.get('mcp', {})
        for srv in mcp_cfg.get('servers', []):
            name = srv.get('name', '?')
            cmd = srv.get('command', '?')
            connected = '[green]connected[/green]' if name in self.mcp_manager._clients else '[red]failed[/red]'
            self.renderer.render_text('  [cyan]{}[/cyan] — {} — {}'.format(name, cmd, connected))
        self.renderer.render_text('\n[dim]MCP tools are prefixed with `mcp__<server>__` . Use /tools to list all tools.[/dim]')

    def _handle_config(self):
        editor = ConfigEditor(self.settings.to_dict())
        new_config = editor.edit()
        if new_config is None:
            self.renderer.render_text('[dim]Config editing cancelled.[/dim]')
            return
        paths = get_config_paths()
        cfg_file = paths.get('projact_config_file')
        if not cfg_file:
            self.renderer.render_error('Config file path not found.')
            return
        save_config(new_config, cfg_file)
        self.settings.reload()
        self.llm = LLMClient(self.settings)
        self.agent.llm = self.llm
        self.agent.tracker.model = self.settings.model
        timeout = self.settings.get('bash_timeout_seconds', 120)
        from tools.bash import BashTool
        self.tools.register_tool(BashTool(timeout=timeout, workdir=str(self.context.working_dir)))
        self.renderer.render_text('[green]Configuration saved and reloaded.[/green]')

    def _load_live_tools(self):
        import json
        if not self._live_tools_file.exists():
            return
        try:
            data = json.loads(self._live_tools_file.read_text(encoding='utf-8'))
        except Exception:
            return
        loaded = 0
        for name, entry in data.items():
            try:
                tool = SoftwareCLITool(entry['name'], entry['spec'], exe_path=entry.get('exe_path'))
                self.tools.register_tool(tool)
                loaded += 1
            except Exception:
                pass
        if loaded:
            self.renderer.render_text(f'[dim]Loaded {loaded} live CLI tool(s): {", ".join(data.keys())}[/dim]\n')

    def _save_live_tools(self, tools_data: dict):
        import json
        existing = {}
        if self._live_tools_file.exists():
            try:
                existing = json.loads(self._live_tools_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        existing.update(tools_data)
        self._live_tools_file.parent.mkdir(parents=True, exist_ok=True)
        self._live_tools_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')

    def _handle_buildcli(self, parts: list[str]):
        import os
        import shutil
        import subprocess

        # Parse live parameter
        live = False
        args = parts[1:]
        if args and args[0].lower() == 'live':
            live = True
            args = args[1:]

        if len(args) < 1:
            self.renderer.render_text('Usage: /buildCLI [live] <software_name_or_path>\n\nExample: /buildCLI blender\nExample: /buildCLI live ffmpeg\nExample: /buildCLI live /usr/local/bin/my-tool')
            return

        raw = args[0]
        exe_path = Path(raw)
        if exe_path.is_absolute() or '/' in raw or '\\' in raw:
            resolved = exe_path.resolve()
            if not resolved.is_file() or not os.access(str(resolved), os.X_OK):
                self.renderer.render_error(f'"{raw}" is not a valid executable file.')
                return
            exe = str(resolved)
            name = resolved.stem
        else:
            name = raw
            exe = shutil.which(name)
            if not exe:
                self.renderer.render_error(f'Software "{name}" not found on PATH. Try using an absolute path instead.\n\nExample: /buildCLI /path/to/{name}')
                return

        self.renderer.render_text(f'[dim]Analyzing {name} (at {exe}) ...[/dim]')
        help_text = ''
        for flag in ['--help', '-h', 'help', '--version']:
            try:
                proc = subprocess.run([exe, flag], capture_output=True, text=True, timeout=10, env={**os.environ, 'PAGER': 'cat'})
                if proc.returncode == 0 and proc.stdout.strip():
                    help_text = proc.stdout
                    break
                if proc.stderr.strip():
                    help_text = proc.stderr
                    break
            except Exception:
                continue

        if not help_text:
            help_text = f'No help output available for {name}. The software exists at {exe}. Wrap as a generic CLI tool.'

        prompt = (
            f'Analyze the following CLI help output for "{name}" and produce a comprehensive usage guide '
            f'that an AI agent can use to operate this software via CLI commands.\n\n'
            f'HELP OUTPUT:\n{help_text[:4000]}\n\n'
            f'Return ONLY the usage guide in this exact format (no introduction, no markdown headers, just the guide):\n'
            f'- First line: a one-sentence summary of what {name} does\n'
            f'- Then: ## Common Commands\n'
            f'- Then list 5-15 most important commands with brief descriptions\n'
            f'- Then: ## Usage Notes\n'
            f'- Then 2-4 tips about using {name} effectively (important flags, output formats, pitfalls)\n'
            f'Keep it concise. The agent will read this as a tool description.'
        )

        try:
            response = self.llm.complete(
                messages=[{'role': 'user', 'content': prompt}],
                model=self.settings.model,
            )
            spec = response.content.strip()
        except Exception as e:
            spec = f'{name} CLI tool. Executes {name} commands. Key commands from help:\n{help_text[:800]}'

        tool = SoftwareCLITool(name, spec, exe_path=exe)
        self.tools.register_tool(tool)

        if live:
            self._save_live_tools({name: {'name': name, 'spec': spec, 'exe_path': exe}})

        self.renderer.render_text(f'[bold green]Built CLI for {name}[/bold green] — registered as tool [cyan]{tool.name}[/cyan]\n')
        self.renderer.render_text(spec)
        if live:
            self.renderer.render_text(f'\n[dim]Tool "{tool.name}" is now [bold]permanently[/bold] available across all sessions. Use /tools to see all registered tools.[/dim]')
        else:
            self.renderer.render_text(f'\n[dim]Tool "{tool.name}" is now available to the agent in this session. Use /tools to see all registered tools.[/dim]')

    def _remote_start(self, nocode: bool=False):
        if self.remote.is_running:
            self.renderer.render_text('[yellow]Remote control is already running.[/yellow]')
            self._remote_status()
            return
        result = self.remote.start(nocode=nocode)
        if result['ok']:
            if nocode:
                if result.get('paired'):
                    self.renderer.render_text(f'[bold green]Remote control started! (Feishu Bot — No-code)[/bold green]\n\n  Provider:   [bold cyan]Feishu[/bold cyan]\n  Mode:       [bold cyan]nocode[/bold cyan] (existing binding)\n\n  {result.get('status_note', '')}\n')
                else:
                    self.renderer.render_text(f'[bold green]Remote control started! (Feishu Bot — No-code)[/bold green]\n\n  Provider:   [bold cyan]Feishu[/bold cyan]\n  Mode:       [bold cyan]nocode[/bold cyan] (auto-bind)\n\n  [bold]How to connect:[/bold]\n    Open [bold]Feishu[/bold] on your phone, find your bot, and send any message.\n    The first sender will be automatically bound.\n\n  {result.get('status_note', '')}\n')
            else:
                paired_note = ''
                if result.get('paired'):
                    paired_note = '\n  [green](Already paired — no new pairing needed)[/green]'
                self.renderer.render_text(f'[bold green]Remote control started! (Feishu Bot)[/bold green]\n\n  Provider:  [bold cyan]Feishu[/bold cyan]\n  Pairing:   [bold yellow]{result['pairing_code']}[/bold yellow]{paired_note}\n\n  [bold]How to connect:[/bold]\n    1. Open [bold]Feishu[/bold] on your phone\n    2. Search for your bot and send it the pairing code above\n    3. Once paired, send any message to chat with TUDOU_agent\n\n  {result.get('status_note', '')}\n\n[dim]Pairing code expires in 5 minutes.[/dim]\n')
        else:
            self.renderer.render_error(f'Failed to start: {result.get('error')}')

    def _remote_stop(self):
        result = self.remote.stop()
        if result['ok']:
            self.renderer.render_text('[green]Remote control stopped.[/green]')
        else:
            self.renderer.render_text(f'[yellow]{result.get('error')}[/yellow]')

    def _remote_unpair(self):
        result = self.remote.unpair()
        if result['ok']:
            self.renderer.render_text('[green]Binding cleared. Use /remote start to pair a new device.[/green]')
        else:
            self.renderer.render_text(f'[yellow]{result.get('error')}[/yellow]')

    def _handle_plan_approval(self) -> bool:
        plan_file = self._plan_state.get('plan_file')
        if not plan_file or not plan_file.exists():
            self.renderer.render_text('[yellow]No plan file found.[/yellow]')
            return False
        plan_content = plan_file.read_text(encoding='utf-8', errors='replace')
        if not plan_content.strip():
            self.renderer.render_text('[yellow]Plan file is empty.[/yellow]')
            return False
        display = plan_content
        if len(display) > 6000:
            display = display[:6000] + f'\n\n... (truncated {len(plan_content) - 6000} chars)'
        self.renderer.render_text(f'[bold]Plan Review[/bold] — [dim]{plan_file.name}[/dim]\n\n{display}\n')
        approved = self.renderer.prompt_choice(question='Approve this plan?', options=['Yes', 'No'])
        if approved == 0:
            self._plan_state['active'] = False
            self._plan_state['plan_file'] = None
        else:
            self.renderer.render_text('[yellow]Plan rejected. Agent will revise.[/yellow]')
        return approved

    def _remote_status(self):
        s = self.remote.status()
        if not s['running']:
            self.renderer.render_text('[dim]Remote control is not running. Use /remote start to enable.[/dim]')
            return
        bound = '[green]yes[/green]' if s.get('bound') else '[yellow]no[/yellow]'
        ws = '[green]connected[/green]' if s.get('ws_connected') else '[yellow]connecting...[/yellow]'
        pairing = s.get('pairing_code') if s.get('pairing_active') else '[dim]expired[/dim]'
        self.renderer.render_text(f'Remote Control Status (Feishu Bot):\n  Running:    [green]yes[/green]\n  WebSocket:  {ws}\n  Bound:      {bound}\n  Pairing:    {pairing}\n')

    def _process_input(self, user_input: str):
        spinner = TUDOU_spinner('The agent is thinking for your questions...', style='dots')

        def _maybe_show_thinking():
            self._start_panel_animation()
            if not self._panel_running:
                spinner.start()

        _maybe_show_thinking()
        write_old_content: str | None = None
        stream_started = [False]
        TOOL_HINTS = {'Read': 'The agent is reading a file for you...', 'Write': 'The agent is writing a file for you...', 'Edit': 'The agent is editing a file for you...', 'Bash': 'The agent is running a command for you...', 'Glob': 'The agent is searching for files for you...', 'Grep': 'The agent is searching code for you...', 'WebSearch': 'The agent is searching the web for you...', 'WebFetch': 'The agent is fetching a URL for you...'}

        streamed_text = ['']

        def on_stream_token(token: str):
            if not stream_started[0]:
                spinner.stop()
                self._stop_panel_animation()
                stream_started[0] = True
                self.renderer.start_live_markdown()
            streamed_text[0] += token
            self.renderer.update_live_markdown(streamed_text[0])

        def on_tool_output(line: str):
            self.renderer.render_text(f'  [dim]│[/dim] {line}')

        def on_pre_tool(name, arguments):
            if stream_started[0]:
                self.renderer.stop_live_markdown()
            stream_started[0] = False
            spinner.stop()
            self._stop_panel_animation()
            if not self._quiet_ui:
                hint = TOOL_HINTS.get(name, f'Running {name}...')
                self.renderer.render_pre_tool(hint, name, arguments)

        def on_tool_call(name, arguments, result):
            nonlocal write_old_content
            if name in ('Write', 'Edit'):
                fp = arguments.get('file_path', '')
                plan_f = self._plan_state.get('plan_file')
                if not plan_f or str(fp) != str(plan_f):
                    if not self._code_mode:
                        self._code_mode = True
                        self.agent.code_mode = True
            self.renderer.render_tool_call(name, arguments)
            if name == 'Write' and 'content' in arguments:
                lang = _guess_lang(arguments.get('file_path', ''))
                new_content = arguments['content']
                if write_old_content is not None and write_old_content != new_content:
                    self.renderer.render_unified_diff(write_old_content, new_content, lang)
                else:
                    self.renderer.render_code_block(new_content, lang)
                write_old_content = None
            elif name == 'Edit' and 'new_string' in arguments:
                lang = _guess_lang(arguments.get('file_path', ''))
                old = arguments.get('old_string', '')
                new = arguments.get('new_string', '')
                self.renderer.render_unified_diff(old, new, lang)
            self.renderer.render_tool_result(name, arguments, result)
            _maybe_show_thinking()

        def on_approval(name, arguments):
            nonlocal write_old_content
            spinner.stop()
            self._stop_panel_animation()
            if name == 'ExitPlanMode':
                approved = self._handle_plan_approval()
                if not approved:
                    _maybe_show_thinking()
                return approved
            # Auto-approve if set
            if self._auto_approve:
                return True
            # Capture old file content for Write diff
            if name == 'Write' and 'file_path' in arguments:
                write_old_content = _read_file_if_exists(arguments['file_path'])
            perm_allowed, perm_reason = self.permission_enforcer.may_execute(name, arguments)
            if perm_allowed and not perm_reason.startswith('default'):
                _maybe_show_thinking()
                return True
            if not perm_allowed and 'Denied' in perm_reason:
                self.renderer.render_error(f'Blocked: {perm_reason}')
                _maybe_show_thinking()
                return False
            # Render approval block with code/command preview
            question = self.renderer.render_approval_block(name, arguments)
            choice = self.renderer.prompt_choice(
                question=question,
                options=['Yes', 'Yes, allow all edits during this session (shift+tab)', 'No'],
            )
            if choice == 1:
                self._auto_approve = True
                return True
            if choice == 0:
                return True
            _maybe_show_thinking()
            return False
        try:
            system_extra = self.skills.get_active_prompt()
            response = self.agent.run_conversation(user_input, system_extra=system_extra, on_tool_call=on_tool_call, on_approval=on_approval, on_pre_tool=on_pre_tool, on_stream_token=on_stream_token, on_tool_output=on_tool_output)
        except KeyboardInterrupt:
            if stream_started[0]:
                self.renderer.stop_live_markdown()
            spinner.stop()
            self._stop_panel_animation()
            self._code_mode = False
            self.agent.code_mode = False
            self.renderer.render_text('[dim]Cancelled.[/dim]')
            return
        except Exception as e:
            if stream_started[0]:
                self.renderer.stop_live_markdown()
            spinner.stop()
            self._stop_panel_animation()
            self._code_mode = False
            self.agent.code_mode = False
            self.renderer.render_error(str(e))
            return
        if stream_started[0]:
            self.renderer.stop_live_markdown()
        else:
            spinner.stop()
        self._stop_panel_animation()
        self._code_mode = False
        self.agent.code_mode = False
        if not self._conv_created:
            self._conv_created = True
            self.session_store.create_conversation(self._conv_id, model=self.settings.model)
        self.session_store.save_message(self._conv_id, 'user', user_input)
        if response.final_message:
            self.session_store.save_message(self._conv_id, 'assistant', response.final_message)
            if not stream_started[0]:
                self.renderer.render_text(response.final_message)
            if not self._title_generated:
                self._title_generated = True
                self._generate_title()
        self._save_to_history_md(user_input, response)
        if not self._panel_rendered:
            self._render_task_panel()
        if response.tool_stats and not self._quiet_ui:
            stats = ', '.join((f'{k}: {v}' for k, v in response.tool_stats.items()))
            tok = response.token_usage
            self.renderer.render_text(f'[dim](tools: {stats} | tokens: {tok.input}+{tok.output} | {response.duration_ms}ms)[/dim]')

    def _generate_title(self):
        try:
            msgs = self.session_store.load_messages(self._conv_id)
            user_msgs = [m for m in msgs if m['role'] == 'user']
            asst_msgs = [m for m in msgs if m['role'] == 'assistant']
            if not user_msgs:
                return
            user_text = user_msgs[0]['content'][:300]
            asst_text = asst_msgs[0]['content'][:300] if asst_msgs else ''
            prompt = f'Summarize this conversation in a brief title (5-10 words, in the same language as the conversation):\n\nUser: {user_text}\n\nAssistant: {asst_text}'
            resp = self.llm.complete(
                messages=[{'role': 'user', 'content': prompt}],
                model=self.settings.model,
            )
            title = resp.content.strip().strip('"\'').strip()
            if title:
                self.session_store.update_summary(self._conv_id, title)
        except Exception:
            pass

    def _show_tudou_info(self):
        info_path = PROJACT_DIR / 'TUDOU_information.md'
        if not info_path.exists():
            self.renderer.render_error('TUDOU_information.md not found.')
            return
        content = info_path.read_text(encoding='utf-8', errors='replace')
        self.renderer.render_text(content)

    def _show_tasks(self):
        tasks = self.task_manager.list_tasks()
        if not tasks:
            self.renderer.render_text('[dim]No tasks yet. Agent can create tasks with TaskCreate tool during complex work.[/dim]')
            return
        counts = self.task_manager.count()
        icons = {'pending': '[dim]○[/dim]', 'in_progress': '[bold cyan]●[/bold cyan]', 'completed': '[green]✓[/green]', 'deleted': '[dim]✗[/dim]'}
        lines = [f'[bold]Tasks ({counts["total"]}):[/bold]  {icons["in_progress"]} {counts["in_progress"]} in-progress  {icons["pending"]} {counts["pending"]} pending  {icons["completed"]} {counts["completed"]} done']
        for t in tasks:
            icon = icons.get(t.status, '?')
            lines.append(f'  [{t.id}] {icon} {t.subject}')
            if t.blocked_by:
                lines.append(f'      [dim]⏳ blocked by: {", ".join(t.blocked_by)}[/dim]')
        self.renderer.render_text('\n'.join(lines))

    @staticmethod
    def _wave_chars(text: str, t: float, extra_sgr: str='') -> str:
        """ANSI wave gradient per char; extra_sgr prepended (e.g. '9'=strike, '2'=dim, '1'=bold)."""
        parts = []
        if extra_sgr:
            parts.append(f'\x1b[{extra_sgr}m')
        for i, ch in enumerate(text):
            if ch == ' ':
                parts.append(ch)
                continue
            phase = i * 0.45 + t * 2.8
            ratio = (math.sin(phase) + 1.0) / 2.0
            g = int(255 * ratio)
            b = int(255 * (1.0 - ratio) + 255 * ratio)
            parts.append(f'\x1b[38;2;0;{g};{b}m{ch}')
        parts.append('\x1b[0m')
        return ''.join(parts)

    def _build_panel_lines(self, t: float) -> list[str]:
        """Build wave-colored panel lines. Returns empty list if no tasks."""
        tasks = self.task_manager.list_tasks()
        active = [t for t in tasks if t.status in ('pending', 'in_progress')]
        if not tasks or not active:
            return []

        icons = {'pending': '○', 'in_progress': '●', 'completed': '✓'}
        visible = [t for t in tasks if t.status != 'deleted']
        sgr_map = {'completed': '9', 'pending': '2', 'in_progress': '1'}

        # Measure
        title = f'  ▸ Task progress ({len(active)} active) (Agent is doing something for your question)  '
        raw_lines = [title]
        for i, task in enumerate(visible):
            is_last = (i == len(visible) - 1)
            prefix = '└─' if is_last else '├─'
            icon = icons.get(task.status, '?')
            raw_lines.append(f'  {prefix} [{task.id}] {icon} {task.subject}  ')
        inner_w = max(len(l) for l in raw_lines)

        out = [self._wave_chars(f'╭{"─" * inner_w}╮', t)]
        padded_title = f'│{title}{" " * (inner_w - len(title))}│'
        out.append(self._wave_chars(padded_title, t))

        for i, task in enumerate(visible):
            is_last = (i == len(visible) - 1)
            prefix = '└─' if is_last else '├─'
            icon = icons.get(task.status, '?')
            sgr = sgr_map.get(task.status, '')
            head = f'│  {prefix} [{task.id}] {icon} '
            subj = self._wave_chars(task.subject, t, extra_sgr=sgr)
            tail_len = inner_w - len(f'  {prefix} [{task.id}] {icon} {task.subject}  ')
            tail = f'{" " * tail_len}│'
            out.append(self._wave_chars(head, t) + subj + self._wave_chars(tail, t))

        out.append(self._wave_chars(f'╰{"─" * inner_w}╯', t))
        return out

    def _render_task_panel(self):
        """One-shot panel render (for end-of-response fallback)."""
        lines = self._build_panel_lines(time.time())
        if not lines:
            return
        sys.stdout.write('\n'.join(lines) + '\n')
        sys.stdout.flush()
        self._panel_rendered = True

    # ── animated panel (spinner-style: count lines, \x1b[{n}A + \x1b[J, reprint) ──

    def _clear_panel_area(self):
        """Move up N lines and clear to end of screen."""
        if self._last_panel_lines > 0:
            sys.stdout.write(f'\x1b[{self._last_panel_lines}A')
            sys.stdout.write('\x1b[J')
            sys.stdout.flush()
            self._last_panel_lines = 0

    def _panel_animate(self):
        """Thread: render panel every 100ms, overwriting previous frame in-place."""
        while self._panel_running:
            lines = self._build_panel_lines(time.time())
            if not lines:
                self._clear_panel_area()
                self._panel_running = False
                return

            if self._last_panel_lines > 0:
                sys.stdout.write(f'\x1b[{self._last_panel_lines}A')
            sys.stdout.write('\x1b[J')
            sys.stdout.write('\n'.join(lines) + '\n')
            sys.stdout.flush()
            self._last_panel_lines = len(lines)
            time.sleep(0.1)

    def _start_panel_animation(self):
        self._stop_panel_animation()
        tasks = self.task_manager.list_tasks()
        active = [t for t in tasks if t.status in ('pending', 'in_progress')]
        if not active:
            return
        self._panel_running = True
        self._panel_thread = threading.Thread(target=self._panel_animate, daemon=True)
        self._panel_thread.start()

    def _stop_panel_animation(self):
        self._panel_running = False
        if self._panel_thread:
            self._panel_thread.join(timeout=0.5)
            self._panel_thread = None
        self._clear_panel_area()

    def _show_context(self):
        tracker = self.agent.tracker
        messages = self.context._history
        turn_count = len(messages) // 2
        est_tokens = tracker.estimate_messages(self.context.build_messages(user_input='', tools=self.tools.get_schemas() if self.tools.tool_count() > 0 else None, system_extra=self.skills.get_active_prompt()))
        self.renderer.render_text(f'Context Status:\n  Model: {tracker.model}  |  Budget: {tracker.budget.max_tokens:,} tokens\n  Estimated: {est_tokens:,} tokens ({tracker.usage_ratio() * 100:.1f}%)  |  Remaining: {tracker.remaining():,}\n  Messages in history: {len(messages)}  |  Turns: {turn_count}\n  Cumulative input: {tracker.cumulative_input:,}  |  Cumulative output: {tracker.cumulative_output:,}\n  Compressions: {tracker.compression_count}\n  Tool result max chars: {tracker.max_tool_result_chars:,}')

    @staticmethod
    def _mask(value: str) -> str:
        if len(value) <= 8:
            return '*' * len(value)
        return value[:4] + '*' * (len(value) - 8) + value[-4:]

    def _show_help(self):
        active_skill = f' ({self.skills.active_skill.name})' if self.skills.active_skill else ''
        self.renderer.render_text(f'## TUDOU Agent Commands\n\n| Command | Description |\n|---------|-------------|\n| `/tudou` | Show TUDOU_agent information |\n| `/help` | Show this help |\n| `/exit`, `/quit` | Exit the agent |\n| `/clear` | Clear conversation history |\n| `/model [name]` | Show or set the model |\n| `/tools` | List available tools |\n| `/context` | Show context usage and budget status |\n| `/memory [list\\|show\\|delete\\|LLM]` | Manage persistent memories |\n| `/history [list\\|recent\\|show\\|LLM]` | View saved conversation history |\n| `/permissions [status\\|mode\\|allow\\|deny\\|remove\\|LLM]` | Manage tool permissions |\n| `/config` | Open full-screen interactive config editor |\n| `/mcp` | Show MCP server status |\n| `/skills` | List loaded skills (150 built-in) |\n| `/activate <name>` | Activate a skill for this session{active_skill} |\n| `/deactivate` | Deactivate the current skill |\n| `/importdangerskills <name>` | Import a skill from dangerskills/ |\n| `/removeskills <name>` | Remove a skill to dangerskills/ |\n| `/setMAPI <key>` | Set OpenAI-compatible API key |\n| `/setMURL <url>` | Set OpenAI-compatible base URL |\n| `/setFID <id>` | Set Feishu App ID |\n| `/setFAS <secret>` | Set Feishu App Secret |\n| `/rootmodel` | Toggle root mode: auto-execute without asking permission |\n| `/betterui` | Toggle better UI: reduce noise, hide non-essential output |\n| `/subagent` | Toggle sub-agent delegation: allow Agent to spawn sub-agents for parallel tasks |\n| `/remote start [nocode]` | Start remote control (Feishu Bot). Add `nocode` to skip pairing code |\n| `/remote stop` | Stop remote control |\n| `/remote status` | Show remote control status |\n| `/buildCLI [live] <name or path>` | Wrap a CLI program as an agent-callable tool. Add `live` to persist across sessions |\n\nAdd `LLM` after any command (e.g. `/memory LLM ...`) to let the AI handle it with full tool access.\n\nType any message to chat with the agent.\n')

def TUDOU_main():
    cli = TUDOU_CLI()
    cli.run()
