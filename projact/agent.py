import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from config.settings import Settings
from llm.client import LLMClient
from llm.types import LLMResponse, TokenUsage
from tools.registry import ToolRegistry, ToolResult
from context.manager import ContextManager
from context.compressor import ContextCompressor
from context.token_tracker import TokenTracker
from context.ccr import CCRStore

@dataclass
class AgentResponse:
    final_message: str
    messages: list[dict] = field(default_factory=list)
    tool_stats: dict = field(default_factory=dict)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    duration_ms: int = 0

class TUDOU_Agent:

    def __init__(self, settings: Settings, llm_client: LLMClient, tool_registry: ToolRegistry | None=None, context_manager: ContextManager | None=None, plan_state: dict | None=None, root_mode: bool=False, ccr_store: CCRStore | None=None, hook_manager=None):
        self.settings = settings
        self.llm = llm_client
        self.tools = tool_registry or ToolRegistry()
        self.context = context_manager or ContextManager()
        self._plan_state = plan_state or {}
        self.root_mode = root_mode
        self.code_mode = False
        ctx_cfg = settings.get('context', {})
        self.max_iterations = settings.max_iterations
        model_limit = ctx_cfg.get('max_tokens')
        if not model_limit:
            try:
                model_limit = llm_client.get_model_limit(settings.model)
            except Exception:
                model_limit = None
        self.tracker = TokenTracker(model=settings.model, max_tokens=model_limit, compress_threshold=ctx_cfg.get('compress_threshold', 0.75), urgent_threshold=ctx_cfg.get('compress_urgent_threshold', 0.9), max_tool_result_chars=ctx_cfg.get('max_tool_result_chars', 15000), max_history_turns=ctx_cfg.get('max_history_turns', 50))
        summary_model = ctx_cfg.get('summary_model') or settings.model
        self.compressor = ContextCompressor(llm_client=llm_client, summary_model=summary_model)
        self.show_usage = ctx_cfg.get('show_usage_on_turn', False)
        self._ccr = ccr_store
        self._hooks = hook_manager

    def chat(self, user_input: str) -> str:
        response = self.run_conversation(user_input)
        return response.final_message

    def run_conversation(self, user_input: str, system_extra: str='', history: list[dict] | None=None, on_tool_call: Any=None, on_approval: Any=None, on_pre_tool: Any=None, get_supplements: Any=None, on_stream_token: Any=None, on_tool_output: Any=None, on_checkpoint: Any=None) -> AgentResponse:
        start_time = time.time()
        tool_stats: dict[str, int] = {}
        total_usage = TokenUsage()
        if history:
            for msg in history:
                self.context.add_to_history(msg)
        worktree_path = str(self.context.working_dir) if self.context.working_dir != Path.cwd() else ''
        messages = self.context.build_messages(user_input=user_input, tools=self.tools.get_schemas() if self.tools.tool_count() > 0 else None, system_extra=system_extra, worktree_path=worktree_path)
        iteration = 0
        final_text = ''
        if self._hooks:
            self._hooks.fire('on_agent_start', user_input=user_input)
        while iteration < self.max_iterations:
            turn_count = iteration
            if get_supplements:
                supps = get_supplements()
                for supp in supps:
                    messages.append({'role': 'user', 'content': f'[Supplement from user while thinking]\n\n{supp}'})
            should_compress, urgent = self.tracker.should_compress(messages, turn_count)
            if should_compress:
                if urgent:
                    messages = self.compressor.compress_aggressive(messages)
                else:
                    messages = self.compressor.compress(messages)
                self.tracker.compression_count += 1
                self.tracker.invalidate_cache()
                if self._hooks:
                    self._hooks.fire('on_compress', count=self.tracker.compression_count)
            response = self.llm.complete(messages=messages, tools=self.tools.get_schemas() if self.tools.tool_count() > 0 else None, on_token=on_stream_token)
            self.tracker.update_after_llm_call(response.usage)
            total_usage.input += response.usage.input
            total_usage.output += response.usage.output
            total_usage.cache_read += response.usage.cache_read
            total_usage.cache_write += response.usage.cache_write
            if response.has_tool_calls():
                # Phase 1: validate + classify
                read_only_calls = []
                write_calls = []
                for tc in response.tool_calls:
                    tool_name = tc.name
                    tool_stats[tool_name] = tool_stats.get(tool_name, 0) + 1

                    if self._plan_state.get('active'):
                        blocked = self._check_plan_mode_block(tool_name, tc.arguments)
                        if blocked:
                            if on_tool_call:
                                on_tool_call(tool_name, tc.arguments, blocked)
                            self._append_tool_messages(messages, tc, response, blocked, response.reasoning_content)
                            continue

                    tool_def = self.tools.get(tool_name)
                    needs_approval = not self.root_mode and tool_def is not None and tool_def.permission_level in ('needs_approval', 'destructive')
                    if needs_approval and on_approval:
                        if not on_approval(tool_name, tc.arguments):
                            result = ToolResult(success=False, output='', error='Execution denied by user.')
                            if on_tool_call:
                                on_tool_call(tool_name, tc.arguments, result)
                            self._append_tool_messages(messages, tc, response, result, response.reasoning_content)
                            continue

                    if tool_def and (tool_def.is_read_only or tc.name == 'Agent'):
                        read_only_calls.append(tc)
                    else:
                        write_calls.append(tc)

                # Phase 2: execute read-only tools in parallel
                if read_only_calls:
                    if len(read_only_calls) > 1:
                        with ThreadPoolExecutor(max_workers=min(len(read_only_calls), 8)) as executor:
                            futures = {}
                            for tc in read_only_calls:
                                if on_pre_tool:
                                    on_pre_tool(tc.name, tc.arguments)
                                if self._hooks:
                                    self._hooks.fire('on_tool_before', name=tc.name, arguments=tc.arguments)
                                tool_output = (lambda n: lambda line, stream='stdout': on_tool_output(line, n, stream) if on_tool_output else None)(tc.name)
                                futures[executor.submit(self.tools.execute, tc.name, tc.arguments, on_output=tool_output)] = tc
                            for future in as_completed(futures):
                                tc = futures[future]
                                try:
                                    result = future.result()
                                except Exception as e:
                                    result = ToolResult(success=False, output='', error=f'Tool execution error: {e}')
                                if on_tool_call:
                                    on_tool_call(tc.name, tc.arguments, result)
                                self._append_tool_messages(messages, tc, response, result, response.reasoning_content)
                    else:
                        tc = read_only_calls[0]
                        if on_pre_tool:
                            on_pre_tool(tc.name, tc.arguments)
                        if self._hooks:
                            self._hooks.fire('on_tool_before', name=tc.name, arguments=tc.arguments)
                        tool_output = (lambda n: lambda line, stream='stdout': on_tool_output(line, n, stream) if on_tool_output else None)(tc.name)
                        try:
                            result = self.tools.execute(tc.name, tc.arguments, on_output=tool_output)
                        except Exception as e:
                            result = ToolResult(success=False, output='', error=f'Tool execution error: {e}')
                        if on_tool_call:
                            on_tool_call(tc.name, tc.arguments, result)
                        self._append_tool_messages(messages, tc, response, result, response.reasoning_content)

                # Phase 3: execute write tools sequentially
                for tc in write_calls:
                    if on_pre_tool:
                        on_pre_tool(tc.name, tc.arguments)
                    if self._hooks:
                        if not self._hooks.fire('on_tool_before', name=tc.name, arguments=tc.arguments):
                            result = ToolResult(success=False, output='', error='Blocked by hook: on_tool_before')
                            if on_tool_call:
                                on_tool_call(tc.name, tc.arguments, result)
                            self._append_tool_messages(messages, tc, response, result, response.reasoning_content)
                            continue
                    tool_output = (lambda n: lambda line, stream='stdout': on_tool_output(line, n, stream) if on_tool_output else None)(tc.name)
                    try:
                        result = self.tools.execute(tc.name, tc.arguments, on_output=tool_output)
                    except Exception as e:
                        result = ToolResult(success=False, output='', error=f'Tool execution error: {e}')
                    if on_tool_call:
                        on_tool_call(tc.name, tc.arguments, result)
                    self._append_tool_messages(messages, tc, response, result, response.reasoning_content)

                iteration += 1
                if on_checkpoint:
                    on_checkpoint(iteration, messages)
                continue
            final_text = response.content
            self.context.add_to_history({'role': 'user', 'content': user_input})
            final_assistant: dict[str, Any] = {'role': 'assistant', 'content': final_text}
            if response.reasoning_content:
                final_assistant['reasoning_content'] = response.reasoning_content
            self.context.add_to_history(final_assistant)
            if on_checkpoint:
                on_checkpoint(iteration, messages)
            break
        if not final_text and iteration >= self.max_iterations:
            final_text = 'Reached maximum iterations without a final response.'
        elapsed = int((time.time() - start_time) * 1000)
        if self._hooks:
            self._hooks.fire('on_agent_stop',
                             user_input=user_input, final_message=final_text,
                             duration_ms=elapsed, tokens_input=total_usage.input,
                             tokens_output=total_usage.output, tool_stats=tool_stats)
        if self.show_usage:
            ratio = self.tracker.usage_ratio()
            pct = f'{ratio * 100:.0f}%'
            final_text += f'\n\n[dim](context: {pct} used, {self.tracker.compression_count} compressions)[/dim]'
        return AgentResponse(final_message=final_text, messages=messages, tool_stats=tool_stats, token_usage=total_usage, duration_ms=elapsed)

    def _check_plan_mode_block(self, tool_name: str, arguments: dict) -> ToolResult | None:
        if self.code_mode:
            return None
        plan_file = self._plan_state.get('plan_file')
        if tool_name == 'Bash':
            return self._check_destructive_bash(arguments)
        if tool_name == 'Edit':
            return ToolResult(success=False, output='', error=f'{tool_name} is not available in plan mode. Only Read, Write (plan file), Glob, Grep, WebSearch, WebFetch, and read-only Bash are allowed.')
        if tool_name == 'Write':
            file_path = arguments.get('file_path', '')
            if not file_path:
                return ToolResult(success=False, output='', error='Write requires file_path.')
            try:
                target = Path(file_path).resolve()
            except (OSError, ValueError):
                return ToolResult(success=False, output='', error='Invalid file path.')
            if plan_file and target == Path(str(plan_file)).resolve():
                return None
            return ToolResult(success=False, output='', error=f'Write is restricted in plan mode. You can only write to the plan file:\n  {plan_file}\n\nTo write to other files, call ExitPlanMode to get plan approval first.')
        return None

    DESTRUCTIVE_BASH_PATTERNS = ['rm', 'rmdir', 'mv', 'dd', 'mkfs', 'format', 'sudo', 'chmod', 'chown', 'kill', 'pkill', 'reboot', 'shutdown', 'pip install', 'pip3 install', 'npm install', 'yarn add', 'apt-get', 'apt', 'yum', 'dnf', 'brew install', 'make', 'cmake', 'gcc', 'g++', 'cargo build', 'go build', 'docker', 'kubectl', 'git push', 'git commit', 'git merge', 'git rebase', 'git reset', 'git clean', 'git stash drop', 'git branch -D', 'git tag -d', 'del', 'erase', 'copy', 'move', 'ren', 'mkdir', 'wget', 'curl -o', 'curl -O', 'scp', 'rsync']

    @classmethod
    def _get_destructive_regexes(cls):
        if not hasattr(cls, '_destructive_regexes_cache'):
            compiled = []
            for pattern in cls.DESTRUCTIVE_BASH_PATTERNS:
                parts = [re.escape(p) for p in pattern.strip().split()]
                regex = r'(?<!\w)' + r'\s+'.join(parts) + r'(?!\w)'
                compiled.append(re.compile(regex))
            cls._destructive_regexes_cache = compiled
        return cls._destructive_regexes_cache

    @classmethod
    def _check_destructive_bash(cls, arguments: dict) -> ToolResult | None:
        cmd = arguments.get('command', '')
        cmd_lower = cmd.lower().strip()
        for pattern_re in cls._get_destructive_regexes():
            match = pattern_re.search(cmd_lower)
            if match:
                return ToolResult(success=False, output='', error=f'Bash command blocked in plan mode — destructive pattern detected: "{match.group()}". In plan mode, only read-only Bash commands are allowed (e.g., ls, cat, git log, python --version, pip list, etc.).')
        if re.search(r'(?<![0-9&])\s*>>?\s*[^&]', cmd):
            return ToolResult(success=False, output='', error='Bash command blocked in plan mode — destructive redirect (>/>>). Use read-only commands only (e.g., ls, cat, git log).')
        return None

    def _append_tool_messages(self, messages: list[dict], tc: Any, response: LLMResponse, result: ToolResult, reasoning_content: str):
        if self._hooks:
            self._hooks.fire('on_tool_after', name=tc.name, arguments=tc.arguments, success=result.success)

        result_text = result.output if result.success else f'Error: {result.error}'
        original_len = len(result_text)
        truncated = self.tracker.truncate_tool_result(result_text, self.tracker.max_tool_result_chars)

        # CCR: store original if truncation happened
        if len(truncated) < original_len and self._ccr is not None:
            rid = self._ccr.store(result_text)
            truncated += f'\n\n[CCR:{rid} | original: {original_len} chars | use Retrieve to fetch full content]'

        assistant_msg: dict[str, Any] = {'role': 'assistant', 'content': response.content or '', 'tool_calls': [{'id': tc.id, 'type': 'function', 'function': {'name': tc.name, 'arguments': json.dumps(tc.arguments, ensure_ascii=False) if isinstance(tc.arguments, dict) else tc.arguments}}]}
        if reasoning_content:
            assistant_msg['reasoning_content'] = reasoning_content
        messages.append(assistant_msg)

        # Build tool response — support image content blocks
        tool_content: str | list[dict] = truncated
        if result.images:
            content_blocks = [{'type': 'text', 'text': truncated}]
            for img in result.images:
                content_blocks.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': img['media_type'],
                        'data': img['base64'],
                    }
                })
            tool_content = content_blocks
        messages.append({'role': 'tool', 'tool_call_id': tc.id, 'content': tool_content})
