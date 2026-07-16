"""把查询、检索、记忆和历史路由链组合成应用服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from yiyan_dingzhen import prompts
from yiyan_dingzhen.config import Settings
from yiyan_dingzhen.domain import AnswerResult, Document, ScoredDocument
from yiyan_dingzhen.llm import EmbeddingModel, create_chat_model, create_embedding_model
from yiyan_dingzhen.memory import MemoryTurn, SessionMemoryRegistry
from yiyan_dingzhen.query import prepare_query
from yiyan_dingzhen.retrieval import (
    AnnoyRetriever,
    append_unique_documents,
    create_default_retriever,
    merge_scored_documents,
    pad_documents,
    search_memory,
)
from yiyan_dingzhen.routing import LegacyRoutingEngine

KNOWLEDGE_CONTEXT_SLOTS = 3
MEMORY_CONTEXT_SLOTS = 3


class Retriever(Protocol):
    def search(self, query: str, *, k: int = 3) -> list[ScoredDocument]: ...

    def keyword_search(self, keywords: list[str], *, k: int = 3) -> list[Document]: ...


class RoutingEngine(Protocol):
    def answer(
        self,
        *,
        query: str,
        related_docs: list[Document],
        document_text: str,
        wenxin_template: str,
    ) -> Any: ...


@dataclass(slots=True)
class AnswerService:
    settings: Settings
    chat_model: Any
    embeddings: EmbeddingModel
    retriever: Retriever
    routing_engine: RoutingEngine
    memories: SessionMemoryRegistry

    @classmethod
    def from_settings(cls, settings: Settings) -> AnswerService:
        chat_model = create_chat_model(settings)
        embeddings = create_embedding_model(settings)
        retriever: AnnoyRetriever = create_default_retriever(
            settings,
            embeddings=embeddings,
        )
        return cls(
            settings=settings,
            chat_model=chat_model,
            embeddings=embeddings,
            retriever=retriever,
            routing_engine=LegacyRoutingEngine(chat_model),
            memories=SessionMemoryRegistry(
                max_sessions=settings.memory_sessions,
                max_turns=settings.memory_turns,
            ),
        )

    def answer(
        self,
        query_text: str,
        *,
        session_id: str = "default",
        document_text: str = "",
    ) -> AnswerResult:
        prepared = prepare_query(
            query_text,
            chat_model=self.chat_model,
            stopwords_path=self.settings.stopwords_path,
        )
        origin_results = self.retriever.search(
            prepared.input_query,
            k=self.settings.retrieval_k,
        )
        translated_results = self.retriever.search(
            prepared.translated_query,
            k=self.settings.retrieval_k,
        )
        retrieved = merge_scored_documents(
            (origin_results, translated_results),
            k=KNOWLEDGE_CONTEXT_SLOTS,
            min_score=self.settings.retrieval_min_score,
        )
        if len(retrieved) < KNOWLEDGE_CONTEXT_SLOTS:
            keyword_documents = self.retriever.keyword_search(
                [str(keyword) for keyword in prepared.keywords],
                k=KNOWLEDGE_CONTEXT_SLOTS,
            )
            retrieved = append_unique_documents(
                retrieved,
                keyword_documents,
                length=KNOWLEDGE_CONTEXT_SLOTS,
            )
        retrieved = pad_documents(retrieved, length=KNOWLEDGE_CONTEXT_SLOTS)

        memory = self.memories.get(session_id)
        memory_documents = search_memory(
            prepared.input_query,
            memory,
            self.embeddings,
            k=MEMORY_CONTEXT_SLOTS,
        )
        related_documents = [*retrieved, *memory_documents]

        wenxin_template = prompts.getWenXin_template(
            prepared.input_query,
            self.chat_model,
        )
        raw = self.routing_engine.answer(
            query=prepared.input_query,
            related_docs=related_documents,
            document_text=document_text,
            wenxin_template=wenxin_template,
        )

        normalized = _normalize_answer(raw)
        turn = MemoryTurn(tag=prepared.input_query)
        turn.add_documents(
            [document for document in retrieved if document.page_content],
            limit=3,
        )
        memory.add(turn)
        return normalized


def _normalize_answer(raw: Any) -> AnswerResult:
    if isinstance(raw, str):
        return AnswerResult(text=raw, raw=raw)
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("result") or raw.get("output")
        if isinstance(text, str):
            return AnswerResult(text=text, raw=raw)
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        return AnswerResult(text=content, raw=raw)
    return AnswerResult(text=str(raw), raw=raw)
