import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from .base import BaseTool, ToolResult

@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str = 'pending'
    active_form: str = ''
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    blocks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        if self.started_at:
            end = self.completed_at or time.time()
            return end - self.started_at
        return 0.0

    def to_dict(self):
        return {'id': self.id, 'subject': self.subject, 'description': self.description, 'status': self.status, 'active_form': self.active_form, 'created_at': self.created_at, 'started_at': self.started_at, 'completed_at': self.completed_at, 'blocks': self.blocks, 'blocked_by': self.blocked_by}

    @classmethod
    def from_dict(cls, d):
        return cls(id=d['id'], subject=d['subject'], description=d['description'], status=d.get('status', 'pending'), active_form=d.get('active_form', ''), created_at=d.get('created_at', 0), started_at=d.get('started_at', 0.0), completed_at=d.get('completed_at', 0.0), blocks=d.get('blocks', []), blocked_by=d.get('blocked_by', []))


class TaskManager:

    def __init__(self, conv_id: str, data_dir: Path):
        self._conv_id = conv_id
        self._file = data_dir / f'tasks_{conv_id}.json'
        self._tasks: dict[str, Task] = {}
        self._next_id = 1
        self._load()

    def _load(self):
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for d in data.get('tasks', []):
                    task = Task.from_dict(d)
                    self._tasks[task.id] = task
                    try:
                        n = int(task.id)
                        if n >= self._next_id:
                            self._next_id = n + 1
                    except ValueError:
                        pass
            except (json.JSONDecodeError, OSError):
                pass

    def switch_conversation(self, conv_id: str):
        self._conv_id = conv_id
        self._file = self._file.parent / f'tasks_{conv_id}.json'
        self._tasks.clear()
        self._next_id = 1
        self._load()

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {'conv_id': self._conv_id, 'tasks': [t.to_dict() for t in self._tasks.values()]}
        tmp = self._file.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(self._file)

    def create(self, subject: str, description: str, active_form: str='', blocks: list[str] | None=None, blocked_by: list[str] | None=None) -> Task:
        task = Task(id=str(self._next_id), subject=subject, description=description, active_form=active_form, blocks=blocks or [], blocked_by=blocked_by or [])
        self._next_id += 1
        self._tasks[task.id] = task
        self._save()
        return task

    def update(self, task_id: str, status: str | None=None, subject: str | None=None, description: str | None=None, add_blocks: list[str] | None=None, add_blocked_by: list[str] | None=None) -> Task | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        if status is not None:
            if task.status != status:
                if status == 'in_progress' and not task.started_at:
                    task.started_at = time.time()
                elif status == 'completed' and not task.completed_at:
                    task.completed_at = time.time()
            task.status = status
        if subject is not None:
            task.subject = subject
        if description is not None:
            task.description = description
        if add_blocks:
            for b in add_blocks:
                if b not in task.blocks:
                    task.blocks.append(b)
        if add_blocked_by:
            for b in add_blocked_by:
                if b not in task.blocked_by:
                    task.blocked_by.append(b)
        self._save()
        return task

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def count(self) -> dict[str, int]:
        counts = {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}
        for t in self._tasks.values():
            counts['total'] += 1
            s = t.status
            if s in counts:
                counts[s] += 1
        return counts


class TaskCreateTool(BaseTool):
    name = 'TaskCreate'
    description = 'Create a task to track progress. MANDATORY before any code action (write, edit, bash, search). Call this FIRST, then immediately TaskUpdate to in_progress. Only skip for pure chat with no file/command actions.'
    parameters = {'type': 'object', 'properties': {'subject': {'type': 'string', 'description': 'Brief, actionable title in imperative form'}, 'description': {'type': 'string', 'description': 'What needs to be done'}, 'activeForm': {'type': 'string', 'description': 'Present continuous form shown when task is in progress (e.g. "Running tests")'}}, 'required': ['subject', 'description']}
    permission_level = 'safe'
    is_read_only = False

    def __init__(self, task_manager: TaskManager):
        self._tm = task_manager

    def execute(self, subject: str, description: str, activeForm: str='') -> ToolResult:
        task = self._tm.create(subject=subject, description=description, active_form=activeForm)
        return ToolResult(success=True, output=f'Task [{task.id}] created: {task.subject} (pending)', metadata={'task_id': task.id})


class TaskUpdateTool(BaseTool):
    name = 'TaskUpdate'
    description = 'Update a task status or details. Use to mark progress.'
    parameters = {'type': 'object', 'properties': {'taskId': {'type': 'string', 'description': 'The task ID to update'}, 'status': {'type': 'string', 'description': "New status: pending, in_progress, completed, or deleted"}, 'subject': {'type': 'string', 'description': 'Updated subject'}, 'description': {'type': 'string', 'description': 'Updated description'}, 'addBlocks': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Task IDs that this task now blocks'}, 'addBlockedBy': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Task IDs this task now depends on'}}, 'required': ['taskId']}
    permission_level = 'safe'
    is_read_only = False

    def __init__(self, task_manager: TaskManager):
        self._tm = task_manager

    def execute(self, taskId: str, status: str | None=None, subject: str | None=None, description: str | None=None, addBlocks: list[str] | None=None, addBlockedBy: list[str] | None=None) -> ToolResult:
        task = self._tm.update(taskId, status=status, subject=subject, description=description, add_blocks=addBlocks, add_blocked_by=addBlockedBy)
        if not task:
            return ToolResult(success=False, output='', error=f'Task {taskId} not found')
        return ToolResult(success=True, output=f'Task [{task.id}] updated: {task.subject} → {task.status}', metadata={'task_id': task.id, 'status': task.status})


class TaskListTool(BaseTool):
    name = 'TaskList'
    description = 'List all tasks in the current conversation with their statuses.'
    parameters = {'type': 'object', 'properties': {}, 'required': []}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, task_manager: TaskManager):
        self._tm = task_manager

    def execute(self) -> ToolResult:
        tasks = self._tm.list_tasks()
        if not tasks:
            return ToolResult(success=True, output='No tasks yet.')
        lines = []
        icons = {'pending': '○', 'in_progress': '●', 'completed': '✓', 'deleted': '✗'}
        for t in tasks:
            icon = icons.get(t.status, '?')
            lines.append(f'  [{t.id}] {icon} {t.subject} ({t.status})')
            if t.blocks:
                lines.append(f'      blocks: {", ".join(t.blocks)}')
            if t.blocked_by:
                lines.append(f'      blocked by: {", ".join(t.blocked_by)}')
        return ToolResult(success=True, output='\n'.join(lines), metadata={'count': len(tasks)})
