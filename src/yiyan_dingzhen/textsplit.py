"""不依赖外部语料下载的中英文分段工具。"""

from __future__ import annotations

DEFAULT_SEPARATORS = (
    "\n\n",
    "\n",
    "。 ",
    "。",
    "！",
    "？",
    ". ",
    "! ",
    "? ",
    "；",
    "; ",
    "，",
    ", ",
    " ",
)


def split_text(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
) -> list[str]:
    """按标点优先切分文本，并用字符重叠保留相邻上下文。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能小于 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    source = text.strip()
    if not source:
        return []

    chunks: list[str] = []
    start = 0
    source_length = len(source)
    while start < source_length:
        hard_end = min(start + chunk_size, source_length)
        end = hard_end
        if hard_end < source_length:
            earliest_break = start + max(chunk_size // 2, 1)
            candidates: list[int] = []
            for separator in separators:
                position = source.rfind(separator, earliest_break, hard_end)
                if position >= 0:
                    candidates.append(position + len(separator))
            if candidates:
                end = max(candidates)

        chunk = source[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= source_length:
            break

        next_start = max(end - chunk_overlap, start + 1)
        while next_start < end and source[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


def hierarchical_split_text(
    text: str,
    *,
    coarse_chunk_size: int,
    coarse_chunk_overlap: int,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """复现历史“先按章节、再按语义”两级切分意图。"""
    coarse_chunks = split_text(
        text,
        chunk_size=coarse_chunk_size,
        chunk_overlap=coarse_chunk_overlap,
    )
    return [
        chunk
        for coarse_chunk in coarse_chunks
        for chunk in split_text(
            coarse_chunk,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    ]
