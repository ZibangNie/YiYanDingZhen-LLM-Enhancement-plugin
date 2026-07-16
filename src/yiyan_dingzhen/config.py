"""集中管理环境变量、项目路径和运行限制。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path

DEFAULT_CORS_ORIGIN = "https://yiyan.baidu.com"
DEFAULT_CHAT_MODEL = "ernie-4.5-turbo-128k"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


class ConfigurationError(RuntimeError):
    """运行配置不完整或无效。"""


def project_root() -> Path:
    explicit = os.getenv("YDZ_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()

    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "pyproject.toml").is_file():
        return source_root
    return Path.cwd().resolve()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} 必须是 true 或 false")


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是整数") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} 不能小于 {minimum}")
    return value


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是数字") from exc
    if not isfinite(value):
        raise ConfigurationError(f"{name} 必须是有限数字")
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} 不能小于 {minimum}")
    return value


def _env_csv(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _resolve_path(root: Path, raw: str | None, default: Path) -> Path:
    if not raw:
        return default.resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    root_dir: Path
    qianfan_api_key: str | None = field(repr=False)
    chat_model: str
    temperature: float
    llm_timeout_seconds: float
    embedding_model: str
    index_dir: Path
    retrieval_k: int
    retrieval_min_score: float
    host: str
    port: int
    debug: bool
    public_base_url: str | None
    cors_origins: tuple[str, ...]
    max_query_chars: int
    download_timeout_seconds: float
    download_max_bytes: int
    download_max_redirects: int
    allow_http_downloads: bool
    allowed_download_hosts: tuple[str, ...]
    log_level: str
    memory_turns: int = 10
    memory_sessions: int = 512

    @classmethod
    def from_env(
        cls,
        *,
        root_dir: Path | None = None,
        load_dotenv_file: bool = True,
    ) -> Settings:
        root = (root_dir or project_root()).resolve()
        if load_dotenv_file:
            try:
                from dotenv import load_dotenv
            except ImportError:
                pass
            else:
                load_dotenv(root / ".env", override=False)

        api_key = (
            os.getenv("QIANFAN_API_KEY")
            or os.getenv("BAIDU_API_KEY")
            or os.getenv("WENXIN_APP_KEY")
        )
        default_index = root / "artifacts" / "indexes" / "2018"

        return cls(
            root_dir=root,
            qianfan_api_key=api_key or None,
            chat_model=os.getenv("YDZ_CHAT_MODEL", DEFAULT_CHAT_MODEL),
            temperature=_env_float("YDZ_TEMPERATURE", 0.9, minimum=0.0),
            llm_timeout_seconds=_env_float(
                "YDZ_LLM_TIMEOUT_SECONDS",
                60.0,
                minimum=0.1,
            ),
            embedding_model=os.getenv("YDZ_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            index_dir=_resolve_path(root, os.getenv("YDZ_INDEX_DIR"), default_index),
            retrieval_k=_env_int("YDZ_RETRIEVAL_K", 3, minimum=1),
            retrieval_min_score=_env_float(
                "YDZ_RETRIEVAL_MIN_SCORE",
                0.6,
            ),
            host=os.getenv("YDZ_HOST", "127.0.0.1"),
            port=_env_int("YDZ_PORT", 8081, minimum=1),
            debug=_env_bool("YDZ_DEBUG", False),
            public_base_url=os.getenv("YDZ_PUBLIC_BASE_URL") or None,
            cors_origins=_env_csv("YDZ_CORS_ORIGINS", (DEFAULT_CORS_ORIGIN,)),
            max_query_chars=_env_int("YDZ_MAX_QUERY_CHARS", 10_000, minimum=1),
            download_timeout_seconds=_env_float(
                "YDZ_DOWNLOAD_TIMEOUT_SECONDS",
                15.0,
                minimum=0.1,
            ),
            download_max_bytes=_env_int(
                "YDZ_DOWNLOAD_MAX_BYTES",
                20 * 1024 * 1024,
                minimum=1,
            ),
            download_max_redirects=_env_int(
                "YDZ_DOWNLOAD_MAX_REDIRECTS",
                3,
                minimum=0,
            ),
            allow_http_downloads=_env_bool("YDZ_ALLOW_HTTP_DOWNLOADS", False),
            allowed_download_hosts=_env_csv("YDZ_ALLOWED_DOWNLOAD_HOSTS"),
            log_level=os.getenv("YDZ_LOG_LEVEL", "INFO").upper(),
            memory_turns=_env_int("YDZ_MEMORY_TURNS", 10, minimum=1),
            memory_sessions=_env_int("YDZ_MEMORY_SESSIONS", 512, minimum=1),
        )

    @property
    def stopwords_path(self) -> Path:
        return Path(__file__).resolve().parent / "resources" / "cn_stopwords.txt"

    @property
    def logo_path(self) -> Path:
        return Path(__file__).resolve().parent / "resources" / "logo.png"

    @property
    def plugin_dir(self) -> Path:
        return Path(__file__).resolve().parent / "plugin"

    @property
    def baidu_api_key(self) -> str | None:
        """旧字段名的只读兼容别名。"""

        return self.qianfan_api_key

    def require_qianfan_api_key(self) -> str:
        if not self.qianfan_api_key:
            raise ConfigurationError(
                "缺少千帆凭据，请设置 QIANFAN_API_KEY（BAIDU_API_KEY 仅作为兼容别名）"
            )
        return self.qianfan_api_key
