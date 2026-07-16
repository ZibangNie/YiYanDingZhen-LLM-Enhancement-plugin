"""按文件名顺序合并目录中的 PDF。"""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def merge_pdfs(source_dir: Path, output: Path) -> list[Path]:
    source_dir = source_dir.expanduser().resolve()
    output = output.expanduser().resolve()
    files = sorted(
        path for path in source_dir.glob("*.pdf") if path.is_file() and path.resolve() != output
    )
    if not files:
        raise ValueError("没有找到可合并 PDF")

    writer = PdfWriter()
    for path in files:
        reader = PdfReader(path, strict=False)
        for page in reader.pages:
            writer.add_page(page)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("merged.pdf"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = merge_pdfs(args.source_dir, args.output)
    print(f"已合并 {len(files)} 个 PDF 到 {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
