from __future__ import annotations
import uuid
from collections import OrderedDict


class CCRStore:
    """Central Context Repository — stores original tool outputs before compression.

    When a tool result gets truncated, the original is stored here with a short
    retrieval ID. The LLM sees a CCR hint in the truncated output and can use
    the Retrieve tool to fetch the full original when needed.
    """

    def __init__(self, max_entries: int = 500):
        self._store: OrderedDict[str, str] = OrderedDict()
        self._max = max_entries

    def store(self, content: str) -> str:
        """Store original content. Returns a short retrieval ID."""
        rid = uuid.uuid4().hex[:8]
        if len(self._store) >= self._max:
            self._store.popitem(last=False)
        self._store[rid] = content
        return rid

    def retrieve(self, rid: str) -> str | None:
        """Retrieve original content by ID. Moves entry to end (MRU)."""
        if rid not in self._store:
            return None
        self._store.move_to_end(rid)
        return self._store[rid]

    @property
    def stats(self) -> dict:
        return {
            'entries': len(self._store),
            'total_chars': sum(len(v) for v in self._store.values()),
        }

    def clear(self):
        self._store.clear()
