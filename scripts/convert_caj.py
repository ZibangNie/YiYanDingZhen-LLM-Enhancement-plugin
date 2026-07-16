"""批量把本地 CAJ 文件转换为 PDF。"""

from __future__ import annotations

import argparse
from pathlib import Path


def convert_file(source: Path, output: Path) -> None:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('缺少工具依赖：pip install -e ".[tools]"') from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with fitz.open(source) as document:
            document.save(output)
    except Exception as exc:
        raise RuntimeError(f"无法转换 {source}") from exc


def source_files(path: Path, *, recursive: bool) -> list[Path]:
    resolved = path.expanduser().resolve()
    if resolved.is_file():
        return [resolved] if resolved.suffix.lower() == ".caj" else []
    iterator = resolved.rglob("*.caj") if recursive else resolved.glob("*.caj")
    return sorted(item for item in iterator if item.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--recursive", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = source_files(args.source, recursive=args.recursive)
    if not files:
        raise SystemExit("没有找到 CAJ 文件")
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else args.source.expanduser().resolve().parent
        if args.source.is_file()
        else args.source.expanduser().resolve()
    )
    failures = 0
    for source in files:
        target = output_dir / f"{source.stem}.pdf"
        try:
            convert_file(source, target)
        except RuntimeError as exc:
            failures += 1
            print(f"失败：{exc}")
        else:
            print(f"完成：{target}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
