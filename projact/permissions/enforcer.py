from .modes import PermissionMode

class PermissionEnforcer:

    def __init__(self, mode: PermissionMode=PermissionMode.DEFAULT):
        self.mode = mode
        self._rules: list[tuple[str, str, str]] = []

    def may_execute(self, tool_name: str, params: dict) -> tuple[bool, str]:
        for rule_tool, rule_pattern, action in self._rules:
            if self._match(rule_tool, rule_pattern, tool_name, params):
                if action == 'deny':
                    return (False, f'Denied by rule: {rule_tool} {rule_pattern}')
                elif action == 'allow':
                    return (True, '')
        if self.mode == PermissionMode.AUTO:
            return (True, 'auto mode')
        elif self.mode == PermissionMode.PLAN:
            return (False, 'plan mode: requires approval')
        else:
            return (True, 'default: safe operation')

    def add_rule(self, tool: str, pattern: str, action: str):
        self._rules.append((tool, pattern, action))

    def remove_rule(self, tool: str, pattern: str):
        self._rules = [(t, p, a) for t, p, a in self._rules if not (t == tool and p == pattern)]

    @staticmethod
    def _match(tool: str, pattern: str, tool_name: str, params: dict) -> bool:
        if tool != '*' and tool != tool_name:
            return False
        if pattern == '*':
            return True
        param_str = ' '.join((str(v) for v in params.values()))
        return pattern in param_str
