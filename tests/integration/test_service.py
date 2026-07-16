from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from yiyan_dingzhen.domain import Document, ScoredDocument
from yiyan_dingzhen.memory import SessionMemoryRegistry
from yiyan_dingzhen.service import AnswerService


class FakeChatModel:
    def invoke(self, prompt):
        if "翻译为英文" in prompt:
            return "translated question"
        return "dynamic physics prompt"


class FakeEmbeddings:
    vectors = {
        "问题": [1.0, 0.0],
        "translated question": [1.0, 0.0],
        "context": [1.0, 0.0],
    }

    def embed_query(self, text: str) -> list[float]:
        return self.vectors.get(text, [1.0, 0.0])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors.get(text, [1.0, 0.0]) for text in texts]


class FakeRetriever:
    def search(self, query: str, *, k: int = 3):
        if query == "translated question":
            return []
        return [
            ScoredDocument(
                Document(f"{query}-context-{index}", {"query": query}),
                0.9 - index / 100,
            )
            for index in range(k)
        ]

    def keyword_search(self, keywords: list[str], *, k: int = 3):
        return []


@dataclass
class FakeRoutingEngine:
    calls: list[dict]

    def answer(self, **kwargs):
        self.calls.append(kwargs)
        return {"input": kwargs["query"], "text": "final answer"}


@pytest.mark.integration
def test_service_combines_retrieval_and_memory(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "yiyan_dingzhen.service.prepare_query",
        lambda text, **_kwargs: SimpleNamespace(
            input_query=text,
            translated_query="translated question",
            keywords=[],
        ),
    )
    monkeypatch.setattr(
        "yiyan_dingzhen.service.prompts.getWenXin_template",
        lambda _query, _model: "dynamic physics prompt",
    )
    routing = FakeRoutingEngine([])
    service = AnswerService(
        settings=replace(settings, retrieval_k=6),
        chat_model=FakeChatModel(),
        embeddings=FakeEmbeddings(),
        retriever=FakeRetriever(),
        routing_engine=routing,
        memories=SessionMemoryRegistry(max_sessions=2, max_turns=2),
    )

    first = service.answer("first", session_id="session")
    second = service.answer("second", session_id="session")

    assert first.text == "final answer"
    assert second.text == "final answer"
    assert len(routing.calls) == 2
    assert len(routing.calls[0]["related_docs"]) == 6
    assert [document.page_content for document in routing.calls[1]["related_docs"][:3]] == [
        "second-context-0",
        "second-context-1",
        "second-context-2",
    ]
    assert {document.page_content for document in routing.calls[1]["related_docs"][3:]} == {
        "first-context-0",
        "first-context-1",
        "first-context-2",
    }
