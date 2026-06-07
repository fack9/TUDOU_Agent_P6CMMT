import shutil
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, Dimension, FloatContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.styles import Style
SLASH_COMMANDS = ['/help', '/exit', '/quit', '/clear', '/model', '/tools', '/tasks', '/tudou', '/context', '/skills', '/activate', '/deactivate', '/importdangerskills', '/removeskills', '/config', '/history', '/memory', '/permissions', '/permission', '/mcp', '/setmapi', '/setmurl', '/setfid', '/setfas', '/thinking', '/sandbox', '/rootmodel', '/betterui', '/worktree', '/subagent', '/remote', '/buildCLI', '/resume', '/export']

SUBCOMMANDS = {
    '/history':    ['list', 'recent', 'show', 'LLM'],
    '/memory':     ['list', 'show', 'delete', 'LLM'],
    '/permissions': ['status', 'mode', 'allow', 'deny', 'remove', 'LLM'],
    '/permission': ['status', 'mode', 'allow', 'deny', 'remove', 'LLM'],
    '/remote':     ['start', 'stop', 'status', 'unpair'],
    '/remote start': ['nocode'],
    '/buildCLI':    ['live'],
    '/sandbox':    ['on', 'off', 'status'],
    '/worktree':   ['create', 'enter', 'exit', 'list'],
    '/skills':     ['list', 'install', 'search'],
    '/resume':     ['list', 'list all', 'clear', 'delete', 'import'],
    '/export':     [],
    '/resume':      ['list', 'clear', 'delete', 'import'],
    '/resume list': ['all'],
}

class SlashCompleter(Completer):

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith('/'):
            parts = text.split()
            trailing_space = text.endswith(' ')

            if trailing_space:
                base_cmd = ' '.join(parts)
                subs = SUBCOMMANDS.get(base_cmd, [])
                for sub in subs:
                    yield Completion(sub, start_position=0)
                return
            elif len(parts) == 1:
                cmd = parts[0]
                if cmd in SUBCOMMANDS:
                    for sub in SUBCOMMANDS[cmd]:
                        yield Completion(f' {sub}', start_position=0, display=sub)
                for c in SLASH_COMMANDS:
                    if c.startswith(text):
                        yield Completion(c, start_position=-len(text))
                return
            else:
                base_cmd = ' '.join(parts[:-1])
                current_word = parts[-1]
                subs = SUBCOMMANDS.get(base_cmd, [])
                for sub in subs:
                    if sub.lower().startswith(current_word.lower()):
                        yield Completion(sub, start_position=-len(current_word))
                return

        if ' ' in text or text.startswith('.'):
            try:
                word = text.split()[-1] if ' ' in text else text
                parent = Path(word).parent if '/' in word else Path('.')
                prefix = Path(word).name
                if parent.exists():
                    for p in parent.iterdir():
                        name = p.name
                        if name.startswith(prefix):
                            display = name + ('/' if p.is_dir() else '')
                            yield Completion(str(p), start_position=-len(prefix), display=display)
            except Exception:
                pass
PROMPT_STYLE = Style.from_dict({'prompt': 'bold ansicyan', 'shell_prompt': 'bold yellow', 'separator': 'fg:ansibrightblack', 'planmode_sep': 'fg:#3355cc bold', 'codemode_sep': 'fg:#ccaa00 bold'})

def _make_sep() -> str:
    return '─' * shutil.get_terminal_size().columns

def _make_planmode_top_sep() -> str:
    cols = shutil.get_terminal_size().columns
    label = ' TUDOU_planmode '
    side_len = (cols - len(label)) // 2
    return '─' * side_len + label + '─' * (cols - side_len - len(label))

def _make_codemode_top_sep() -> str:
    cols = shutil.get_terminal_size().columns
    label = ' TUDOU_codemode '
    side_len = (cols - len(label)) // 2
    return '─' * side_len + label + '─' * (cols - side_len - len(label))

