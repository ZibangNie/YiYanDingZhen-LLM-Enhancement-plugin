"""带 SSRF、重定向、超时和大小限制的远程文档下载。"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import PurePath
from urllib.parse import unquote, urljoin, urlsplit

import requests

from yiyan_dingzhen.config import Settings

_FILENAME_RE = re.compile(
    r"""filename\*?=(?:UTF-8''|["'])?([^"';]+)""",
    flags=re.IGNORECASE,
)


class DownloadError(ValueError):
    """远程地址不安全、请求失败或响应不符合限制。"""


@dataclass(frozen=True, slots=True)
class DownloadedFile:
    content: bytes
    filename: str
    content_type: str
    final_url: str


def _is_allowed_host(hostname: str, allowed_hosts: tuple[str, ...]) -> bool:
    if not allowed_hosts:
        return True
    host = hostname.rstrip(".").lower()
    return any(
        host == allowed.rstrip(".").lower() or host.endswith("." + allowed.rstrip(".").lower())
        for allowed in allowed_hosts
    )


def _validate_ip(address: str) -> None:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as exc:
        raise DownloadError(f"无法识别目标 IP：{address}") from exc
    if not ip.is_global:
        raise DownloadError("拒绝访问非公网 IP 地址")


def _default_resolver(hostname: str, port: int) -> Iterable[str]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DownloadError("域名解析失败") from exc
    return {str(record[4][0]) for record in records}


def validate_remote_url(
    url: str,
    *,
    allow_http: bool,
    allowed_hosts: tuple[str, ...],
    resolver: Callable[[str, int], Iterable[str]] = _default_resolver,
) -> str:
    if not isinstance(url, str) or not url.strip():
        raise DownloadError("url 必须是非空字符串")
    parsed = urlsplit(url.strip())
    schemes = {"https", "http"} if allow_http else {"https"}
    if parsed.scheme.lower() not in schemes:
        raise DownloadError("远程文档默认只允许 HTTPS")
    if parsed.username or parsed.password:
        raise DownloadError("URL 不能包含用户名或密码")
    if not parsed.hostname:
        raise DownloadError("URL 缺少主机名")
    if not _is_allowed_host(parsed.hostname, allowed_hosts):
        raise DownloadError("目标域名不在允许列表中")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise DownloadError("URL 端口无效") from exc
    for address in resolver(parsed.hostname, port):
        _validate_ip(address)
    return parsed.geturl()


def _response_peer_ip(response: requests.Response) -> str | None:
    """尽力读取实际 TCP 对端；测试替身或不同 urllib3 版本可返回 None。"""
    try:
        connection = getattr(response.raw, "_connection", None)
        socket_object = getattr(connection, "sock", None)
        if socket_object is None:
            return None
        peer = socket_object.getpeername()
    except (AttributeError, OSError, TypeError):
        return None
    return str(peer[0])


def _response_filename(response: requests.Response, final_url: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    match = _FILENAME_RE.search(disposition)
    if match:
        candidate = PurePath(unquote(match.group(1))).name
        if candidate:
            return candidate
    name = PurePath(unquote(urlsplit(final_url).path)).name
    return name or "document"


class RemoteDocumentDownloader:
    def __init__(
        self,
        settings: Settings,
        *,
        session: requests.Session | None = None,
        resolver: Callable[[str, int], Iterable[str]] = _default_resolver,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.resolver = resolver

    def fetch(self, url: str) -> DownloadedFile:
        current = url
        for redirect_count in range(self.settings.download_max_redirects + 1):
            current = validate_remote_url(
                current,
                allow_http=self.settings.allow_http_downloads,
                allowed_hosts=self.settings.allowed_download_hosts,
                resolver=self.resolver,
            )
            try:
                response = self.session.get(
                    current,
                    stream=True,
                    allow_redirects=False,
                    timeout=(
                        self.settings.download_timeout_seconds,
                        self.settings.download_timeout_seconds,
                    ),
                    headers={"User-Agent": "YiYanDingZhen/0.2"},
                )
            except requests.RequestException as exc:
                raise DownloadError("远程文档下载失败") from exc

            with response:
                peer_ip = _response_peer_ip(response)
                if peer_ip is not None:
                    _validate_ip(peer_ip)

                if response.is_redirect or response.is_permanent_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        raise DownloadError("重定向响应缺少 Location")
                    if redirect_count >= self.settings.download_max_redirects:
                        raise DownloadError("远程文档重定向次数过多")
                    current = urljoin(current, location)
                    continue

                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    raise DownloadError(f"远程服务器返回 HTTP {response.status_code}") from exc

                declared_length = response.headers.get("Content-Length")
                if declared_length:
                    try:
                        content_length = int(declared_length)
                    except ValueError as exc:
                        raise DownloadError("Content-Length 无效") from exc
                    if content_length > self.settings.download_max_bytes:
                        raise DownloadError("远程文档超过允许大小")

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.settings.download_max_bytes:
                        raise DownloadError("远程文档超过允许大小")
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not content:
                    raise DownloadError("远程文档内容为空")
                content_type = response.headers.get("Content-Type", "")
                return DownloadedFile(
                    content=content,
                    filename=_response_filename(response, current),
                    content_type=content_type,
                    final_url=current,
                )
        raise DownloadError("远程文档重定向次数过多")
