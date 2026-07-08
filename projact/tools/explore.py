from __future__ import annotations
import sys
from collections.abc import Callable
from .base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from context.manager import ContextManager
from context.ccr import CCRStore


class ExploreTool(BaseTool):
    name = 'Explore'
    description = (
        'Launch a fast sub-agent to explore a codebase. '
        'Use this instead of individual Read/Glob/Grep/Bash calls when you need to '
        'survey a large area — finding files, understanding project structure, or '
        'searching across many directories. '
        'The sub-agent runs multiple read-only tools in parallel and returns a '
        'consolidated summary.\n\n'
        'Provide a short description (shown in the UI) and a detailed exploration prompt '
        'with clear success criteria so the sub-agent knows when to stop.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'description': {
                'type': 'string',
                'description': 'Short label shown in the UI (e.g. "Find auth middleware", "Map API routes").',
            },
            'prompt': {
                'type': 'string',
                'description': 'Complete exploration instructions: what to find, where to look, what to return.',
            },
        },
        'required': ['description', 'prompt'],
    }
    permission_level = 'safe'
    is_read_only = True

    EXPLORE_TOOLS = {'Read', 'Glob', 'Grep', 'Bash', 'WebSearch', 'WebFetch'}

    def __init__(self, llm_client=None, tool_registry: ToolRegistry | None = None, settings=None, timeout: int = 120):
        self._llm = llm_client
        self._registry = tool_registry
        self._settings = settings
        self._timeout = timeout

    def execute(self, description: str, prompt: str, on_output: Callable[[str, str], None] | None = None) -> ToolResult:
        if self._llm is None:
            return ToolResult(success=False, output='', error='Explore: LLM client not available.')

        # Build sub-agent registry with explore-safe tools
        sub_registry = ToolRegistry()
        for name in self.EXPLORE_TOOLS:
            tool_def = self._registry.get(name) if self._registry else None
            if tool_def is not None:
                sub_registry.register(
                    name=tool_def.name,
                    description=tool_def.description,
                    parameters=tool_def.parameters,
                    handler=tool_def.handler,
                    permission_level=tool_def.permission_level,
                    is_read_only=tool_def.is_read_only,
                )

        if sub_registry.tool_count() == 0:
            return ToolResult(success=False, output='', error='Explore: no tools available for sub-agent.')

                # Track sub-tool calls for display (fixed-height block with built-in ghost)
        import shutil as _shutil_ex
        sub_tools_used: list[dict] = []
        _visible_limit = 5
        _FIXED_H = _visible_limit + 6  # 5 tools + counter + blank + sep + status + sep + hint = 11
        _prev_block_lines = 0
        _esc = chr(27)

        def _redraw_block():
            """Redraw the block (6 lines) + ghost (5 lines) = 11 lines total."""
            nonlocal _prev_block_lines
            show = sub_tools_used[-_visible_limit:] if len(sub_tools_used) > _visible_limit else sub_tools_used
            _gsep = '─' * _shutil_ex.get_terminal_size().columns
            _ghint = '  /help  /exit  /clear  /quiet  /tools  /model  /skills  /remote  /tudou'

            if _prev_block_lines > 0:
                sys.stdout.write(f'{_esc}[{_prev_block_lines}A')

            # 5 tool slots
            for i in range(_visible_limit):
                if i < len(show):
                    dl = _format_sub_tool(show[i]['name'], show[i]['args'], done=not show[i].get('running'))
                    sys.stdout.write(f'{_esc}[2K{dl}\n')
                else:
                    sys.stdout.write(f'{_esc}[2K\n')

            # Counter row
            sys.stdout.write(f'{_esc}[2K')
            overflow = len(sub_tools_used) - _visible_limit
            if overflow > 0:
                sys.stdout.write(f'     {_esc}[2m… +{overflow} tools uses{_esc}[0m\n')
            else:
                sys.stdout.write('\n')

            # Ghost footer — same format as _draw_ghost (blank + sep + status + sep + hint)
            sys.stdout.write(f'{_esc}[2K\n')
            sys.stdout.write(f'{_esc}[2K{_esc}[2m{_gsep}{_esc}[0m\n')
            sys.stdout.write(f'{_esc}[2K  {_esc}[2m❯ exploring...{_esc}[0m\n')
            sys.stdout.write(f'{_esc}[2K{_esc}[2m{_gsep}{_esc}[0m\n')
            sys.stdout.write(f'{_esc}[2K{_esc}[2m{_ghint}{_esc}[0m\n')

            sys.stdout.flush()
            _prev_block_lines = _FIXED_H

        def on_sub_pre_tool(name, arguments):
            t = {'name': name, 'args': arguments, 'running': True}
            sub_tools_used.append(t)
            try:
                _redraw_block()
            except Exception:
                pass

        def on_sub_tool_done(name, arguments, result):
            for t in sub_tools_used:
                if t['name'] == name and t.get('running'):
                    t['running'] = False
                    try:
                        _redraw_block()
                    except Exception:
                        pass
                    break

        # Build system prompt for explore sub-agent
        explore_sys = (
            'You are a fast codebase exploration agent. Your job is to search, read, and survey '
            '— never edit files or run destructive commands. '
            'Use Glob/Grep to find files, Read to inspect them, Bash for ls/find/wc/cat. '
            'Run read-only tools in parallel where possible. '
            'Be concise: return findings, not conversation. '
            'When you have enough information to answer the exploration prompt, stop and report.'
        )

        try:
            from agent import TUDOU_Agent
            sub_agent = TUDOU_Agent(
                settings=self._settings,
                llm_client=self._llm,
                tool_registry=sub_registry,
                context_manager=ContextManager(system_prompt=explore_sys),
                ccr_store=CCRStore(max_entries=50),
            )
        except Exception as e:
            return ToolResult(success=False, output='', error=f'Explore: failed to create sub-agent: {e}')

        try:
            response = sub_agent.run_conversation(
                prompt,
                on_pre_tool=on_sub_pre_tool,
                on_tool_call=on_sub_tool_done,
            )
        except Exception as e:
            return ToolResult(success=False, output='', error=f'Explore: sub-agent failed: {e}')

        if on_output:
            try:
                on_output('', 'explore-done')
            except Exception:
                pass

        return ToolResult(
            success=True,
            output=response.final_message,
            metadata={
                'description': description,
                'sub_tools_used': len(sub_tools_used),
                'sub_tool_names': list(set(t['name'] for t in sub_tools_used)),
                'tokens_input': response.token_usage.input,
                'tokens_output': response.token_usage.output,
                'duration_ms': response.duration_ms,
            },
        )


