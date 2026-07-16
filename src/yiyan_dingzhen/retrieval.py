"""安全的 Annoy 检索与短期记忆检索。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np

from yiyan_dingzhen.config import Settings
from yiyan_dingzhen.domain import Document, ScoredDocument
from yiyan_dingzhen.llm import EmbeddingModel, create_embedding_model
from yiyan_dingzhen.memory import MemoryStore


class ArtifactError(RuntimeError):
    """索引资产缺失、损坏或格式不受支持。"""


@dataclass(frozen=True, slots=True)
class IndexMetadata:
    dimension: int
    metric: str
    documents: tuple[Document, ...]


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_index_metadata(path: Path) -> IndexMetadata:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactError(f"缺少索引文档映射：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"索引文档映射不是有效 JSON：{path}") from exc

    if payload.get("format_version") != 1:
        raise ArtifactError("不支持的索引文档映射版本")
    dimension = payload.get("dimension")
    metric = payload.get("metric")
    rows = payload.get("documents")
    if not isinstance(dimension, int) or dimension <= 0:
        raise ArtifactError("索引 dimension 无效")
    if metric != "dot":
        raise ArtifactError("当前运行时只支持 dot metric")
    if not isinstance(rows, list):
        raise ArtifactError("索引 documents 必须是数组")

    documents_by_id: dict[int, Document] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ArtifactError("索引文档记录必须是对象")
        annoy_id = row.get("annoy_id")
        content = row.get("page_content")
        metadata = row.get("metadata", {})
        if not isinstance(annoy_id, int) or annoy_id < 0:
            raise ArtifactError("索引文档 annoy_id 无效")
        if not isinstance(content, str) or not isinstance(metadata, dict):
            raise ArtifactError("索引文档内容或 metadata 无效")
        if annoy_id in documents_by_id:
            raise ArtifactError(f"索引文档 annoy_id 重复：{annoy_id}")
        documents_by_id[annoy_id] = Document(content, metadata)

    expected_ids = list(range(len(documents_by_id)))
    if sorted(documents_by_id) != expected_ids:
        raise ArtifactError("索引文档 annoy_id 必须从 0 连续编号")
    return IndexMetadata(
        dimension=dimension,
        metric=metric,
        documents=tuple(documents_by_id[index] for index in expected_ids),
    )


class AnnoyRetriever:
    """读取 Annoy 二进制和安全 JSON 映射，不在运行时加载 pickle。"""

    def __init__(
        self,
        *,
        index_dir: Path,
        embeddings: EmbeddingModel,
    ) -> None:
        self.index_dir = index_dir.resolve()
        self.embeddings = embeddings
        self.metadata = load_index_metadata(self.index_dir / "documents.json")
        index_path = self.index_dir / "index.annoy"
        if not index_path.is_file():
            raise ArtifactError(f"缺少 Annoy 索引：{index_path}")

        try:
            from annoy import AnnoyIndex
        except ImportError as exc:
            raise ArtifactError("缺少 annoy 依赖") from exc

        metric = cast(
            Literal["dot"],
            self.metadata.metric,
        )
        self._index = AnnoyIndex(self.metadata.dimension, metric)
        if not self._index.load(str(index_path)):
            raise ArtifactError(f"无法加载 Annoy 索引：{index_path}")
        if self._index.get_n_items() != len(self.metadata.documents):
            raise ArtifactError("Annoy 索引条目数与 documents.json 不一致")

    def search(self, query: str, *, k: int = 3) -> list[ScoredDocument]:
        if not query.strip():
            return []
        vector = self.embeddings.embed_query(query)
        if len(vector) != self.metadata.dimension:
            raise ArtifactError(
                f"查询向量维度 {len(vector)} 与索引维度 {self.metadata.dimension} 不一致"
            )
        count = min(k, len(self.metadata.documents))
        ids, scores = self._index.get_nns_by_vector(
            vector,
            count,
            include_distances=True,
        )
        return [
            ScoredDocument(self.metadata.documents[index], float(score))
            for index, score in zip(ids, scores, strict=True)
        ]

    def keyword_search(self, keywords: list[str], *, k: int = 3) -> list[Document]:
        normalized = tuple(
            dict.fromkeys(keyword.strip().lower() for keyword in keywords if keyword.strip())
        )
        if not normalized:
            return []

        scored: list[tuple[float, int, Document]] = []
        for position, document in enumerate(self.metadata.documents):
            content = document.page_content.lower()
            matched = sum(keyword in content for keyword in normalized)
            if not matched:
                continue
            frequency = sum(content.count(keyword) for keyword in normalized)
            score = matched / len(normalized) + min(frequency, 100) / 10_000
            scored.append((score, -position, document))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [document for _score, _position, document in scored[:k]]


def create_default_retriever(
    settings: Settings,
    *,
    embeddings: EmbeddingModel | None = None,
) -> AnnoyRetriever:
    return AnnoyRetriever(
        index_dir=settings.index_dir,
        embeddings=embeddings or create_embedding_model(settings),
    )


def merge_scored_documents(
    result_sets: Iterable[Iterable[ScoredDocument]],
    *,
    k: int,
    min_score: float,
) -> list[Document]:
    """Annoy dot 索引的分数越高越相关；合并、去重后取前 k 个。"""
    best: dict[tuple[str, str, str], ScoredDocument] = {}
    for result_set in result_sets:
        for item in result_set:
            if item.score <= min_score:
                continue
            metadata = item.document.metadata
            key = (
                item.document.page_content,
                str(metadata.get("source", "")),
                str(metadata.get("page", "")),
            )
            current = best.get(key)
            if current is None or item.score > current.score:
                best[key] = item
    ordered = sorted(best.values(), key=lambda item: item.score, reverse=True)
    return [item.document for item in ordered[:k]]


def pad_documents(documents: Iterable[Document], *, length: int) -> list[Document]:
    result = list(documents)[:length]
    result.extend(Document.empty() for _ in range(length - len(result)))
    return result


def append_unique_documents(
    primary: Iterable[Document],
    fallback: Iterable[Document],
    *,
    length: int,
) -> list[Document]:
    result: list[Document] = []
    seen: set[tuple[str, str, str]] = set()
    for document in [*primary, *fallback]:
        if not document.page_content:
            continue
        key = (
            document.page_content,
            str(document.metadata.get("source", "")),
            str(document.metadata.get("page", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(document)
        if len(result) >= length:
            break
    return result


def search_memory(
    query: str,
    memory: MemoryStore,
    embeddings: EmbeddingModel,
    *,
    k: int = 3,
    min_score: float = 0.58,
) -> list[Document]:
    documents = [document for document in memory.all_documents() if document.page_content]
    if not documents:
        return pad_documents([], length=k)

    query_vector = np.asarray(embeddings.embed_query(query), dtype=np.float32)
    document_vectors = np.asarray(
        embeddings.embed_documents([document.page_content for document in documents]),
        dtype=np.float32,
    )
    if document_vectors.ndim != 2 or document_vectors.shape[1] != query_vector.shape[0]:
        raise ArtifactError("记忆向量维度不一致")
    scores = document_vectors @ query_vector
    ordered_indices = np.argsort(scores)[::-1]
    selected = [
        documents[int(index)] for index in ordered_indices if float(scores[int(index)]) > min_score
    ][:k]
    return pad_documents(selected, length=k)
