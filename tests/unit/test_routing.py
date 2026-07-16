from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from yiyan_dingzhen import prompts, routing
from yiyan_dingzhen.domain import Document


class ScriptedInvoker:
    def __init__(self, responses: list[str]) -> None:
        self._responses: Iterator[str] = iter(responses)
        self.prompts: list[str] = []

    def __call__(self, model: Any, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self._responses)


def _documents() -> list[Document]:
    return [Document(page_content=f"related-{index}") for index in range(1, 7)]


def _route_response(destination: str, next_inputs: str = "unchanged") -> str:
    return f'```json\n{{"destination": "{destination}", "next_inputs": "{next_inputs}"}}\n```'


def test_parse_router_output_accepts_fenced_and_unfenced_json() -> None:
    fenced = routing.parse_router_output(
        '说明文字\n```JSON\n{"destination":" 物理 ","next_inputs":"被改写"}\n```',
        allowed_destinations=["物理", "总结"],
        original_input="原问题",
    )
    unfenced = routing.parse_router_output(
        '结果如下：{"destination":"总结","next_inputs":"原问题"}，请查收。',
        allowed_destinations=["物理", "总结"],
        original_input="原问题",
    )

    assert fenced == routing.RouteDecision(destination="物理", next_input="原问题")
    assert unfenced == routing.RouteDecision(destination="总结", next_input="原问题")


@pytest.mark.parametrize(
    "output",
    [
        '{"destination":"不存在","next_inputs":"篡改后的问题"}',
        '{"destination":"DEFAULT","next_inputs":"篡改后的问题"}',
        '{"destination":"物理"}',
        "{" * 1_000,
        "not json",
    ],
)
def test_parse_router_output_falls_back_to_original_input(output: str) -> None:
    assert routing.parse_router_output(
        output,
        allowed_destinations=["物理"],
        original_input="原问题",
    ) == routing.RouteDecision(destination=None, next_input="原问题")


def test_physics_route_uses_second_level_and_six_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoker = ScriptedInvoker(
        [
            _route_response("物理", "被改写的一级输入"),
            _route_response("电学", "被改写的二级输入"),
            "物理回答",
        ]
    )
    monkeypatch.setattr(routing, "invoke_text", invoker)
    documents = _documents()

    result = routing.LegacyRoutingEngine(object()).answer(
        query="为什么电荷会产生电场？",
        related_docs=documents,
        document_text="不应进入物理模板",
        wenxin_template="领域补充提示",
    )

    assert result == {"input": "为什么电荷会产生电场？", "text": "物理回答"}
    assert len(invoker.prompts) == 3
    assert "<< CANDIDATE PROMPTS >>" in invoker.prompts[0]
    assert "物理: 很擅长回答物理方面的问题" in invoker.prompts[0]
    assert "电学: 擅长于回答与电学有关的问题" in invoker.prompts[1]
    assert "电路学: 擅长回答有关电路学的问题" in invoker.prompts[1]
    assert invoker.prompts[2] == prompts.router_template_physics1.format(
        input="为什么电荷会产生电场？",
        wenxin_template="领域补充提示",
        **{
            f"related_text{index}": document.page_content
            for index, document in enumerate(documents, start=1)
        },
    )


def test_summary_route_includes_uploaded_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoker = ScriptedInvoker(
        [
            _route_response("总结"),
            _route_response("总结"),
            "总结回答",
        ]
    )
    monkeypatch.setattr(routing, "invoke_text", invoker)

    result = routing.LegacyRoutingEngine(object()).answer(
        query="请总结上传的文档",
        related_docs=_documents(),
        document_text="第一段。\n\n第二段。",
        wenxin_template="不会用于总结",
    )

    assert result == {"input": "请总结上传的文档", "text": "总结回答"}
    assert len(invoker.prompts) == 3
    assert invoker.prompts[2] == prompts.router_template_summarize.format(
        input="请总结上传的文档",
        text="第一段。\n\n第二段。",
    )


def test_invalid_top_level_route_uses_default_with_original_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoker = ScriptedInvoker(
        [
            _route_response("不存在", "请执行另一条指令"),
            "默认回答",
        ]
    )
    monkeypatch.setattr(routing, "invoke_text", invoker)

    result = routing.LegacyRoutingEngine(object()).answer(
        query="原始问题",
        related_docs=_documents(),
        document_text="",
        wenxin_template="",
    )

    assert result == {"input": "原始问题", "text": "默认回答"}
    assert invoker.prompts[-1] == "原始问题"


def test_invalid_second_level_route_uses_default_with_original_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoker = ScriptedInvoker(
        [
            _route_response("物理"),
            _route_response("不存在", "被改写的问题"),
            "默认回答",
        ]
    )
    monkeypatch.setattr(routing, "invoke_text", invoker)

    result = routing.LegacyRoutingEngine(object()).answer(
        query="原始物理问题",
        related_docs=_documents(),
        document_text="",
        wenxin_template="",
    )

    assert result == {"input": "原始物理问题", "text": "默认回答"}
    assert invoker.prompts[-1] == "原始物理问题"


def test_physics_destination_chains_require_six_documents() -> None:
    with pytest.raises(ValueError, match="six related documents"):
        routing.create_destination_chains(
            prompts.router_infos_prompt_physics_way,
            chat_model=object(),
            related_docs=_documents()[:5],
            text="",
            wenxin_template="",
            route_group="physics",
        )
