"""查询对象、语言判断、关键词提取和双语翻译。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yiyan_dingzhen.llm import invoke_text

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


@dataclass(slots=True)
class Query:
    input_query: str
    keywords: list[Any] = field(default_factory=list)
    language: str = "unknown"
    translated_query: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.input_query, str):
            raise ValueError("Input must be a string")

    # 兼容历史代码使用的属性名。
    @property
    def inputQuery(self) -> str:
        return self.input_query

    @inputQuery.setter
    def inputQuery(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        self.input_query = value

    @property
    def keyWord(self) -> list[Any]:
        return self.keywords

    @keyWord.setter
    def keyWord(self, value: list[Any]) -> None:
        self.keywords = value

    @property
    def trans_query(self) -> str:
        return self.translated_query

    @trans_query.setter
    def trans_query(self, value: str) -> None:
        self.translated_query = value


def detect_language(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "unknown"

    cjk_count = len(_CJK_RE.findall(stripped))
    if cjk_count and cjk_count / max(len(stripped), 1) >= 0.15:
        return "zh-cn"

    try:
        from langdetect import detect

        detected = detect(stripped)
    except Exception:
        return "unknown"

    if detected.startswith("zh"):
        return "zh-cn"
    if detected == "en":
        return "en"
    return "unknown"


def extract_chinese_keywords(
    content: str,
    *,
    stopwords_path: Path,
    top_k: int = 20,
) -> list[str]:
    import jieba.analyse

    jieba.analyse.set_stop_words(str(stopwords_path))
    return list(jieba.analyse.extract_tags(content, topK=top_k))


def extract_english_keywords(content: str, *, top_k: int = 2) -> list[str]:
    import yake

    extractor = yake.KeywordExtractor(
        lan="en",
        n=2,
        dedupLim=0.9,
        top=top_k,
        features=None,
    )
    return [keyword for keyword, _score in extractor.extract_keywords(content)]


def translate_query(query: Query, chat_model: Any) -> str:
    if query.language == "en":
        return invoke_text(
            chat_model,
            "You are an expert in translation. Translate the text delimited by triple "
            "backticks into Chinese. Output only the translation.\n"
            f"```{query.input_query}```",
        )
    if query.language == "zh-cn":
        return invoke_text(
            chat_model,
            "你是翻译专家。请将三重反引号中的文本翻译为英文，只输出翻译结果。\n"
            f"```{query.input_query}```",
        )
    return query.input_query


def prepare_query(
    text: str,
    *,
    chat_model: Any,
    stopwords_path: Path,
) -> Query:
    query = Query(text)
    query.language = detect_language(text)
    if query.language == "zh-cn":
        query.keywords = extract_chinese_keywords(text, stopwords_path=stopwords_path)
    elif query.language == "en":
        query.keywords = extract_english_keywords(text)
    query.translated_query = translate_query(query, chat_model)
    return query


# 历史 API 别名。
languageDetect = detect_language
Chinese_key_words_extraction = extract_chinese_keywords
English_key_word_extraction = extract_english_keywords
query_translate = translate_query
