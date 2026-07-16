from __future__ import annotations

from dataclasses import dataclass

from yiyan_dingzhen.app import create_app
from yiyan_dingzhen.domain import AnswerResult
from yiyan_dingzhen.downloader import DownloadedFile
from yiyan_dingzhen.llm import ModelRequestError


@dataclass
class FakeService:
    calls: list[tuple[str, str, str]]

    def answer(
        self,
        query_text: str,
        *,
        session_id: str = "default",
        document_text: str = "",
    ) -> AnswerResult:
        self.calls.append((query_text, session_id, document_text))
        return AnswerResult(
            text="answer",
            raw={"input": query_text, "text": "answer"},
        )


class FakeDownloader:
    def fetch(self, url: str) -> DownloadedFile:
        return DownloadedFile(
            content=b"document body",
            filename="document.txt",
            content_type="text/plain",
            final_url=url,
        )


def test_query_contract_preserves_legacy_fields(settings) -> None:
    service = FakeService([])
    app = create_app(
        settings,
        service_factory=lambda _settings: service,
        downloader=FakeDownloader(),
    )
    client = app.test_client()

    response = client.post(
        "/set_Query",
        json={"query_content": "什么是牛顿第二定律？", "session_id": "s1"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["result"]["text"] == "answer"
    assert payload["prompt"]
    assert payload["session_id"] == "s1"
    assert service.calls == [("什么是牛顿第二定律？", "s1", "")]


def test_query_rejects_invalid_json(settings) -> None:
    app = create_app(
        settings,
        service_factory=lambda _settings: FakeService([]),
        downloader=FakeDownloader(),
    )
    response = app.test_client().post("/set_Query", data="not-json")
    assert response.status_code == 400
    assert response.get_json()["code"] == "bad_request"


def test_remote_document_contract(settings) -> None:
    service = FakeService([])
    app = create_app(
        settings,
        service_factory=lambda _settings: service,
        downloader=FakeDownloader(),
    )
    response = app.test_client().post(
        "/set_text",
        json={"url": "https://example.com/document.txt", "session_id": "s2"},
    )

    assert response.status_code == 200
    assert service.calls == [("总结文档", "s2", "document body")]
    assert response.get_json()["source_url"] == "https://example.com/document.txt"


def test_health_is_ready_without_initializing_heavy_service(settings) -> None:
    app = create_app(
        settings,
        service_factory=lambda _settings: FakeService([]),
        downloader=FakeDownloader(),
    )
    payload = app.test_client().get("/health").get_json()

    assert payload["ready"] is True
    assert payload["checks"]["credentials_configured"] is True
    assert payload["checks"]["service_initialized"] is False


def test_model_service_failure_is_reported_as_unavailable(settings) -> None:
    class FailingService:
        def answer(self, *_args, **_kwargs):
            raise ModelRequestError("模型服务暂时不可用")

    app = create_app(
        settings,
        service_factory=lambda _settings: FailingService(),
        downloader=FakeDownloader(),
    )
    response = app.test_client().post(
        "/set_Query",
        json={"query_content": "问题", "session_id": "s1"},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "模型服务暂时不可用",
        "code": "service_unavailable",
    }


def test_unknown_endpoint_keeps_http_404(settings) -> None:
    app = create_app(
        settings,
        service_factory=lambda _settings: FakeService([]),
        downloader=FakeDownloader(),
    )

    response = app.test_client().get("/missing")

    assert response.status_code == 404
    assert response.get_json()["code"] == "not_found"
