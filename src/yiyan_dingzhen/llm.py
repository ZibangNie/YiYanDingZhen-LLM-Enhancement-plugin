"""千帆对话模型和句向量模型的延迟构造。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from threading import local
from typing import Any, Protocol, runtime_checkable

import requests

from yiyan_dingzhen.config import ConfigurationError, Settings

QIANFAN_V2_CHAT_COMPLETIONS_URL = "https://qianfan.baidubce.com/v2/chat/completions"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0


class MissingDependencyError(RuntimeError):
    """可选运行依赖尚未安装。"""


class ModelRequestError(RuntimeError):
    """模型服务请求失败，或服务端返回了无效响应。"""


@runtime_checkable
class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class EmbeddingModel(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(slots=True)
class QianfanChatModel:
    """使用千帆 v2 OpenAI 兼容接口的最小对话客户端。"""

    api_key: str = field(repr=False)
    model: str
    temperature: float
    timeout_seconds: float
    session: requests.Session | None = field(default=None, repr=False)
    _session_state: local = field(default_factory=local, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key.strip()
        self.model = self.model.strip()
        if not self.api_key:
            raise ConfigurationError("QIANFAN_API_KEY 不能为空")
        if "\r" in self.api_key or "\n" in self.api_key:
            raise ConfigurationError("QIANFAN_API_KEY 包含非法换行符")
        if not self.model:
            raise ConfigurationError("YDZ_CHAT_MODEL 不能为空")
        if not isfinite(self.temperature) or self.temperature < 0:
            raise ConfigurationError("YDZ_TEMPERATURE 必须是大于等于 0 的有限数字")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ConfigurationError("YDZ_LLM_TIMEOUT_SECONDS 必须大于 0")

    def _get_session(self) -> requests.Session:
        if self.session is not None:
            return self.session
        thread_session = getattr(self._session_state, "session", None)
        if not isinstance(thread_session, requests.Session):
            thread_session = requests.Session()
            self._session_state.session = thread_session
        return thread_session

    def invoke(self, input: Any, **kwargs: Any) -> str:
        if not isinstance(input, str):
            raise TypeError("千帆模型输入必须是字符串")
        if kwargs:
            names = ", ".join(sorted(kwargs))
            raise TypeError(f"千帆模型不支持额外调用参数：{names}")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": input}],
            "temperature": self.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._get_session().post(
                QIANFAN_V2_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=payload,
                timeout=(DEFAULT_CONNECT_TIMEOUT_SECONDS, self.timeout_seconds),
            )
        except requests.Timeout as exc:
            raise ModelRequestError(
                f"千帆模型请求超时（读取超时 {self.timeout_seconds:g} 秒）"
            ) from exc
        except requests.RequestException as exc:
            raise ModelRequestError("无法连接千帆模型服务") from exc

        try:
            if response.status_code >= 400:
                request_id = response.headers.get("x-bce-request-id") or response.headers.get(
                    "x-request-id"
                )
                suffix = f"，请求 ID：{request_id}" if request_id else ""
                raise ModelRequestError(f"千帆模型服务返回 HTTP {response.status_code}{suffix}")

            try:
                data = response.json()
            except ValueError as exc:
                raise ModelRequestError("千帆模型服务返回了非 JSON 响应") from exc
        finally:
            response.close()

        if not isinstance(data, dict):
            raise ModelRequestError("千帆模型响应必须是 JSON 对象")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelRequestError("千帆模型响应缺少 choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ModelRequestError("千帆模型响应中的 choice 格式无效")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ModelRequestError("千帆模型响应缺少 message")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelRequestError("千帆模型响应中的 content 不是字符串")
        return content


class SentenceTransformerEmbeddingModel:
    """保持旧检索接口语义的 SentenceTransformer 轻量包装。"""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MissingDependencyError(
                '缺少 sentence-transformers，请安装项目的 "rag" 可选依赖'
            ) from exc

        try:
            self._model = SentenceTransformer(
                model_name,
                device="cpu",
                trust_remote_code=False,
            )
        except ImportError as exc:
            raise MissingDependencyError(
                'sentence-transformers 运行依赖不完整，请重新安装项目的 "rag" 可选依赖'
            ) from exc

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        values = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        if not isinstance(values, list) or any(not isinstance(vector, list) for vector in values):
            raise ModelRequestError("嵌入模型返回了无法识别的向量格式")
        return [[float(component) for component in vector] for vector in values]

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)


def create_chat_model(settings: Settings) -> ChatModel:
    return QianfanChatModel(
        api_key=settings.require_qianfan_api_key(),
        model=settings.chat_model,
        temperature=settings.temperature,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def create_embedding_model(settings: Settings) -> EmbeddingModel:
    return SentenceTransformerEmbeddingModel(settings.embedding_model)


def invoke_text(model: ChatModel, prompt: str) -> str:
    response = model.invoke(prompt)
    content = getattr(response, "content", response)
    if not isinstance(content, str):
        raise ModelRequestError("模型返回了无法识别的响应类型")
    return content
