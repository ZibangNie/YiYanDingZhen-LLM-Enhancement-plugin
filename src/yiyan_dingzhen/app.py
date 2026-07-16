"""Flask 应用工厂和百度插件兼容接口。"""

from __future__ import annotations

import json
import logging
import re
import secrets
from collections.abc import Callable
from threading import Lock
from typing import Any, Protocol, cast

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from yiyan_dingzhen import __version__
from yiyan_dingzhen.config import ConfigurationError, Settings
from yiyan_dingzhen.documents import DocumentReadError, extract_text_from_bytes
from yiyan_dingzhen.domain import AnswerResult
from yiyan_dingzhen.downloader import DownloadError, RemoteDocumentDownloader
from yiyan_dingzhen.llm import MissingDependencyError, ModelRequestError
from yiyan_dingzhen.retrieval import ArtifactError
from yiyan_dingzhen.service import AnswerService

LOGGER = logging.getLogger(__name__)
LEGACY_DISPLAY_PROMPT = "请显示工具返回结果，不要改写任何内容，也不要新增内容。"
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class AnswerServiceLike(Protocol):
    def answer(
        self,
        query_text: str,
        *,
        session_id: str = "default",
        document_text: str = "",
    ) -> AnswerResult: ...


class ServiceProvider:
    def __init__(
        self,
        settings: Settings,
        factory: Callable[[Settings], AnswerServiceLike],
    ) -> None:
        self.settings = settings
        self.factory = factory
        self._service: AnswerServiceLike | None = None
        self._lock = Lock()

    @property
    def initialized(self) -> bool:
        return self._service is not None

    def get(self) -> AnswerServiceLike:
        if self._service is not None:
            return self._service
        with self._lock:
            if self._service is None:
                self._service = self.factory(self.settings)
            return self._service


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value)


def _request_json() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("请求体必须是 JSON 对象")
    return data


def _session_id(data: dict[str, Any]) -> str:
    value = data.get("session_id") or request.headers.get("X-Session-ID")
    if value is None:
        return secrets.token_urlsafe(18)
    if not isinstance(value, str) or not _SESSION_ID_RE.fullmatch(value):
        raise ValueError("session_id 格式无效")
    return value


def _query_text(data: dict[str, Any], settings: Settings) -> str:
    value = data.get("query_content")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("query_content 必须是非空字符串")
    if len(value) > settings.max_query_chars:
        raise ValueError(f"query_content 不能超过 {settings.max_query_chars} 个字符")
    return value


def _base_url(settings: Settings) -> str:
    return (settings.public_base_url or request.url_root).rstrip("/")


def create_app(
    settings: Settings | None = None,
    *,
    service_factory: Callable[[Settings], AnswerServiceLike] | None = None,
    downloader: RemoteDocumentDownloader | None = None,
) -> Flask:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=1024 * 1024,
        JSON_AS_ASCII=False,
    )
    json_provider = cast(Any, app.json)
    json_provider.ensure_ascii = False
    CORS(
        app,
        resources={r"/*": {"origins": list(settings.cors_origins)}},
    )

    provider = ServiceProvider(
        settings,
        service_factory or AnswerService.from_settings,
    )
    downloader = downloader or RemoteDocumentDownloader(settings)
    app.extensions["yiyan_dingzhen_provider"] = provider

    @app.get("/")
    def index() -> str:
        return "welcomeb7!!!!!!"

    @app.get("/health")
    def health() -> tuple[Response, int]:
        checks = {
            "credentials_configured": bool(settings.qianfan_api_key),
            "index_present": (settings.index_dir / "index.annoy").is_file(),
            "documents_present": (settings.index_dir / "documents.json").is_file(),
            "service_initialized": provider.initialized,
        }
        ready = all(
            checks[key]
            for key in (
                "credentials_configured",
                "index_present",
                "documents_present",
            )
        )
        return (
            jsonify(
                {
                    "status": "ok" if ready else "degraded",
                    "ready": ready,
                    "version": __version__,
                    "checks": checks,
                }
            ),
            200,
        )

    @app.post("/set_Query")
    def set_query() -> tuple[Response, int]:
        data = _request_json()
        query_text = _query_text(data, settings)
        session_id = _session_id(data)
        result = provider.get().answer(query_text, session_id=session_id)
        return (
            jsonify(
                {
                    "result": _json_safe(result.as_legacy_result()),
                    "prompt": LEGACY_DISPLAY_PROMPT,
                    "session_id": session_id,
                }
            ),
            200,
        )

    @app.post("/set_text")
    def set_text() -> tuple[Response, int]:
        data = _request_json()
        url = data.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url 必须是非空字符串")
        session_id = _session_id(data)
        remote_file = downloader.fetch(url)
        document_text = extract_text_from_bytes(
            remote_file.content,
            filename=remote_file.filename,
            content_type=remote_file.content_type,
        )
        result = provider.get().answer(
            "总结文档",
            session_id=session_id,
            document_text=document_text,
        )
        return (
            jsonify(
                {
                    "result": _json_safe(result.as_legacy_result()),
                    "prompt": LEGACY_DISPLAY_PROMPT,
                    "session_id": session_id,
                    "source_url": remote_file.final_url,
                }
            ),
            200,
        )

    @app.get("/logo.png")
    def plugin_logo() -> Any:
        return send_file(settings.logo_path, mimetype="image/png")

    @app.get("/.well-known/ai-plugin.json")
    def plugin_manifest() -> tuple[Response, int]:
        manifest = json.loads((settings.plugin_dir / "ai-plugin.json").read_text(encoding="utf-8"))
        base_url = _base_url(settings)
        manifest["api"]["url"] = f"{base_url}/.well-known/openapi.yaml"
        manifest["logo_url"] = f"{base_url}/logo.png"
        manifest["examples"]["url"] = f"{base_url}/.well-known/example.yaml"
        return jsonify(manifest), 200

    @app.get("/.well-known/openapi.yaml")
    def openapi_spec() -> tuple[str, int, dict[str, str]]:
        text = (settings.plugin_dir / "openapi.yaml").read_text(encoding="utf-8")
        return (
            text.replace("PLUGIN_HOST", _base_url(settings)),
            200,
            {"Content-Type": "application/yaml; charset=utf-8"},
        )

    @app.get("/.well-known/example.yaml")
    def example_spec() -> tuple[str, int, dict[str, str]]:
        text = (settings.plugin_dir / "example.yaml").read_text(encoding="utf-8")
        return text, 200, {"Content-Type": "application/yaml; charset=utf-8"}

    @app.errorhandler(ValueError)
    @app.errorhandler(DownloadError)
    @app.errorhandler(DocumentReadError)
    def bad_request(error: Exception) -> tuple[Response, int]:
        return jsonify({"error": str(error), "code": "bad_request"}), 400

    @app.errorhandler(ConfigurationError)
    @app.errorhandler(MissingDependencyError)
    @app.errorhandler(ModelRequestError)
    @app.errorhandler(ArtifactError)
    def unavailable(error: Exception) -> tuple[Response, int]:
        LOGGER.warning("Service is not ready: %s", error)
        return (
            jsonify({"error": str(error), "code": "service_unavailable"}),
            503,
        )

    @app.errorhandler(Exception)
    def internal_error(error: Exception) -> tuple[Response, int]:
        if isinstance(error, HTTPException):
            return (
                jsonify(
                    {
                        "error": error.description,
                        "code": error.name.lower().replace(" ", "_"),
                    }
                ),
                error.code or 500,
            )
        LOGGER.exception("Unhandled request error", exc_info=error)
        return jsonify({"error": "内部服务错误", "code": "internal_error"}), 500

    return app
