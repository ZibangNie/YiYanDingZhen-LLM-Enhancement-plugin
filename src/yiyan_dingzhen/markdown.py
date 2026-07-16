"""Markdown 分段工具；保留旧 md_translator.py 的公开能力。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BlockType = Literal["text", "code", "image"]
_IMAGE_RE = re.compile(r"^\s*!\[[^\]]*]\([^)]+\)\s*$")


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    content: str
    type: BlockType


def identify_type(paragraph: str) -> BlockType:
    stripped = paragraph.lstrip()
    if stripped.startswith("```"):
        return "code"
    if _IMAGE_RE.match(paragraph):
        return "image"
    return "text"


def split_markdown(content: str) -> list[MarkdownBlock]:
    blocks: list[MarkdownBlock] = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            text = "\n".join(paragraph).rstrip() + "\n"
            blocks.append(MarkdownBlock(text, "text"))
            paragraph.clear()

    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            if in_code:
                code.append(line)
                blocks.append(MarkdownBlock("\n".join(code) + "\n", "code"))
                code.clear()
                in_code = False
            else:
                flush_paragraph()
                code.append(line)
                in_code = True
            continue

        if in_code:
            code.append(line)
            continue

        if _IMAGE_RE.match(line):
            flush_paragraph()
            blocks.append(MarkdownBlock(line, "image"))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line)

    if in_code:
        blocks.append(MarkdownBlock("\n".join(code) + "\n", "code"))
    flush_paragraph()
    return blocks


def read_markdown(file: str | Path) -> list[str]:
    content = Path(file).read_text(encoding="utf-8", errors="ignore")
    return [block.content for block in split_markdown(content)]


def md_df(filepath: str | Path) -> Any:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError('md_df 需要 tools 依赖：pip install -e ".[tools]"') from exc
    return pd.DataFrame(
        [
            {"content": block.content, "type": block.type}
            for block in split_markdown(Path(filepath).read_text(encoding="utf-8", errors="ignore"))
        ]
    )
