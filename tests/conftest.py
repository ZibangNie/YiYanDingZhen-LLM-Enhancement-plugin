from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yiyan_dingzhen.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    base = Settings.from_env(root_dir=ROOT, load_dotenv_file=False)
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "index.annoy").write_bytes(b"test")
    (index_dir / "documents.json").write_text(
        '{"format_version":1,"dimension":2,"metric":"dot","documents":[]}',
        encoding="utf-8",
    )
    return replace(
        base,
        qianfan_api_key="test-key",
        index_dir=index_dir,
        public_base_url=None,
        allowed_download_hosts=(),
        allow_http_downloads=False,
    )
