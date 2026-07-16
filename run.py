"""兼容历史入口，同时把 CLI 与 Flask 服务显式分开。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yiyan_dingzhen.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
