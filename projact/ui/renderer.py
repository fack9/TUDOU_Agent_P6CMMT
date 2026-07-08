import difflib
import sys
from io import StringIO
from pathlib import Path
from rich.console import Console as RichConsole
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
try:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    _PT_AVAILABLE = True
except Exception:
    _PT_AVAILABLE = False
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
        try:
            md = Markdown(text)
            self.console.print(md)
        except Exception:
            self.console.print(text)

    def render_tool_output_line(self, tool_name: str, line: str, stream: str = 'stdout'):
        """Render a single streaming output line — no extra spacing."""
        label = f'[dim]{tool_name}[/dim] │ ' if tool_name else ''
        if stream == 'stderr':
            color = 'rgb(255,100,180)'  # light magenta
            self.console.print(f'  [dim]│[/dim] {label}[rgb(255,100,180)]{line}[/rgb(255,100,180)]')
        elif stream == 'explore-pre':
            sys.stdout.write(line + '\n')
            sys.stdout.flush()
        elif stream == 'explore-counter':
            if getattr(self, '_explore_counter_active', False):
                sys.stdout.write('[1A[2K')
            else:
                self._explore_counter_active = True
            sys.stdout.write(line + '\n')
            sys.stdout.flush()
        elif stream == 'explore-done':
            self._explore_counter_active = False
        else:
            self.console.print(f'  [dim]│[/dim] {label}[rgb(135,206,250)]{line}[/rgb(135,206,250)]')

    def render_explore_start(self, description: str):
        """Render the Explore header when exploration begins."""
        import shutil
        cols = shutil.get_terminal_size().columns
        sep = ('─' * (cols // 2))[:cols]
        self.console.print(f'[dim]{sep}[/dim]')
        esc = chr(27)
        sys.stdout.write(f'  {esc}[5m●{esc}[25m {esc}[1;37mExplore{esc}[0m({esc}[38;2;135;206;250m{description}{esc}[0m){esc}[K\n')
        sys.stdout.flush()

    def render_explore_summary(self, sub_tool_count: int, sub_tool_names: list[str]):
        """Render the Explore summary line with collapse/background hints."""
        tools_str = ', '.join(sub_tool_names[:3])
        if len(sub_tool_names) > 3:
            tools_str += f' +{len(sub_tool_names) - 3} more'
        self.console.print(f'     [dim white]… {sub_tool_count} tool uses[/dim white] [dim]({tools_str})[/dim]')
        self.console.print(f'     [dim]ctrl+o to expand  |  ctrl+b to run in background[/dim]')

    def render_agent_summary(self, tool_stats: dict, duration_ms: int):
        """Render the Agent sub-agent summary line."""
        if tool_stats:
            parts = [f'{k}×{v}' for k, v in sorted(tool_stats.items())]
            stats_str = '  '.join(parts[:4])
            if len(parts) > 4:
                stats_str += f'  +{len(parts) - 4} more'
        else:
            stats_str = 'no tools used'
        dur_s = duration_ms / 1000
        self.console.print(f'     [dim white]… sub-agent used[/dim white] [dim]{stats_str}[/dim] [dim white]({dur_s:.1f}s)[/dim white]')

    _TOOL_LABELS = {
        'Write': 'Create file', 'Edit': 'Edit file', 'Read': 'Read file',
        'Bash': 'Run command', 'Grep': 'Search code', 'Glob': 'Search files',
        'WebSearch': 'Search web', 'WebFetch': 'Fetch URL',
        'TaskCreate': 'Create task', 'TaskUpdate': 'Update task', 'TaskList': 'List tasks',
    }

    def render_tool_call(self, name: str, arguments: dict, success: bool = True):
        short_args = self._format_args(arguments)
        ESC = chr(27)
        if success:
            sys.stdout.write(f'  {ESC}[5m●{ESC}[25m {ESC}[38;2;135;206;250m{name}{ESC}[0m({short_args}){ESC}[K\n')
        else:
            sys.stdout.write(f'  {ESC}[5m●{ESC}[25m {ESC}[38;2;255;100;180m{name}{ESC}[0m({short_args}){ESC}[K\n')
        sys.stdout.flush()

    def render_pre_tool(self, hint: str, name: str, arguments: dict):
        import shutil
        cols = shutil.get_terminal_size().columns
        sep = ('─' * (cols // 2))[:cols]
        self.console.print(f'[dim]{sep}[/dim]')
        detail = self._pre_tool_detail(name, arguments)
        esc = chr(27)
        blink = f'{esc}[5m●{esc}[25m'
        if detail:
            sys.stdout.write(f'  {blink} {esc}[1m→ {hint}{esc}[0m {esc}[2m{detail}{esc}[0m{esc}[K\n')
        else:
            sys.stdout.write(f'  {blink} {esc}[1m→ {hint}{esc}[0m{esc}[K\n')
        sys.stdout.flush()

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
            ESC = chr(27)
            import re as _re
            for line in ansi.rstrip('\n').split('\n'):
                clean = _re.sub(r'\x1b\[(0|49)?m', '', line)
                sys.stdout.write(f'{ESC}[48;2;32;32;32m{ESC}[K  {clean}{ESC}[0m{ESC}[48;2;32;32;32m{ESC}[K{ESC}[0m\n')
            self.console.print(f'[dim]{"╌" * cols}[/dim]')

        # Diff preview for Edit
        elif name == 'Edit':
            old = arguments.get('old_string', '')
            new = arguments.get('new_string', '')
            if old or new:
                self.console.print(f'[dim]{"╌" * cols}[/dim]')
                self.render_unified_diff(old, new)
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
            if name in ('Glob', 'Grep'):
                lines = output.split('\n')
                if len(lines) > 2:
                    output = '\n'.join(lines[:2]) + f'\n... and {len(lines) - 2} more lines'
            elif len(output) > 500:
                output = output[:500] + f'\n... [truncated {len(result.output) - 500} chars]'
            if output:
                self.console.print(f'  [rgb(135,206,250)]✓[/rgb(135,206,250)] [rgb(135,206,250)]{output}[/rgb(135,206,250)]')
            else:
                self.console.print(f'  [rgb(135,206,250)]✓[/rgb(135,206,250)]')
        else:
            error = result.error or 'Unknown error'
            self.console.print(f'  [rgb(255,100,180)]✗[/rgb(255,100,180)] [rgb(255,100,180)]{error}[/rgb(255,100,180)]')

    def render_error(self, error: str):
        self.console.print(f'\n[bold red]Error:[/bold red] {error}\n')

    @staticmethod
    def _render_ansi(renderable) -> str:
        import re
        buf = StringIO()
        tmp = RichConsole(file=buf, force_terminal=True, color_system='truecolor')
        tmp.print(renderable)
        result = buf.getvalue()
        result = re.sub(r'[ ]+(\x1b\[0m)?$', r'\1', result, flags=re.MULTILINE)
        return result

    def render_code_block(self, code: str, language: str=''):
        ESC = chr(27)
        lang = language or 'text'
        total_lines = len(code.split('\n'))
        ansi = self._render_ansi(Syntax(code, lang, theme='native', line_numbers=True))
        lines = ansi.rstrip('\n').split('\n')
        truncated = len(lines) > 25
        if truncated:
            lines = lines[:25]
        import re as _re
        for line in lines:
            # Strip ALL reset codes so our background persists through the whole line
            clean = _re.sub(r'\x1b\[(0|49)?m', '', line)
            sys.stdout.write(f'{ESC}[48;2;32;32;32m{ESC}[K  {clean}{ESC}[0m{ESC}[48;2;32;32;32m{ESC}[K{ESC}[0m\n')
        if truncated:
            self.console.print(f'  [dim]... truncated, showing 25/{total_lines} lines[/dim]')

    def render_diff(self, old: str, new: str, language: str=''):
        ESC = chr(27)
        if not old and (not new):
            return
        if old:
            for line in old.rstrip('\n').split('\n'):
                sys.stdout.write(f'  {ESC}[48;2;80;30;30m{ESC}[K- {line}{ESC}[K{ESC}[0m\n')
        if new:
            for line in new.rstrip('\n').split('\n'):
                sys.stdout.write(f'  {ESC}[48;2;30;80;30m{ESC}[K+ {line}{ESC}[K{ESC}[0m\n')

    def render_unified_diff(self, old: str, new: str, language: str=''):
        ESC = chr(27)
        RED_BG = f'{ESC}[48;2;80;30;30m'
        GRN_BG = f'{ESC}[48;2;30;80;30m'
        RST = f'{ESC}[0m'
        old_lines = old.split('\n')
        new_lines = new.split('\n')
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        blocks = list(matcher.get_grouped_opcodes(n=3))
        if not blocks:
            return
        added = 0
        removed = 0
        out_lines = []
        for block in blocks:
            for tag, i1, i2, j1, j2 in block:
                if tag == 'equal':
                    for i in range(i1, min(i2, i1 + 3)):
                        out_lines.append(('ctx', i + 1, old_lines[i]))
                    if i2 - i1 > 6:
                        n = i2 - i1 - 6
                        out_lines.append(('skip', 0, f'... ({n} unchanged lines)'))
                        for i in range(i2 - 3, i2):
                            out_lines.append(('ctx', i + 1, old_lines[i]))
                    elif i2 - i1 > 3:
                        for i in range(i1 + 3, i2):
                            out_lines.append(('ctx', i + 1, old_lines[i]))
                elif tag == 'replace':
                    for i in range(i1, i2):
                        out_lines.append(('del', i + 1, old_lines[i]))
                        removed += 1
                    for j in range(j1, j2):
                        out_lines.append(('add', j + 1, new_lines[j]))
                        added += 1
                elif tag == 'delete':
                    for i in range(i1, i2):
                        out_lines.append(('del', i + 1, old_lines[i]))
                        removed += 1
                elif tag == 'insert':
                    for j in range(j1, j2):
                        out_lines.append(('add', j + 1, new_lines[j]))
                        added += 1
            if block != blocks[-1]:
                out_lines.append(('sep', 0, '···'))
        # Summary
        parts = []
        if added: parts.append(f'Added {added} lines')
        if removed: parts.append(f'removed {removed} lines')
        if parts:
            self.console.print(f'  [bold]⎿  {", ".join(parts)}[/bold]')
        # Render
        for tag, ln, text in out_lines:
            if tag == 'del':
                sys.stdout.write(f'  {RED_BG}{ESC}[K{ln:>4} - {text}{ESC}[K{RST}\n')
            elif tag == 'add':
                sys.stdout.write(f'  {GRN_BG}{ESC}[K{ln:>4} + {text}{ESC}[K{RST}\n')
            elif tag == 'ctx':
                sys.stdout.write(f'  {ln:>4}   {text}\n')
            elif tag == 'skip':
                sys.stdout.write(f'        {text}\n')
            elif tag == 'sep':
                sys.stdout.write(f'    ···\n')

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

    def prompt_form(self, questions: list[dict]) -> dict:
        """Multi-tab form for AskUserQuestion. Returns {header: [selected_labels]} or {'__cancelled__': True}."""
        import shutil
        cols = shutil.get_terminal_size().columns
        sep = '─' * cols

        if not questions:
            return {}

        # State
        tab_idx = [0]
        selected: list[set] = [set() for _ in questions]
        cursor = [0]
        cancelled = [False]

        kb = KeyBindings()

        def _move_cursor(delta):
            q = questions[tab_idx[0]]
            opts = q.get('options', [])
            has_next = q.get('multiSelect', True)
            n = len(opts) + (1 if has_next else 0)
            cursor[0] = max(0, min(n - 1, cursor[0] + delta))

        @kb.add('up')
        def _(event): _move_cursor(-1); event.app.invalidate()

        @kb.add('down')
        def _(event): _move_cursor(1); event.app.invalidate()

        @kb.add('left')
        def _(event):
            if tab_idx[0] > 0:
                tab_idx[0] -= 1
                cursor[0] = 0
            event.app.invalidate()

        @kb.add('right')
        def _(event):
            if tab_idx[0] < len(questions) - 1:
                tab_idx[0] += 1
                cursor[0] = 0
            event.app.invalidate()

        @kb.add('space')
        def _(event):
            q = questions[tab_idx[0]]
            opts = q.get('options', [])
            if opts and cursor[0] < len(opts):
                sel = selected[tab_idx[0]]
                if cursor[0] in sel:
                    sel.discard(cursor[0])
                else:
                    sel.add(cursor[0])
            event.app.invalidate()

        @kb.add('enter')
        def _(event):
            q = questions[tab_idx[0]]
            opts = q.get('options', [])
            is_multi = q.get('multiSelect', True)
            if not is_multi:
                if cursor[0] < len(opts):
                    selected[tab_idx[0]] = {cursor[0]}
                if tab_idx[0] < len(questions) - 1:
                    tab_idx[0] += 1; cursor[0] = 0
                else:
                    event.app.exit(result=_build_result(questions, selected))
            else:
                if cursor[0] >= len(opts):
                    if tab_idx[0] < len(questions) - 1:
                        tab_idx[0] += 1; cursor[0] = 0
                    else:
                        event.app.exit(result=_build_result(questions, selected))
            event.app.invalidate()

        @kb.add('c-c')
        def _(event):
            cancelled[0] = True
            event.app.exit(result={'__cancelled__': True})

        @kb.add('escape')
        def _(event):
            cancelled[0] = True
            event.app.exit(result={'__cancelled__': True})

        def _build_result(qs, sel) -> dict:
            result = {}
            for i, q in enumerate(qs):
                header = q.get('header', f'Q{i+1}')
                opts = q.get('options', [])
                if opts:
                    chosen = [opts[j].get('label', opts[j]) if isinstance(opts[j], dict) else str(opts[j])
                              for j in sorted(sel[i])]
                    result[header] = chosen if chosen else ['(no selection)']
                else:
                    result[header] = ''
            return result

        def _build_text():
            q = questions[tab_idx[0]]
            question_text = q.get('question', '')
            opts = q.get('options', [])
            is_multi = q.get('multiSelect', True)

            # Build as prompt_toolkit formatted text: list of (style, text) tuples
            result = []

            # Top separator
            result.append(('class:dim', sep))
            result.append(('', '\n'))

            # Tab bar: ←  tabs  ✔ Submit  →
            result.append(('class:dim', '←  '))
            for i, tq in enumerate(questions):
                hdr = tq.get('header', f'Q{i+1}')[:12]
                icon = '☑' if selected[i] else '☐'
                if i == tab_idx[0]:
                    result.append(('class:bold', f'{icon} {hdr}'))
                else:
                    result.append(('class:dim', f'{icon} {hdr}'))
                if i < len(questions) - 1:
                    result.append(('', '  '))
            result.append(('', '  '))
            result.append(('bold #00d700', '✔ Submit'))
            result.append(('class:dim', '  →'))
            result.append(('', '\n\n'))

            # Question
            result.append(('class:bold', f'  {question_text}'))
            result.append(('', '\n\n'))

            # Options
            for idx, opt in enumerate(opts):
                label = opt.get('label', opt) if isinstance(opt, dict) else str(opt)
                desc = opt.get('description', '') if isinstance(opt, dict) else ''
                checked = 'x' if idx in selected[tab_idx[0]] else ' '
                cursor_mark = '❯' if cursor[0] == idx else ' '
                result.append(('', f'  {cursor_mark} {idx + 1}. [{checked}] {label}'))
                result.append(('', '\n'))
                if desc:
                    result.append(('class:dim', f'     {desc}'))
                    result.append(('', '\n'))

            # Next/Done row for multi-select
            if is_multi:
                next_label = 'Next tab →' if tab_idx[0] < len(questions) - 1 else 'Done ✓'
                cursor_mark = '❯' if cursor[0] >= len(opts) else ' '
                result.append(('', f'  {cursor_mark} {len(opts) + 1}. [ ] {next_label}'))
                result.append(('', '\n'))

            # Bottom separator
            result.append(('class:dim', sep))
            return result

        control = FormattedTextControl(text=_build_text)
        window = Window(content=control)

        style = Style.from_dict({
            'dim': '#888888',
            'bold': 'bold',
        })

        app = Application(
            layout=Layout(window),
            key_bindings=kb,
            full_screen=True,
            erase_when_done=True,
            style=style,
        )
        try:
            return app.run()
        except (KeyboardInterrupt, EOFError):
            return {'__cancelled__': True}

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


class HeadlessRenderer:
    """Minimal renderer for headless mode (MCP, CI). Plain-text only, no TUI."""

    def __init__(self):
        pass

    def welcome(self, version=''):
        pass

    def render_text(self, text: str):
        print(text)

    def render_tool_output_line(self, tool_name: str, line: str, stream: str = 'stdout'):
        if stream in ('explore-done',):
            return
        print(line)

    def render_tool_call(self, name, arguments, success=True):
        pass

    def render_tool_result(self, name, arguments, result):
        if result.success:
            output = (result.output or '')[:200]
            if output:
                print(f'  [{name}] {output}')
        else:
            print(f'  [{name}] ERROR: {result.error}')

    def render_error(self, error: str):
        print(f'Error: {error}')

    def render_pre_tool(self, hint, name, arguments):
        pass

    def render_code_block(self, code, language=''):
        pass

    def render_unified_diff(self, old, new, language=''):
        pass

    def render_approval_block(self, name, arguments):
        return 'Proceed?'

    def render_explore_start(self, description):
        pass

    def render_explore_summary(self, sub_tool_count, sub_tool_names):
        pass

    def render_agent_summary(self, tool_stats, duration_ms):
        pass

    def start_live_markdown(self):
        pass

    def update_live_markdown(self, text):
        pass

    def stop_live_markdown(self):
        pass

    def prompt_choice(self, question='', options=None):
        return 0  # auto-approve in headless

    def prompt_form(self, questions):
        return {}

    def prompt(self, text='> '):
        return ''
