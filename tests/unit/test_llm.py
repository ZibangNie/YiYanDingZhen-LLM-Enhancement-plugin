from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import requests

from yiyan_dingzhen.config import ConfigurationError, Settings, project_root
from yiyan_dingzhen.llm import (
    QIANFAN_V2_CHAT_COMPLETIONS_URL,
    ModelRequestError,
    QianfanChatModel,
    create_embedding_model,
    invoke_text,
)


class FakeResponse:
    def __init__(
        self,
        payload: Any,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def json(self) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(
        self,
        response: FakeResponse | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def _client(session: FakeSession) -> QianfanChatModel:
    return QianfanChatModel(
        api_key="test-secret-key",
        model="ernie-test",
        temperature=0.9,
        timeout_seconds=30,
        session=session,  # type: ignore[arg-type]
    )


def test_qianfan_client_sends_openai_compatible_request() -> None:
    response = FakeResponse({"choices": [{"message": {"role": "assistant", "content": "回答"}}]})
    session = FakeSession(response)

    result = invoke_text(_client(session), "问题")

    assert result == "回答"
    assert response.closed is True
    assert session.calls == [
        {
            "url": QIANFAN_V2_CHAT_COMPLETIONS_URL,
            "headers": {
                "Authorization": "Bearer test-secret-key",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "ernie-test",
                "messages": [{"role": "user", "content": "问题"}],
                "temperature": 0.9,
            },
            "timeout": (10.0, 30),
        }
    ]
    assert "test-secret-key" not in repr(_client(session))


def test_qianfan_client_reports_http_failure_without_exposing_key() -> None:
    response = FakeResponse(
        {"error": {"message": "authentication failed"}},
        status_code=401,
        headers={"x-bce-request-id": "request-123"},
    )

    with pytest.raises(ModelRequestError) as exc_info:
        _client(FakeSession(response)).invoke("问题")

    assert str(exc_info.value) == ("千帆模型服务返回 HTTP 401，请求 ID：request-123")
    assert "test-secret-key" not in str(exc_info.value)
    assert response.closed is True


def test_qianfan_client_wraps_timeout() -> None:
    with pytest.raises(ModelRequestError, match="请求超时"):
        _client(FakeSession(error=requests.Timeout("upstream details"))).invoke("问题")


@pytest.mark.parametrize(
    "payload, message",
    [
        (ValueError("invalid json"), "非 JSON"),
        ([], "JSON 对象"),
        ({}, "缺少 choices"),
        ({"choices": [{}]}, "缺少 message"),
        (
            {"choices": [{"message": {"content": ["unexpected"]}}]},
            "content 不是字符串",
        ),
    ],
)
def test_qianfan_client_validates_response_structure(
    payload: Any,
    message: str,
) -> None:
    with pytest.raises(ModelRequestError, match=message):
        _client(FakeSession(FakeResponse(payload))).invoke("问题")


def test_qianfan_client_rejects_header_injection() -> None:
    with pytest.raises(ConfigurationError, match="非法换行符"):
        QianfanChatModel(
            api_key="test\r\nX-Evil: true",
            model="ernie-test",
            temperature=0.9,
            timeout_seconds=30,
        )


def test_invoke_text_accepts_legacy_content_wrapper() -> None:
    class WrappedResponseModel:
        def invoke(self, prompt: Any) -> Any:
            assert prompt == "问题"
            return SimpleNamespace(content="回答")

    assert invoke_text(WrappedResponseModel(), "问题") == "回答"


def test_settings_prefer_qianfan_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("QIANFAN_API_KEY", "qianfan-key")
    monkeypatch.setenv("BAIDU_API_KEY", "baidu-alias")

    settings = Settings.from_env(root_dir=tmp_path, load_dotenv_file=False)

    assert settings.qianfan_api_key == "qianfan-key"
    assert settings.require_qianfan_api_key() == "qianfan-key"
    assert settings.baidu_api_key == "qianfan-key"
    assert "qianfan-key" not in repr(settings)


def test_settings_accept_baidu_api_key_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("QIANFAN_API_KEY", raising=False)
    monkeypatch.setenv("BAIDU_API_KEY", "baidu-alias")

    settings = Settings.from_env(root_dir=tmp_path, load_dotenv_file=False)

    assert settings.require_qianfan_api_key() == "baidu-alias"


def test_settings_reject_non_finite_model_numbers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("YDZ_TEMPERATURE", "nan")

    with pytest.raises(ConfigurationError, match="有限数字"):
        Settings.from_env(root_dir=tmp_path, load_dotenv_file=False)


def test_project_root_accepts_explicit_installed_location(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("YDZ_PROJECT_ROOT", str(tmp_path))

    assert project_root() == tmp_path.resolve()


def test_embedding_wrapper_uses_normalized_cpu_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    calls: list[tuple[str, Any]] = []

    class FakeSentenceTransformer:
        def __init__(
            self,
            model_name: str,
            *,
            device: str,
            trust_remote_code: bool,
        ) -> None:
            calls.append(("init", (model_name, device, trust_remote_code)))

        def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
            calls.append(("encode", (texts, kwargs)))
            return [[float(index), 1.0] for index, _text in enumerate(texts)]

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embeddings = create_embedding_model(settings)

    assert embeddings.embed_query("query") == [0.0, 1.0]
    assert embeddings.embed_documents(["a", "b"]) == [
        [0.0, 1.0],
        [1.0, 1.0],
    ]
    assert calls[0] == (
        "init",
        (settings.embedding_model, "cpu", False),
    )
    assert calls[1] == (
        "encode",
        (
            ["query"],
            {
                "convert_to_numpy": True,
                "normalize_embeddings": True,
                "show_progress_bar": False,
            },
        ),
    )
