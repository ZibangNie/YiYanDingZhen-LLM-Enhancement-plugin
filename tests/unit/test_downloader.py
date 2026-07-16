from __future__ import annotations

from dataclasses import replace

import pytest

from yiyan_dingzhen.downloader import (
    DownloadError,
    RemoteDocumentDownloader,
    validate_remote_url,
)


class FakeResponse:
    status_code = 200
    is_redirect = False
    is_permanent_redirect = False
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": "5",
        "Content-Disposition": 'attachment; filename="file.txt"',
    }
    raw = object()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size > 0
        yield b"hello"


class FakeSession:
    trust_env = True

    def get(self, *_args, **kwargs):
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        return FakeResponse()


def test_validate_remote_url_rejects_private_ip() -> None:
    with pytest.raises(DownloadError):
        validate_remote_url(
            "https://example.com/file.pdf",
            allow_http=False,
            allowed_hosts=(),
            resolver=lambda _host, _port: ["127.0.0.1"],
        )


def test_validate_remote_url_rejects_http_by_default() -> None:
    with pytest.raises(DownloadError):
        validate_remote_url(
            "http://example.com/file.pdf",
            allow_http=False,
            allowed_hosts=(),
            resolver=lambda _host, _port: ["93.184.216.34"],
        )


def test_downloader_streams_bounded_public_file(settings) -> None:
    downloader = RemoteDocumentDownloader(
        replace(settings, download_max_bytes=10),
        session=FakeSession(),
        resolver=lambda _host, _port: ["93.184.216.34"],
    )
    result = downloader.fetch("https://example.com/file.txt")

    assert result.content == b"hello"
    assert result.filename == "file.txt"
    assert downloader.session.trust_env is False
