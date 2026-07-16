import pytest

from yiyan_dingzhen.textsplit import hierarchical_split_text, split_text


def test_split_text_prefers_sentence_boundaries_and_keeps_overlap() -> None:
    text = "第一句话。第二句话稍微长一些。第三句话也在这里。第四句话结束。"

    chunks = split_text(text, chunk_size=18, chunk_overlap=4)

    assert len(chunks) >= 2
    assert all(chunk for chunk in chunks)
    assert all(len(chunk) <= 18 for chunk in chunks)
    assert chunks[0].endswith("。")


def test_hierarchical_split_text_handles_mixed_language() -> None:
    text = ("中文段落。English sentence. " * 20).strip()

    chunks = hierarchical_split_text(
        text,
        coarse_chunk_size=80,
        coarse_chunk_overlap=10,
        chunk_size=30,
        chunk_overlap=5,
    )

    assert len(chunks) > 2
    assert all(len(chunk) <= 30 for chunk in chunks)
    assert any("中文" in chunk for chunk in chunks)
    assert any("English" in chunk for chunk in chunks)


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (10, -1), (10, 10), (10, 11)],
)
def test_split_text_rejects_invalid_sizes(chunk_size: int, chunk_overlap: int) -> None:
    with pytest.raises(ValueError):
        split_text("content", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