class _SepPromptSession(PromptSession):

    def __init__(self, *args, get_plan_state=None, get_code_mode=None, get_shell_mode=None, **kwargs):
        self._get_plan_state = get_plan_state
        self._get_code_mode = get_code_mode
        self._get_shell_mode = get_shell_mode
        super().__init__(*args, **kwargs)

    def _create_application(self, *args, **kwargs):
        app = super()._create_application(*args, **kwargs)
        fc = None
        buf_win = None

        def _search(container):
            nonlocal fc, buf_win
            if isinstance(container, FloatContainer):
                fc = container
            if isinstance(container, Window):
                if isinstance(container.content, BufferControl):
                    buf_win = container
            try:
                for child in container.get_children():
                    _search(child)
            except (AttributeError, TypeError):
                pass
        _search(app.layout.container)
        if buf_win is None:
            return app
        if isinstance(buf_win.content, BufferControl):
            self._buf = buf_win.content.buffer
        else:
            self._buf = None

        _slash_guard = [False]
        slash_kb = KeyBindings()

        @slash_kb.add('/')
        def _on_slash(event):
            if _slash_guard[0]:
                return
            _slash_guard[0] = True
            try:
                buf = event.app.current_buffer
                buf.insert_text('/')
                if not buf.complete_state:
                    buf.start_completion(select_first=False)
            finally:
                _slash_guard[0] = False

        @slash_kb.add(' ')
        def _on_space(event):
            buf = event.app.current_buffer
            text = buf.text
            if text.startswith('/'):
                parts = text.split()
                base_cmd = ' '.join(parts)
                if base_cmd in SUBCOMMANDS:
                    buf.insert_text(' ')
                    if not buf.complete_state:
                        buf.start_completion(select_first=False)
                    return
            buf.insert_text(' ')

        app.key_bindings = merge_key_bindings([slash_kb, app.key_bindings])
        app.full_screen = False
        try:
            object.__setattr__(buf_win, '_Window__dont_extend_height', True)
        except AttributeError:
            pass

        def get_top_sep():
            if self._get_shell_mode and self._get_shell_mode():
                return [('class:shell_prompt', _make_sep())]
            if self._get_code_mode and self._get_code_mode():
                return [('class:codemode_sep', _make_codemode_top_sep())]
            if self._get_plan_state and self._get_plan_state():
                return [('class:planmode_sep', _make_planmode_top_sep())]
            return [('class:separator', _make_sep())]

        def get_bottom_sep():
            if self._get_shell_mode and self._get_shell_mode():
                return [('class:shell_prompt', _make_sep())]
            if self._get_code_mode and self._get_code_mode():
                return [('class:codemode_sep', _make_sep())]
            if self._get_plan_state and self._get_plan_state():
                return [('class:planmode_sep', _make_sep())]
            return [('class:separator', _make_sep())]

        def get_hint_line():
            if self._get_shell_mode and self._get_shell_mode():
                return [('class:shell_prompt', '  /downshell  —  exit shell mode,  type any command to execute')]
            cmds = '/help  /exit  /clear  /rootmodel  /betterui  /tools  /model  /skills  /mcp  /context  /remote  /tudou'
            return [('class:separator', f'  {cmds}')]

        top_win = Window(height=1, dont_extend_height=True, content=FormattedTextControl(text=get_top_sep))
        bottom_sep = Window(height=1, dont_extend_height=True, content=FormattedTextControl(text=get_bottom_sep))
        hint_win = Window(height=1, dont_extend_height=True, content=FormattedTextControl(text=get_hint_line))
        spacer = Window(height=Dimension(weight=10 ** 6), content=FormattedTextControl(text=''))

        def _strip_inner(container, depth=0):
            if isinstance(container, Window):
                h = container.height
                if callable(h):
                    container.height = Dimension(preferred=1)
                elif isinstance(h, Dimension) and h.weight > 0:
                    container.height = Dimension(preferred=1)
                try:
                    object.__setattr__(container, '_Window__dont_extend_height', True)
                except AttributeError:
                    pass
                return
            try:
                for child in container.get_children():
                    _strip_inner(child, depth + 1)
            except (AttributeError, TypeError):
                pass
            if hasattr(container, 'content') and not isinstance(container, Window):
                _strip_inner(container.content, depth + 1)

        if fc is not None:
            inner = fc.content
            _strip_inner(inner)
            fc.content = HSplit([spacer, top_win, inner, bottom_sep, hint_win])
        else:
            prompt_win = Window(width=2, dont_extend_width=True, content=FormattedTextControl(text=[('class:prompt', '❯ ')]))
            input_row = VSplit([prompt_win, buf_win])
            app.layout.container = HSplit([spacer, top_win, input_row, bottom_sep, hint_win])
        return app

class InputHandler:

    def __init__(self, history_file: Path | None=None, get_plan_state=None, get_code_mode=None, get_shell_mode=None):
        history = None
        if history_file:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(history_file))
        self.session = _SepPromptSession(history=history, auto_suggest=AutoSuggestFromHistory(), completer=SlashCompleter(), style=PROMPT_STYLE, multiline=False, get_plan_state=get_plan_state, get_code_mode=get_code_mode, get_shell_mode=get_shell_mode)

    def get_input(self) -> str:
        session = self.session
        def _shell_prompt():
            if session._get_shell_mode and session._get_shell_mode():
                return [('class:shell_prompt', '❯ ')]
            return [('class:prompt', '❯ ')]
        try:
            return session.prompt(_shell_prompt, enable_history_search=True).strip()
        except (KeyboardInterrupt, EOFError):
            return ''

    @staticmethod
    def prompt_user_response(questions: list[dict]) -> str:
        """Collect user answers to plan-mode questions via terminal input."""
        answers = []
        for i, q in enumerate(questions):
            header = q.get('header', f'Q{i+1}')
            question = q.get('question', '')
            options = q.get('options', [])
            if options:
                labels = [opt.get('label', opt) if isinstance(opt, dict) else str(opt) for opt in options]
                prompt = f'  [{header}] Your choice (1-{len(labels)}): '
                try:
                    choice = input(prompt).strip()
                except (KeyboardInterrupt, EOFError):
                    choice = ''
                answers.append(f'[{header}] User chose: {choice}')
            else:
                try:
                    answer = input(f'  [{header}] {question}: ').strip()
                except (KeyboardInterrupt, EOFError):
                    answer = '(no answer)'
                answers.append(f'[{header}] {question} → {answer}')
        return '\n'.join(answers)
