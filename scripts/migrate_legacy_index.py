"""把受信的 LangChain Annoy index.pkl 迁移为安全 JSON 映射。

警告：pickle 在反序列化时可执行代码。此脚本只能处理项目所有者确认可信的
历史本地文件，不能处理下载文件或第三方提供的 pickle。
"""

from __future__ import annotations

import argparse
import configparser
import functools
import json
import pickle  # nosec B403
import re
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any, BinaryIO


class _SafeDocument:
    def __setstate__(self, state: Any) -> None:
        if isinstance(state, dict) and "__dict__" in state:
            state = state["__dict__"]
        if not isinstance(state, dict):
            raise pickle.UnpicklingError("Document state is not a mapping")
        self.__dict__.update(state)


class _SafeDocstore:
    def __setstate__(self, state: Any) -> None:
        if not isinstance(state, dict):
            raise pickle.UnpicklingError("Docstore state is not a mapping")
        self.__dict__.update(state)


class _LegacyIndexUnpickler(pickle.Unpickler):
    """只允许该历史索引实际用到的类型；仍不能让不可信文件变安全。"""

    _ALLOWED: dict[tuple[str, str], Any] = {
        ("langchain_community.docstore.in_memory", "InMemoryDocstore"): _SafeDocstore,
        ("langchain_core.documents.base", "Document"): _SafeDocument,
        ("configparser", "ConfigParser"): configparser.ConfigParser,
        ("configparser", "ConverterMapping"): configparser.ConverterMapping,
        ("configparser", "SectionProxy"): configparser.SectionProxy,
        ("configparser", "BasicInterpolation"): configparser.BasicInterpolation,
        ("builtins", "dict"): dict,
        ("builtins", "getattr"): getattr,
        ("functools", "partial"): functools.partial,
        ("re", "_compile"): re._compile,
    }

    def find_class(self, module: str, name: str) -> Any:
        try:
            return self._ALLOWED[(module, name)]
        except KeyError as exc:
            raise pickle.UnpicklingError(f"Blocked global: {module}.{name}") from exc


def _load_legacy_index(handle: BinaryIO) -> tuple[Any, dict[int, str], Any]:
    # 仅在 CLI 显式确认后处理项目所有者控制的历史文件。
    payload = _LegacyIndexUnpickler(handle).load()  # nosec B301
    if not isinstance(payload, tuple) or len(payload) != 3:
        raise ValueError("不支持的 LangChain Annoy pickle 结构")
    store, mapping, config = payload
    if not isinstance(mapping, dict):
        raise ValueError("索引映射不是字典")
    return store, mapping, config


def _normalize_source(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    normalized = value.replace("/", "\\")
    return PureWindowsPath(normalized).name


def migrate(source: Path, output: Path) -> dict[str, Any]:
    with source.open("rb") as handle:
        store, mapping, config = _load_legacy_index(handle)

    document_map = getattr(store, "_dict", None)
    if not isinstance(document_map, dict):
        raise ValueError("索引 docstore 缺少 _dict")

    documents: list[dict[str, Any]] = []
    for annoy_id, document_id in sorted(mapping.items()):
        if not isinstance(annoy_id, int) or not isinstance(document_id, str):
            raise ValueError("索引映射包含无效条目")
        document = document_map[document_id]
        content = getattr(document, "page_content", None)
        metadata = dict(getattr(document, "metadata", {}) or {})
        if not isinstance(content, str):
            raise ValueError("文档内容不是字符串")
        if "source" in metadata:
            metadata["source"] = _normalize_source(metadata["source"])
        documents.append(
            {
                "annoy_id": annoy_id,
                "page_content": content,
                "metadata": metadata,
            }
        )

    payload = {
        "format_version": 1,
        "dimension": int(config["ANNOY"]["f"]),
        "metric": str(config["ANNOY"]["metric"]),
        "documents": documents,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=output.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--i-understand-pickle-is-unsafe",
        action="store_true",
        help="确认输入是项目所有者控制的可信本地文件",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.i_understand_pickle_is_unsafe:
        raise SystemExit("拒绝加载 pickle：请确认文件可信并添加 --i-understand-pickle-is-unsafe")
    payload = migrate(args.legacy_index.resolve(), args.output.resolve())
    print(f"已迁移 {len(payload['documents'])} 条文档到 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
