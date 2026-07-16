"""不依赖 LangChain 的兼容双层提示路由。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from yiyan_dingzhen import prompts
from yiyan_dingzhen.domain import Document
from yiyan_dingzhen.llm import invoke_text

RouteInfo = Mapping[str, str]
_MAX_ROUTER_OUTPUT_CHARS = 65_536
_MAX_JSON_START_ATTEMPTS = 32
_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*(.*?)```",
    flags=re.IGNORECASE | re.DOTALL,
)


class InvokableChain(Protocol):
    def invoke(self, inputs: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """经过候选名称校验后的路由结果。"""

    destination: str | None
    next_input: str


def _route_names(route_infos: Iterable[RouteInfo]) -> tuple[str, ...]:
    names: list[str] = []
    for route_info in route_infos:
        name = route_info.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("route info requires a non-empty name")
        names.append(name)
    return tuple(names)


def _parse_json_object(text: str) -> Mapping[str, Any] | None:
    """从代码围栏或普通文本中提取首个 JSON 对象。"""

    if len(text) > _MAX_ROUTER_OUTPUT_CHARS:
        return None

    candidates = [match.group(1).strip() for match in _JSON_FENCE_PATTERN.finditer(text)]
    candidates.append(text.strip())
    decoder = json.JSONDecoder()

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, RecursionError, TypeError):
            parsed = None
        if isinstance(parsed, Mapping):
            return parsed

        attempts = 0
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            attempts += 1
            if attempts > _MAX_JSON_START_ATTEMPTS:
                break
            try:
                parsed, _ = decoder.raw_decode(candidate, index)
            except (json.JSONDecodeError, RecursionError):
                continue
            if isinstance(parsed, Mapping):
                return parsed
    return None


def parse_router_output(
    output: str,
    *,
    allowed_destinations: Iterable[str],
    original_input: str,
) -> RouteDecision:
    """解析模型路由输出；不可信或非法结果统一回退到原始输入。"""

    parsed = _parse_json_object(output)
    if parsed is None:
        return RouteDecision(destination=None, next_input=original_input)

    destination = parsed.get("destination")
    next_inputs = parsed.get("next_inputs")
    if not isinstance(destination, str) or not isinstance(next_inputs, str):
        return RouteDecision(destination=None, next_input=original_input)

    normalized_destination = destination.strip()
    if normalized_destination.casefold() == "default":
        return RouteDecision(destination=None, next_input=original_input)

    allowed = frozenset(allowed_destinations)
    if normalized_destination not in allowed:
        return RouteDecision(destination=None, next_input=original_input)

    # 路由模型只负责选择提示词，不允许它改写用户输入。
    return RouteDecision(
        destination=normalized_destination,
        next_input=original_input,
    )


def _input_text(inputs: Mapping[str, Any]) -> str:
    input_text = inputs.get("input")
    if not isinstance(input_text, str):
        raise TypeError("chain input must contain a string 'input'")
    return input_text


def _build_router_prompt(route_infos: Iterable[RouteInfo], input_text: str) -> str:
    destinations = [
        f"{route_info['name']}: {route_info['description']}" for route_info in route_infos
    ]
    router_template = prompts.MULTI_PROMPT_ROUTER_TEMPLATE.format(
        destinations="\n".join(destinations)
    )
    return router_template.format(input=input_text)


@dataclass(frozen=True, slots=True)
class RouterChain:
    route_infos: tuple[RouteInfo, ...]
    chat_model: Any

    def invoke(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        input_text = _input_text(inputs)
        output = invoke_text(
            self.chat_model,
            _build_router_prompt(self.route_infos, input_text),
        )
        decision = parse_router_output(
            output,
            allowed_destinations=_route_names(self.route_infos),
            original_input=input_text,
        )
        return {
            "destination": decision.destination,
            "next_inputs": {"input": decision.next_input},
        }


@dataclass(frozen=True, slots=True)
class PromptChain:
    chat_model: Any
    prompt_template: str
    partial_variables: Mapping[str, str]

    def invoke(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        input_text = _input_text(inputs)
        rendered_prompt = self.prompt_template.format(
            input=input_text,
            **self.partial_variables,
        )
        return {
            "input": input_text,
            "text": invoke_text(self.chat_model, rendered_prompt),
        }


@dataclass(frozen=True, slots=True)
class FinalChain:
    destination_chains: Mapping[str, InvokableChain]
    router_chain: RouterChain
    default_chain: InvokableChain

    def invoke(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        route = self.router_chain.invoke(inputs)
        destination = route.get("destination")
        next_inputs = route.get("next_inputs")
        if not isinstance(next_inputs, Mapping):
            next_inputs = {"input": _input_text(inputs)}

        selected = (
            self.destination_chains.get(destination) if isinstance(destination, str) else None
        )
        if selected is None:
            selected = self.default_chain
        return selected.invoke(next_inputs)


def create_destination_chains(
    route_infos: Iterable[RouteInfo],
    *,
    chat_model: Any,
    related_docs: list[Document],
    text: str,
    wenxin_template: str,
    route_group: str,
) -> dict[str, PromptChain]:
    route_infos = tuple(route_infos)
    partial_variables: dict[str, str]
    if route_group == "physics":
        if len(related_docs) < 6:
            raise ValueError("physics route requires six related documents")
        partial_variables = {
            "wenxin_template": wenxin_template,
            **{
                f"related_text{index + 1}": document.page_content
                for index, document in enumerate(related_docs[:6])
            },
        }
    elif route_group == "summary":
        partial_variables = {"text": text}
    else:
        partial_variables = {}

    return {
        route_info["name"]: PromptChain(
            chat_model=chat_model,
            prompt_template=route_info["prompt_template"],
            partial_variables=partial_variables,
        )
        for route_info in route_infos
    }


def create_router_chain(
    route_infos: Iterable[RouteInfo],
    *,
    chat_model: Any,
) -> RouterChain:
    return RouterChain(tuple(route_infos), chat_model)


def create_default_chain(*, chat_model: Any) -> PromptChain:
    return PromptChain(
        chat_model=chat_model,
        prompt_template=prompts.router_default_prompt,
        partial_variables={},
    )


def create_final_chain(
    destination_chains: Mapping[str, InvokableChain],
    router_chain: RouterChain,
    default_chain: InvokableChain,
) -> FinalChain:
    return FinalChain(destination_chains, router_chain, default_chain)


def build_answer_chain(
    *,
    chat_model: Any,
    related_docs: list[Document],
    text: str,
    wenxin_template: str,
) -> FinalChain:
    top_router = create_router_chain(
        prompts.router_infos_prompt_pre_level,
        chat_model=chat_model,
    )
    second_level_routers = {
        "物理": create_router_chain(
            prompts.router_infos_prompt_physics_way,
            chat_model=chat_model,
        ),
        "总结": create_router_chain(
            prompts.router_infos_prompt_summarize_way,
            chat_model=chat_model,
        ),
        "生活": create_router_chain(
            prompts.router_infos_prompt_answering_common_query_way,
            chat_model=chat_model,
        ),
    }
    default_chain = create_default_chain(chat_model=chat_model)

    physics = create_destination_chains(
        prompts.router_infos_prompt_physics_way,
        chat_model=chat_model,
        related_docs=related_docs,
        text=text,
        wenxin_template=wenxin_template,
        route_group="physics",
    )
    summary = create_destination_chains(
        prompts.router_infos_prompt_summarize_way,
        chat_model=chat_model,
        related_docs=related_docs,
        text=text,
        wenxin_template=wenxin_template,
        route_group="summary",
    )
    common = create_destination_chains(
        prompts.router_infos_prompt_answering_common_query_way,
        chat_model=chat_model,
        related_docs=related_docs,
        text=text,
        wenxin_template=wenxin_template,
        route_group="common",
    )

    mid_chains = {
        "物理": create_final_chain(physics, second_level_routers["物理"], default_chain),
        "总结": create_final_chain(summary, second_level_routers["总结"], default_chain),
        "生活": create_final_chain(common, second_level_routers["生活"], default_chain),
    }
    return create_final_chain(mid_chains, top_router, default_chain)


class LegacyRoutingEngine:
    def __init__(self, chat_model: Any) -> None:
        self.chat_model = chat_model

    def answer(
        self,
        *,
        query: str,
        related_docs: list[Document],
        document_text: str,
        wenxin_template: str,
    ) -> dict[str, Any]:
        chain = build_answer_chain(
            chat_model=self.chat_model,
            related_docs=related_docs,
            text=document_text,
            wenxin_template=wenxin_template,
        )
        return chain.invoke({"input": query})


# 兼容历史函数名。
createDestinationChains = create_destination_chains
createRouterChain = create_router_chain
createDefaultChain = create_default_chain
createFinalChain = create_final_chain