def _format_sub_tool(name: str, arguments: dict, done: bool = False) -> str:
    """Format a sub-tool call for the explore UI. Uses ANSI since output goes via sys.stdout.
    All argument values are truncated to prevent terminal line-wrapping artefacts."""
    _ESC = chr(27)
    C = f'{_ESC}[38;2;135;206;250m'  # light blue
    RUN = f'{_ESC}[38;2;255;200;50m'  # amber — visible against dark bg
    R = f'{_ESC}[0m'                  # reset
    label = f'{C}{name}{R}'
    suffix = '' if done else f'  {RUN}running...{R}'
    if name == 'Bash':
        cmd = arguments.get('command', '')
        if len(cmd) > 90:
            cmd = cmd[:87] + '…'
        return f'  ⎿  {label}({cmd}){suffix}'
    elif name == 'Read':
        fp = arguments.get('file_path', '')
        if len(fp) > 100:
            fp = '…' + fp[-97:]
        return f'  ⎿  {label}({fp}){suffix}'
    elif name == 'Glob':
        pat = arguments.get('pattern', '')
        if len(pat) > 100:
            pat = pat[:97] + '…'
        return f'  ⎿  {label}({pat}){suffix}'
    elif name == 'Grep':
        pat = arguments.get('pattern', '')
        inc = arguments.get('include', '')
        detail = f'{pat}' + (f', include={inc}' if inc else '')
        if len(detail) > 100:
            detail = detail[:97] + '…'
        return f'  ⎿  {label}({detail}){suffix}'
    elif name == 'WebSearch':
        q = arguments.get('query', '')[:60]
        return f'  ⎿  {label}({q}){suffix}'
    elif name == 'WebFetch':
        url = arguments.get('url', '')[:60]
        return f'  ⎿  {label}({url}){suffix}'
    else:
        return f'  ⎿  {label}{suffix}'
