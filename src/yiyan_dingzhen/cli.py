"""命令行问答、文档总结和 Flask 服务入口。"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from yiyan_dingzhen import __version__
from yiyan_dingzhen.app import create_app
from yiyan_dingzhen.config import ConfigurationError, Settings
from yiyan_dingzhen.documents import DocumentReadError, extract_text_from_path
from yiyan_dingzhen.llm import MissingDependencyError, ModelRequestError
from yiyan_dingzhen.retrieval import ArtifactError
from yiyan_dingzhen.service import AnswerService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yiyan-dingzhen")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command")

    ask = subcommands.add_parser("ask", help="回答一个问题")
    ask.add_argument("query")
    ask.add_argument("--session-id", default="cli")

    summarize = subcommands.add_parser("summarize", help="总结本地文档")
    summarize.add_argument("path", type=Path)
    summarize.add_argument("--session-id", default="cli")

    serve = subcommands.add_parser("serve", help="启动 Flask 插件服务")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--debug", action="store_true")

    subcommands.add_parser("shell", help="进入交互式问答")
    return parser


def _interactive(service: AnswerService) -> int:
    print("一言鼎臻已启动。按 Ctrl+C 或 Ctrl+Z 退出。")
    while True:
        try:
            query = input("请输入问题：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not query:
            continue
        result = service.answer(query, session_id="cli")
        print(result.text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        if args.command == "serve":
            app = create_app(settings)
            app.run(
                host=args.host or settings.host,
                port=args.port or settings.port,
                debug=args.debug or settings.debug,
                use_reloader=False,
            )
            return 0

        service = AnswerService.from_settings(settings)
        if args.command == "ask":
            print(service.answer(args.query, session_id=args.session_id).text)
            return 0
        if args.command == "summarize":
            content = extract_text_from_path(
                args.path,
                max_bytes=settings.download_max_bytes,
            )
            print(
                service.answer(
                    "总结文档",
                    session_id=args.session_id,
                    document_text=content,
                ).text
            )
            return 0
        return _interactive(service)
    except (
        ConfigurationError,
        MissingDependencyError,
        ModelRequestError,
        ArtifactError,
        DocumentReadError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
