from __future__ import annotations

import json
from pathlib import Path

import pytest
from annoy import AnnoyIndex

from yiyan_dingzhen.domain import Document, ScoredDocument
from yiyan_dingzhen.memory import MemoryStore, MemoryTurn
from yiyan_dingzhen.retrieval import (
    AnnoyRetriever,
    ArtifactError,
    append_unique_documents,
    load_index_metadata,
    merge_scored_documents,
    search_memory,
)


class FakeEmbeddings:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.mapping = mapping

    def embed_query(self, text: str) -> list[float]:
        return self.mapping[text]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping[text] for text in texts]


def _write_index(path: Path) -> None:
    path.mkdir()
    index = AnnoyIndex(2, "dot")
    index.add_item(0, [1.0, 0.0])
    index.add_item(1, [0.0, 1.0])
    index.build(2)
    index.save(str(path / "index.annoy"))
    (path / "documents.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "dimension": 2,
                "metric": "dot",
                "documents": [
                    {
                        "annoy_id": 0,
                        "page_content": "horizontal",
                        "metadata": {"page": 0},
                    },
                    {
                        "annoy_id": 1,
                        "page_content": "vertical",
                        "metadata": {"page": 1},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_annoy_retriever_uses_safe_json_mapping(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    _write_index(index_dir)
    retriever = AnnoyRetriever(
        index_dir=index_dir,
        embeddings=FakeEmbeddings({"query": [1.0, 0.0]}),
    )

    result = retriever.search("query", k=2)
    assert result[0].document.page_content == "horizontal"
    assert result[0].score >= result[1].score


def test_keyword_search_supplements_vector_results(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    _write_index(index_dir)
    retriever = AnnoyRetriever(
        index_dir=index_dir,
        embeddings=FakeEmbeddings({"query": [1.0, 0.0]}),
    )

    fallback = retriever.keyword_search(["vertical"], k=2)
    combined = append_unique_documents(
        [Document("horizontal")],
        fallback,
        length=2,
    )

    assert [item.page_content for item in combined] == ["horizontal", "vertical"]


def test_merge_scored_documents_deduplicates_and_sorts() -> None:
    document = Document("same", {"page": 1})
    merged = merge_scored_documents(
        (
            [ScoredDocument(document, 0.7), ScoredDocument(Document("boundary"), 0.6)],
            [ScoredDocument(document, 0.9), ScoredDocument(Document("other"), 0.8)],
        ),
        k=3,
        min_score=0.6,
    )
    assert [item.page_content for item in merged] == ["same", "other"]


def test_non_dot_index_is_rejected(tmp_path: Path) -> None:
    metadata = tmp_path / "documents.json"
    metadata.write_text(
        '{"format_version":1,"dimension":2,"metric":"angular","documents":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ArtifactError, match="只支持 dot"):
        load_index_metadata(metadata)


def test_search_memory_returns_most_similar_documents() -> None:
    store = MemoryStore(max_turns=2)
    store.add(
        MemoryTurn(
            tag="old",
            content=[Document("first"), Document("second")],
        )
    )
    embeddings = FakeEmbeddings(
        {
            "query": [1.0, 0.0],
            "first": [1.0, 0.0],
            "second": [0.0, 1.0],
        }
    )
    result = search_memory(
        "query",
        store,
        embeddings,
        k=2,
        min_score=0.5,
    )
    assert result[0].page_content == "first"
    assert result[1].page_content == ""


def test_search_memory_excludes_exact_threshold() -> None:
    store = MemoryStore(max_turns=1)
    store.add(MemoryTurn(tag="old", content=[Document("boundary")]))
    embeddings = FakeEmbeddings(
        {
            "query": [1.0, 0.0],
            "boundary": [0.5, 0.0],
        }
    )

    result = search_memory("query", store, embeddings, k=1, min_score=0.5)

    assert result[0].page_content == ""
