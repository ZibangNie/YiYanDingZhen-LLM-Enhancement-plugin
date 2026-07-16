"""按会话隔离的短期检索记忆。"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, field
from threading import RLock

from yiyan_dingzhen.domain import Document


@dataclass(slots=True)
class MemoryTurn:
    tag: str
    content: list[Document] = field(default_factory=list)

    def __iter__(self) -> Iterator[Document]:
        return iter(self.content)

    def add_documents(self, documents: list[Document], *, limit: int = 3) -> None:
        self.content.extend(documents[:limit])

    def content_into_memory(self, documents: list[Document]) -> None:
        self.add_documents(documents, limit=3)


class MemoryStore:
    def __init__(self, *, max_turns: int = 10) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        self._max_turns = max_turns
        self._turns: list[MemoryTurn] = []
        self._lock = RLock()

    def __iter__(self) -> Iterator[MemoryTurn]:
        with self._lock:
            return iter(tuple(self._turns))

    def add(self, turn: MemoryTurn) -> None:
        with self._lock:
            self._turns.append(turn)
            if len(self._turns) > self._max_turns:
                del self._turns[: len(self._turns) - self._max_turns]

    def add_memory(self, turn: MemoryTurn) -> None:
        self.add(turn)

    def remove_memory(self, turn: MemoryTurn) -> None:
        with self._lock:
            self._turns.remove(turn)

    def check_empty(self) -> bool:
        with self._lock:
            return not self._turns

    def all_documents(self) -> list[Document]:
        with self._lock:
            return [document for turn in self._turns for document in turn.content]

    def get_all_content_in_memory(self) -> list[Document]:
        return self.all_documents()


class SessionMemoryRegistry:
    def __init__(self, *, max_sessions: int = 512, max_turns: int = 10) -> None:
        self._max_sessions = max_sessions
        self._max_turns = max_turns
        self._sessions: OrderedDict[str, MemoryStore] = OrderedDict()
        self._lock = RLock()

    def get(self, session_id: str) -> MemoryStore:
        normalized = session_id.strip() or "default"
        with self._lock:
            store = self._sessions.pop(normalized, None)
            if store is None:
                store = MemoryStore(max_turns=self._max_turns)
            self._sessions[normalized] = store
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
            return store

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


# 历史名称。
MemoryList = MemoryStore
