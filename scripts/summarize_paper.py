"""使用一言鼎臻总结本地 PDF、DOCX、Markdown 或文本文件。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yiyan_dingzhen.config import Settings
from yiyan_dingzhen.documents import extract_text_from_path
from yiyan_dingzhen.service import AnswerService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--session-id", default="paper-summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings.from_env(root_dir=ROOT)
    content = extract_text_from_path(
        args.path,
        max_bytes=settings.download_max_bytes,
    )
    result = AnswerService.from_settings(settings).answer(
        "总结文档",
        session_id=args.session_id,
        document_text=content,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.text + "\n", encoding="utf-8", newline="\n")
        print(f"总结已写入 {args.output.resolve()}")
    else:
        print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
