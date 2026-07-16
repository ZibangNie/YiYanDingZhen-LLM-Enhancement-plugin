"""不依赖 LangChain 的核心数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Document:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> Document:
        return cls(page_content="", metadata={})


@dataclass(frozen=True, slots=True)
class ScoredDocument:
    document: Document
    score: float


@dataclass(frozen=True, slots=True)
class AnswerResult:
    text: str
    raw: Any

    def as_legacy_result(self) -> Any:
        """保留旧插件把 LangChain 结果对象放在 result 字段中的行为。"""
        return self.raw
