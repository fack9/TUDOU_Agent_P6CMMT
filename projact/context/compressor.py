class ContextCompressor:

    def __init__(self, llm_client=None, summary_model: str = 'claude-haiku-4-5'):
        self._llm = llm_client
        self._summary_model = summary_model
        self._archive: dict[int, list[dict]] = {}  # compressed-out originals, retrievable by ID
        self._archive_counter = 0

    def retrieve_archive(self, archive_id: int) -> list[dict] | None:
        """Return original messages for a compressed archive, or None if evicted."""
        return self._archive.get(archive_id)

    def compress(self, messages: list[dict]) -> list[dict]:
        if len(messages) <= 14:
            return messages
        sys_msg = messages[0] if messages[0].get('role') == 'system' else None
        body = messages[1:] if sys_msg else messages
        tail = self._extract_tail(body, keep_turns=6)
        middle = body[:-len(tail)] if tail else body
        if not middle:
            return messages
        # Save originals before trimming/compressing
        self._archive_counter += 1
        archive_id = self._archive_counter
        self._archive[archive_id] = list(middle)
        # Clean up old archives (keep last 5)
        while len(self._archive) > 5:
            oldest = min(self._archive.keys())
            del self._archive[oldest]
        middle = self._trim_tool_results(middle)
        summaries = self._summarize_groups(middle, turns_per_group=3)
        summary_text = '\n---\n'.join(summaries) if summaries else self._simple_summary(middle)
        result = []
        if sys_msg:
            result.append(sys_msg)
        result.append({'role': 'user', 'content':
            f'<conversation_summary id={archive_id}>\n{summary_text}\n</conversation_summary>'})
        result.extend(tail)
        return result

    def compress_aggressive(self, messages: list[dict]) -> list[dict]:
        if len(messages) <= 8:
            return messages
        sys_msg = messages[0] if messages[0].get('role') == 'system' else None
        body = messages[1:] if sys_msg else messages
        tail = self._extract_tail(body, keep_turns=3)
        middle = body[:-len(tail)] if tail else body
        if not middle:
            return messages
        self._archive_counter += 1
        archive_id = self._archive_counter
        self._archive[archive_id] = list(middle)
        while len(self._archive) > 5:
            oldest = min(self._archive.keys())
            del self._archive[oldest]
        middle = self._trim_tool_results(middle)
        summary = self._llm_summarize(middle, turns_per_group=5)
        result = []
        if sys_msg:
            result.append(sys_msg)
        result.append({'role': 'user', 'content':
            f'<conversation_summary id={archive_id}>\n{summary}\n</conversation_summary>'})
        result.extend(tail)
        return result

    def _llm_summarize(self, messages: list[dict], turns_per_group: int = 5) -> str:
        if not self._llm:
            return self._simple_summary(messages)
        groups = self._group_into_turns(messages, turns_per_group=turns_per_group)
        summaries = []
        for group in groups:
            text = self._build_conversation_text(group)
            prompt = self._build_summary_prompt(text)
            try:
                response = self._llm.complete(messages=[{'role': 'user', 'content': prompt}], model=self._summary_model)
                s = response.content.strip()
                if s:
                    summaries.append(s)
            except Exception:
                s = self._simple_summary(group)
                if s:
                    summaries.append(s)
        return '\n---\n'.join(summaries) if summaries else self._simple_summary(messages)

    def _summarize_groups(self, messages: list[dict], turns_per_group: int = 3) -> list[str]:
        if not self._llm:
            return [self._simple_summary(messages)]
        groups = self._group_into_turns(messages, turns_per_group=turns_per_group)
        summaries = []
        for group in groups:
            text = self._build_conversation_text(group)
            prompt = self._build_summary_prompt(text)
            try:
                response = self._llm.complete(messages=[{'role': 'user', 'content': prompt}], model=self._summary_model)
                s = response.content.strip()
                if s:
                    summaries.append(s)
            except Exception:
                s = self._simple_summary(group)
                if s:
                    summaries.append(s)
        return summaries

    @staticmethod
    def _build_summary_prompt(conversation_text: str) -> str:
        return (
            'Summarize this conversation excerpt for context compression. '
            'Extract only ESSENTIAL information:\n\n'
            '- File paths, function names, line numbers referenced\n'
            '- Key decisions made and their rationale\n'
            '- Code changes: what file was edited, what was added/removed/fixed\n'
            '- Errors encountered and how they were resolved\n'
            '- Commands executed and their important output\n'
            '- User preferences, constraints, or rules explicitly stated\n\n'
            'IGNORE: greetings, small talk, filler text, agent self-description, '
            'tool call boilerplate, thinking/reasoning content.\n\n'
            'Output 4-8 concise bullet points. Keep each bullet under 120 chars.\n\n'
            f'Conversation:\n{conversation_text}'
        )

    @staticmethod
    def _build_conversation_text(messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = m.get('role', '')
            content = ContextCompressor._content_snippet(m)
            if role == 'user':
                lines.append(f'User: {content[:300]}')
            elif role == 'assistant':
                text = content[:200].replace('\n', ' ')
                lines.append(f'Agent: {text}')
                if m.get('tool_calls'):
                    names = [tc.get('function', {}).get('name', '?') for tc in m.get('tool_calls', [])]
                    lines.append(f'  [Called tools: {", ".join(names)}]')
            elif role == 'tool':
                lines.append(f'Tool result ({m.get("tool_call_id", "?")}): {content[:200]}')
        return '\n'.join(lines)

    @staticmethod
    def _extract_tail(messages: list[dict], keep_turns: int) -> list[dict]:
        turns: list[list[dict]] = []
        current: list[dict] = []
        for m in messages:
            if m.get('role') == 'user' and current:
                turns.append(current)
                current = []
            current.append(m)
        if current:
            turns.append(current)
        if len(turns) <= keep_turns:
            return list(messages)
        tail_turns = turns[-keep_turns:]
        result = []
        for turn in tail_turns:
            result.extend(turn)
        return result

    @staticmethod
    def _group_into_turns(messages: list[dict], turns_per_group: int = 3) -> list[list[dict]]:
        turns: list[list[dict]] = []
        current: list[dict] = []
        for m in messages:
            if m.get('role') == 'user' and current:
                turns.append(current)
                current = []
            current.append(m)
        if current:
            turns.append(current)
        groups = []
        for i in range(0, len(turns), turns_per_group):
            group = []
            for turn in turns[i:i + turns_per_group]:
                group.extend(turn)
            groups.append(group)
        return groups

    @staticmethod
    def _simple_summary(messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = m.get('role', '')
            content = ContextCompressor._content_snippet(m)
            if role == 'user' and content:
                lines.append(f'- User asked: {content[:200]}')
            elif role == 'assistant' and content:
                text = content[:200].replace('\n', ' ')
                lines.append(f'- Agent: {text}')
            elif role == 'tool' and content:
                lines.append(f'- Tool result: {content[:150]}')
        return 'Earlier conversation:\n' + '\n'.join(lines[:20]) if lines else ''

    @staticmethod
    def _trim_tool_results(messages: list[dict]) -> list[dict]:
        """Drop old tool-result messages to save space before summarizing.
        Keeps tool results from the most recent 2 turns; drops the rest."""
        # Find the last 2 user-message boundaries
        user_positions = []
        for i, m in enumerate(messages):
            if m.get('role') == 'user':
                user_positions.append(i)
        if len(user_positions) <= 2:
            return messages  # not enough turns to trim
        cutoff = user_positions[-2]  # keep from 2nd-to-last user onward
        trimmed = []
        for i, m in enumerate(messages):
            if i >= cutoff:
                trimmed.append(m)
            elif m.get('role') == 'tool':
                continue  # drop old tool results
            else:
                trimmed.append(m)
        return trimmed

    @staticmethod
    def _content_snippet(msg: dict, max_len: int = 300) -> str:
        content = msg.get('content', '')
        if isinstance(content, str):
            from .content_compressor import content_snippet
            return content_snippet(content, max_len)
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and 'text' in block:
                    from .content_compressor import content_snippet
                    parts.append(content_snippet(block['text'], max_len))
            return ' '.join(parts)[:max_len]
        return str(content)[:max_len]
