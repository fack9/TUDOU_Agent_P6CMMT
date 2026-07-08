from __future__ import annotations
import threading
from .base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from context.manager import ContextManager, SYSTEM_PROMPT
from context.ccr import CCRStore


SUB_AGENT_PROMPT = (
    '[IRON RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION]\n'
    '1. You are a sub-agent of the main TUDOU_agent. You must FULLY obey the main agent\'s instructions '
    'and return exactly what was asked — no more, no less.\n'
    '2. You are ABSOLUTELY FORBIDDEN from creating new sub-agents or delegating work to other agents. '
    'You do NOT have the Agent tool. Complete the task yourself.\n'
    '3. Stay focused: complete ONLY the assigned task. Do NOT expand scope, explore tangents, '
    'or do "extra" work beyond what was explicitly requested.\n'
    '4. If the task is impossible with your available tools, report that clearly rather than '
    'attempting workarounds or making assumptions.'
)


class AgentTool(BaseTool):
    name = 'Agent'
    description = (
        'Launch a sub-agent to handle a complex, self-contained task independently. '
        'The sub-agent has access to tools (all read-only by default) and returns a consolidated result. '
        'Use this to parallelize independent subtasks — e.g., researching multiple topics simultaneously, '
        'or delegating a well-scoped analysis task.\n\n'
        'You may call Agent up to 4 times in parallel for truly independent subtasks. '
        'Each sub-agent runs in its own thread and returns independently. '
        'DO NOT over-use this — only spawn sub-agents when tasks are genuinely independent '
        'and would benefit from parallel execution.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'prompt': {
                'type': 'string',
                'description': 'Complete task description for the sub-agent. Include all context it needs — the sub-agent starts with a fresh conversation.',
            },
            'tools': {
                'type': 'string',
                'description': 'Comma-separated tool names to grant. Default: all read-only tools. Write tools (Bash/Write/Edit) are excluded by default for safety.',
            },
        },
        'required': ['prompt'],
    }
    permission_level = 'safe'
    is_read_only = False

    DEFAULT_READONLY_TOOLS = {'Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch', 'BrowserFetch', 'Retrieve', 'TaskCreate', 'TaskUpdate', 'TaskList'}

    MAX_INSTANCES = 4
    _active_count = 0
    _count_lock = threading.Lock()

    def __init__(self, llm_client=None, tool_registry: ToolRegistry | None = None, settings=None, timeout: int = 120):
        self._llm = llm_client
        self._registry = tool_registry
        self._settings = settings
        self._timeout = timeout

    def execute(self, prompt: str, tools: str | None = None) -> ToolResult:
        if self._llm is None:
            return ToolResult(success=False, output='', error='Agent tool: LLM client not available.')

        # Check instance limit
        with AgentTool._count_lock:
            if AgentTool._active_count >= AgentTool.MAX_INSTANCES:
                return ToolResult(
                    success=False, output='',
                    error=f'Agent: max {AgentTool.MAX_INSTANCES} sub-agents already running. Wait for some to complete before spawning more.',
                )
            AgentTool._active_count += 1

        try:
            # Filter tool set
            if tools:
                allowed = {t.strip() for t in tools.split(',') if t.strip()}
            else:
                allowed = self.DEFAULT_READONLY_TOOLS

            sub_registry = ToolRegistry()
            for name in allowed:
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
            # Never allow recursive Agent delegation
            sub_registry._tools.pop('Agent', None)

            if sub_registry.tool_count() == 0:
                return ToolResult(success=False, output='', error=f'Agent tool: none of the requested tools ({", ".join(sorted(allowed))}) are available.')

            # Create sub-agent with restriction prompt
            try:
                from agent import TUDOU_Agent
                sub_agent = TUDOU_Agent(
                    settings=self._settings,
                    llm_client=self._llm,
                    tool_registry=sub_registry,
                    context_manager=ContextManager(system_prompt=SUB_AGENT_PROMPT + '\n\n' + SYSTEM_PROMPT),
                    ccr_store=CCRStore(max_entries=50),
                )
            except Exception as e:
                return ToolResult(success=False, output='', error=f'Agent tool: failed to create sub-agent: {e}')

            # Run
            try:
                response = sub_agent.run_conversation(prompt)
            except Exception as e:
                return ToolResult(success=False, output='', error=f'Agent tool: sub-agent failed: {e}')

            return ToolResult(
                success=True,
                output=response.final_message,
                metadata={
                    'tools_used': response.tool_stats,
                    'tokens_input': response.token_usage.input,
                    'tokens_output': response.token_usage.output,
                    'duration_ms': response.duration_ms,
                    'available_tools': sorted(allowed),
                },
            )
        finally:
            with AgentTool._count_lock:
                AgentTool._active_count -= 1
