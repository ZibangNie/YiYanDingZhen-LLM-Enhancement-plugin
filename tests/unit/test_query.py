from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yiyan_dingzhen.query import Query, detect_language, prepare_query


@dataclass
class FakeChatModel:
    responses: list[str]

    def invoke(self, _prompt):
        return self.responses.pop(0)


def test_query_legacy_properties() -> None:
    query = Query("hello")
    query.inputQuery = "updated"
    query.keyWord = ["key"]
    query.trans_query = "翻译"

    assert query.input_query == "updated"
    assert query.keywords == ["key"]
    assert query.translated_query == "翻译"


def test_detect_language_handles_short_chinese_text() -> None:
    assert detect_language("什么是牛顿第二定律？") == "zh-cn"
    assert detect_language("What is Newton's second law?") == "en"
    assert detect_language("123") == "unknown"


def test_prepare_query_translates_english(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "yiyan_dingzhen.query.extract_english_keywords",
        lambda _content: ["Newton law"],
    )
    model = FakeChatModel(["牛顿第二定律是什么？"])
    query = prepare_query(
        "What is Newton's second law?",
        chat_model=model,
        stopwords_path=tmp_path / "stopwords.txt",
    )

    assert query.language == "en"
    assert query.keywords == ["Newton law"]
    assert query.translated_query == "牛顿第二定律是什么？"
