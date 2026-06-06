import difflib
from io import StringIO
from pathlib import Path
from rich.console import Console as RichConsole
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from utils.constants import VERSION

class Renderer:

    _LANG_MAP = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
        '.html': 'html', '.css': 'css', '.scss': 'scss', '.json': 'json',
        '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.md': 'markdown',
        '.sh': 'bash', '.bash': 'bash', '.java': 'java', '.kt': 'kotlin',
        '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.rs': 'rust',
        '.go': 'go', '.sql': 'sql', '.xml': 'xml', '.rb': 'ruby', '.php': 'php',
        '.lua': 'lua', '.r': 'r', '.swift': 'swift', '.dockerfile': 'dockerfile',
        '.cfg': 'ini', '.ini': 'ini', '.gitignore': 'gitignore',
    }

    def __init__(self):
        self.console = Console()

    def welcome(self, version: str=VERSION):
        self.console.print()
        self.console.print(Panel(f'[bold cyan]TUDOU Agent v{version}[/bold cyan]\n[dim]CLI AI Agent — type /help for commands, /exit to quit[/dim]', border_style='cyan'))

    def render_text(self, text: str):
        self.console.print()
        try:
            md = Markdown(text)
            self.console.print(md)
        except Exception:
            self.console.print(text)
        self.console.print()

    _TOOL_LABELS = {
        'Write': 'Create file', 'Edit': 'Edit file', 'Read': 'Read file',
        'Bash': 'Run command', 'Grep': 'Search code', 'Glob': 'Search files',
        'WebSearch': 'Search web', 'WebFetch': 'Fetch URL',
        'TaskCreate': 'Create task', 'TaskUpdate': 'Update task', 'TaskList': 'List tasks',
    }

    def render_tool_call(self, name: str, arguments: dict):
        short_args = self._format_args(arguments)
        self.console.print()
        self.console.print(f'  [bold cyan]●[/bold cyan] [bold rgb(135,206,250)]{name}[/bold rgb(135,206,250)]({short_args})')

    def render_pre_tool(self, hint: str, name: str, arguments: dict):
        import shutil
        cols = shutil.get_terminal_size().columns
        sep = ('─' * (cols // 2))[:cols]
        self.console.print(f'[dim]{sep}[/dim]')
        detail = self._pre_tool_detail(name, arguments)
        if detail:
            self.console.print(f'  [yellow]→ {hint} [cyan]{detail}[/cyan][/yellow]')
        else:
            self.console.print(f'  [yellow]→ {hint}[/yellow]')

    def render_approval_block(self, name: str, arguments: dict):
        """Render the approval block with tool info and code/command preview."""
        import shutil
        cols = shutil.get_terminal_size().columns

        self.console.print(f'[dim]{"─" * cols}[/dim]')
        label = self._TOOL_LABELS.get(name, name)
        self.console.print(f' [bold rgb(135,206,250)]{label}[/bold rgb(135,206,250)]')

        # Detail line with prefix
        prefix_map = {
            'Bash': 'commands', 'Read': 'file', 'Write': 'file', 'Edit': 'file',
            'Grep': 'pattern', 'Glob': 'pattern',
            'WebSearch': 'query', 'WebFetch': 'url',
        }
        detail_text = ''
        if name in ('Read', 'Write', 'Edit'):
            detail_text = arguments.get('file_path', '')
        elif name == 'Bash':
            cmd = arguments.get('command', '')
            detail_text = cmd[:200] + ('...' if len(cmd) > 200 else '')
        elif name in ('Grep', 'Glob'):
            detail_text = arguments.get('pattern', '')
        elif name in ('WebSearch', 'WebFetch'):
            detail_text = arguments.get('query', '') or arguments.get('url', '')

        if detail_text:
            prefix = prefix_map.get(name, '')
            self.console.print()
            if prefix:
                self.console.print(f' [bold rgb(135,206,250)]{prefix}:[/bold rgb(135,206,250)] [rgb(135,206,250)]{detail_text}[/rgb(135,206,250)]')
            else:
                self.console.print(f' [rgb(135,206,250)]{detail_text}[/rgb(135,206,250)]')

        # Code preview for Write
        if name == 'Write' and 'content' in arguments:
            code = arguments['content']
            fp = arguments.get('file_path', '')
            lang = self._LANG_MAP.get(Path(fp).suffix.lower(), 'text')
            self.console.print(f'[dim]{"╌" * cols}[/dim]')
            ansi = self._render_ansi(Syntax(code, lang, theme='native', line_numbers=True))
            for line in ansi.rstrip('\n').split('\n'):
                print(f'  {line}')
            print()
            self.console.print(f'[dim]{"╌" * cols}[/dim]')

        # Diff preview for Edit
        elif name == 'Edit':
            old = arguments.get('old_string', '')
            new = arguments.get('new_string', '')
            if old or new:
                self.console.print(f'[dim]{"╌" * cols}[/dim]')
                self.render_unified_diff(old, new)
                self.console.print()
                self.console.print(f'[dim]{"╌" * cols}[/dim]')

        # Return question text for prompt_choice
        detail = self._pre_tool_detail(name, arguments)
        if detail:
            return f'Do you want to proceed with this:{detail}?'
        return 'Do you want to proceed?'

    @staticmethod
    def _pre_tool_detail(name: str, arguments: dict) -> str:
        if name == 'Bash':
            cmd = arguments.get('command', '')
            return cmd[:60] + ('...' if len(cmd) > 60 else '')
        if name in ('Read', 'Write', 'Edit'):
            fp = arguments.get('file_path', '')
            return str(Path(fp).name) if fp else ''
        if name in ('Grep',):
            pattern = arguments.get('pattern', '')
            return pattern[:40] if pattern else ''
        if name == 'Glob':
            pattern = arguments.get('pattern', '')
            return pattern[:40] if pattern else ''
        if name in ('WebSearch', 'WebFetch'):
            query = arguments.get('query', '') or arguments.get('url', '')
            return query[:50] + ('...' if len(query) > 50 else '')
        return ''

    def render_tool_result(self, name: str, arguments: dict, result):
        if result.success:
            output = result.output or ''
            if len(output) > 500:
                output = output[:500] + f'\n... [truncated {len(result.output) - 500} chars]'
            if output:
                self.console.print(f'  [cyan]✓[/cyan] [dim cyan]{output}[/dim cyan]')
            else:
                self.console.print(f'  [cyan]✓[/cyan]')
            self.console.print()
        else:
            error = result.error or 'Unknown error'
            self.console.print(f'  [red]✗[/red] [red]{error}[/red]')
            self.console.print()

    def render_error(self, error: str):
        self.console.print(f'\n[bold red]Error:[/bold red] {error}\n')

    @staticmethod
    def _render_ansi(renderable) -> str:
        buf = StringIO()
        tmp = RichConsole(file=buf, force_terminal=True, color_system='truecolor')
        tmp.print(renderable)
        return buf.getvalue()

    def render_code_block(self, code: str, language: str=''):
        print()
        lang = language or 'text'
        ansi = self._render_ansi(Syntax(code, lang, theme='native', line_numbers=True))
        for line in ansi.rstrip('\n').split('\n'):
            print(f'  {line}')
        print()

    def render_diff(self, old: str, new: str, language: str=''):
        print()
        if not old and (not new):
            return
        if old:
            a = self._render_ansi(Text('── Removed ──', style='bold red'))
            print(f'  {a.rstrip()}')
            for line in old.rstrip('\n').split('\n'):
                print(self._render_ansi(Text(f'  {line}', style='on red')).rstrip('\n'))
        if new:
            a = self._render_ansi(Text('── Added ──', style='bold green'))
            print(f'  {a.rstrip()}')
            for line in new.rstrip('\n').split('\n'):
                print(self._render_ansi(Text(f'  {line}', style='on green')).rstrip('\n'))
        print()

    def render_unified_diff(self, old: str, new: str, language: str=''):
        old_lines = old.split('\n')
        new_lines = new.split('\n')
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        blocks = list(matcher.get_grouped_opcodes(n=3))
        if not blocks:
            return
        print()
        print(f'  ── {len(blocks)} change hunk(s) ──')
        for block in blocks:
            for tag, i1, i2, j1, j2 in block:
                if tag == 'equal':
                    for i in range(i1, min(i2, i1 + 3)):
                        a = self._render_ansi(Text(f'  {old_lines[i]}', style='dim'))
                        print(a.rstrip('\n'))
                    if i2 - i1 > 6:
                        n = i2 - i1 - 6
                        print(f'  ... ({n} unchanged lines)')
                        for i in range(i2 - 3, i2):
                            a = self._render_ansi(Text(f'  {old_lines[i]}', style='dim'))
                            print(a.rstrip('\n'))
                    elif i2 - i1 > 3:
                        for i in range(i1 + 3, i2):
                            a = self._render_ansi(Text(f'  {old_lines[i]}', style='dim'))
                            print(a.rstrip('\n'))
                elif tag in ('replace', 'delete'):
                    for i in range(i1, i2):
                        a = self._render_ansi(Text(f'- {old_lines[i]}', style='on red'))
                        print(a.rstrip('\n'))
                if tag in ('replace', 'insert'):
                    for j in range(j1, j2):
                        a = self._render_ansi(Text(f'+ {new_lines[j]}', style='on green'))
                        print(a.rstrip('\n'))
            if block != blocks[-1]:
                print('  ···')
        print()

    def start_live_markdown(self):
        self._live = Live(Markdown(''), console=self.console, refresh_per_second=15, transient=False)
        self._live.start()

    def update_live_markdown(self, text: str):
        if hasattr(self, '_live') and self._live is not None:
            self._live.update(Markdown(text))

    def stop_live_markdown(self):
        if hasattr(self, '_live') and self._live is not None:
            self._live.stop()
            self._live = None

    def render_thinking(self, text: str):
        self.console.print(f'  [dim italic]{text}[/dim italic]')

    def prompt_choice(self, question: str='Do you want to proceed?', options: list[str] | None=None) -> int:
        """Show a choice prompt. Returns 0-based index, -1 on cancel."""
        if options is None:
            options = ['Yes', 'No']
        kb = KeyBindings()
        selected = [0]
        n = len(options)

        def _build_text():
            lines = [question, '']
            for i, opt in enumerate(options):
                if selected[0] == i:
                    lines.append(f'  ❯ {i + 1}. {opt}')
                else:
                    lines.append(f'    {i + 1}. {opt}')
            return '\n'.join(lines)
        control = FormattedTextControl(text=_build_text)
        window = Window(content=control)

        @kb.add('up')
        @kb.add('left')
        def _(event):
            selected[0] = (selected[0] - 1) % n
            event.app.invalidate()

        @kb.add('down')
        @kb.add('right')
        def _(event):
            selected[0] = (selected[0] + 1) % n
            event.app.invalidate()

        @kb.add('s-tab')
        def _(event):
            # shift+tab jumps to option 2 ("allow all")
            if n > 2:
                selected[0] = 1
                event.app.invalidate()

        for i in range(n):
            @kb.add(str(i + 1))
            def _(event, idx=i):
                selected[0] = idx
                event.app.invalidate()

        @kb.add('enter')
        def _(event):
            event.app.exit(result=selected[0])

        @kb.add('c-c')
        @kb.add('escape')
        def _(event):
            event.app.exit(result=-1)
        app = Application(layout=Layout(window), key_bindings=kb, full_screen=False, erase_when_done=False, style=Style.from_dict({}))
        try:
            return app.run()
        except (KeyboardInterrupt, EOFError):
            return -1

    def prompt(self, text: str='> ') -> str:
        return input(text)

    @staticmethod
    def _format_args(args: dict) -> str:
        if not args:
            return ''
        if 'command' in args:
            cmd = args['command']
            return f'command="{cmd}"'
        if 'file_path' in args:
            return f'file_path="{args['file_path']}"'
        if 'path' in args:
            return f'path="{args['path']}"'
        if 'pattern' in args:
            return f'pattern="{args['pattern']}"'
        if 'query' in args:
            return f'query="{args['query']}"'
        if 'url' in args:
            return f'url="{args['url']}"'
        items = list(args.items())
        if len(items) <= 2:
            return ', '.join((f'{k}="{v}"' for k, v in items))
        return ', '.join((f'{k}="{v}"' for k, v in items[:2])) + ', ...'
