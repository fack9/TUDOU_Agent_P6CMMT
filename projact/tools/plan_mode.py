from datetime import datetime
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolResult
PLAN_MODE_INSTRUCTIONS = 'You are now in **Plan Mode**. Follow these rules:\n\n1. **Explore and research** — read files, search the codebase, fetch documentation. You may use read-only Bash commands (ls, cat, git log, python --version, pip list, etc.) for environment inspection.\n2. **Resolve ambiguities FIRST** — if you have multiple valid approaches or need the user to choose between options, pause plan writing and ASK THE USER DIRECTLY IN THE CONVERSATION. Do NOT write questions into the plan file. The user sees your conversation output before the plan.\n3. **Write your plan** to the plan file path shown above using the Write tool. The plan must be a COMPLETE, DETERMINISTIC document with NO open questions. All user choices must have been resolved before you start writing.\n4. **Do NOT implement** — only plan. Do not edit source files or run destructive commands (rm, pip install, git push, etc.).\n5. **When the plan is complete**, call ExitPlanMode to present it for approval.\n\nThe plan should include:\n- Step-by-step implementation approach\n- Files to create or modify\n- Key design decisions and trade-offs\n- Testing considerations'

class EnterPlanModeTool(BaseTool):
    name = 'EnterPlanMode'
    description = 'Use this tool proactively before implementing non-trivial or large tasks. Transitions into plan mode: explore the codebase, design an approach, and write a plan to a plan file. While in plan mode you cannot edit source files or run commands — only read/search and write the plan file. Call ExitPlanMode when the plan is ready for user approval. IMPORTANT: you should enter plan mode for ANY task that involves multi-file changes, architectural decisions, or more than a few lines of code. The user expects you to plan first, code second.'
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, plan_state: dict[str, Any], plans_dir: Path):
        self._state = plan_state
        self._plans_dir = plans_dir

    def execute(self, **kwargs) -> ToolResult:
        if self._state.get('active'):
            plan_file = self._state.get('plan_file', 'unknown')
            return ToolResult(success=True, output=f'Already in plan mode.\n\nPlan file: {plan_file}\n\nContinue writing your plan, then call ExitPlanMode.')
        self._plans_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plan_file = self._plans_dir / f'plan_{timestamp}.md'
        self._state['active'] = True
        self._state['plan_file'] = plan_file
        return ToolResult(success=True, output=f'Plan mode activated.\n\nPlan file: {plan_file}\n\n{PLAN_MODE_INSTRUCTIONS}')

class ExitPlanModeTool(BaseTool):
    name = 'ExitPlanMode'
    description = 'Present the completed plan to the user for approval. The plan is read from the plan file and shown to the user. If approved, plan mode ends and implementation can begin. If rejected, you remain in plan mode to revise.'
    permission_level = 'needs_approval'
    is_read_only = True

    def __init__(self, plan_state: dict[str, Any]):
        self._state = plan_state

    def execute(self, **kwargs) -> ToolResult:
        if not self._state.get('active'):
            return ToolResult(success=False, output='', error='Not in plan mode. Call EnterPlanMode first.')
        plan_file = self._state.get('plan_file')
        if not plan_file or not plan_file.exists():
            return ToolResult(success=False, output='', error='Plan file not found. Write your plan first using the Write tool.')
        plan_content = plan_file.read_text(encoding='utf-8', errors='replace')
        if not plan_content.strip():
            return ToolResult(success=False, output='', error='Plan file is empty. Write your plan first.')
        return ToolResult(success=True, output=f'Plan submitted for approval. Waiting for user review...\n\n## Plan Summary\n\n{plan_content[:3000]}')

    def get_plan_content(self) -> str:
        plan_file = self._state.get('plan_file')
        if plan_file and plan_file.exists():
            return plan_file.read_text(encoding='utf-8', errors='replace')
        return ''
