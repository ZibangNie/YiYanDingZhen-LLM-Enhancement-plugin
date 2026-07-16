"""已安装包的 WSGI 入口。"""

from __future__ import annotations

from flask import Flask

from yiyan_dingzhen.app import create_app


def create_application() -> Flask:
    return create_app()


app = create_application()
