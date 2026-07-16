"""从本地文档构建不含 pickle 的 Annoy 索引。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from annoy import AnnoyIndex

from yiyan_dingzhen.config import Settings
from yiyan_dingzhen.documents import extract_text_from_path
from yiyan_dingzhen.llm import create_embedding_model
from yiyan_dingzhen.retrieval import sha256_file
from yiyan_dingzhen.textsplit import hierarchical_split_text

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}


def _input_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        resolved = item.expanduser().resolve()
        if resolved.is_dir():
            files.extend(
                path
                for path in resolved.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
            )
        elif resolved.is_file() and resolved.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(resolved)
        else:
            raise ValueError(f"不支持的输入：{item}")
    return sorted(set(files))


def build_index(
    *,
    inputs: list[Path],
    output_dir: Path,
    coarse_chunk_size: int,
    coarse_chunk_overlap: int,
    chunk_size: int,
    chunk_overlap: int,
    trees: int,
    jobs: int,
) -> tuple[Path, Path]:
    if coarse_chunk_overlap >= coarse_chunk_size:
        raise ValueError("coarse_chunk_overlap 必须小于 coarse_chunk_size")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")
    if trees <= 0:
        raise ValueError("trees 必须大于 0")
    if jobs == 0 or jobs < -1:
        raise ValueError("jobs 必须是 -1 或正整数")
    files = _input_files(inputs)
    if not files:
        raise ValueError("没有找到可索引文档")

    documents: list[dict[str, object]] = []
    texts: list[str] = []
    for path in files:
        content = extract_text_from_path(path, max_bytes=200 * 1024 * 1024)
        chunks = hierarchical_split_text(
            content,
            coarse_chunk_size=coarse_chunk_size,
            coarse_chunk_overlap=coarse_chunk_overlap,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        for chunk_number, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            annoy_id = len(texts)
            texts.append(chunk)
            documents.append(
                {
                    "annoy_id": annoy_id,
                    "page_content": chunk,
                    "metadata": {
                        "source": path.name,
                        "chunk": chunk_number,
                    },
                }
            )
    if not texts:
        raise ValueError("文档没有可索引文本")

    settings = Settings.from_env(root_dir=ROOT)
    embeddings = create_embedding_model(settings)
    vectors = embeddings.embed_documents(texts)
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("嵌入向量维度不一致")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output_dir,
        delete=False,
        suffix=".annoy.tmp",
    ) as handle:
        temporary_index = Path(handle.name)
    index = AnnoyIndex(dimension, "dot")
    for annoy_id, vector in enumerate(vectors):
        index.add_item(annoy_id, vector)
    index.build(trees, n_jobs=jobs)
    index.save(str(temporary_index))

    metadata_path = output_dir / "documents.json"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=output_dir,
        delete=False,
        suffix=".json.tmp",
    ) as handle:
        json.dump(
            {
                "format_version": 1,
                "dimension": dimension,
                "metric": "dot",
                "documents": documents,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
        temporary_metadata = Path(handle.name)

    index_path = output_dir / "index.annoy"
    temporary_index.replace(index_path)
    temporary_metadata.replace(metadata_path)
    return index_path, metadata_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "indexes" / "custom")
    parser.add_argument("--coarse-chunk-size", type=int, default=10_000)
    parser.add_argument("--coarse-chunk-overlap", type=int, default=700)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=80)
    parser.add_argument("--trees", type=int, default=800)
    parser.add_argument("--jobs", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_path, metadata_path = build_index(
        inputs=args.inputs,
        output_dir=args.output.resolve(),
        coarse_chunk_size=args.coarse_chunk_size,
        coarse_chunk_overlap=args.coarse_chunk_overlap,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        trees=args.trees,
        jobs=args.jobs,
    )
    print(f"索引：{index_path} SHA256={sha256_file(index_path)}")
    print(f"映射：{metadata_path} SHA256={sha256_file(metadata_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
