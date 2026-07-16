import hashlib
from pathlib import Path

from yiyan_dingzhen import prompts


def test_prompt_routes_are_preserved() -> None:
    assert len(prompts.router_infos_prompt_physics_way) == 13
    assert {item["name"] for item in prompts.router_infos_prompt_pre_level} == {
        "物理",
        "总结",
        "生活",
    }


def test_prompt_module_contains_no_hardcoded_credentials() -> None:
    content = Path(prompts.__file__).read_text(encoding="utf-8")
    assert "WENXIN_APP_Key" not in content
    assert "WENXIN_APP_SECRET" not in content


def test_legacy_prompt_text_snapshot() -> None:
    names = [
        "template_to_ask_WenXin_for_prompt",
        *[f"router_template_physics{index}" for index in range(1, 14)],
        "router_template_summarize",
        "router_template_answering_other_questions",
        "MULTI_PROMPT_ROUTER_TEMPLATE",
        "router_default_chain",
    ]
    content = "\0".join(getattr(prompts, name) for name in names).encode()
    assert (
        hashlib.sha256(content).hexdigest()
        == "100b821b8ba251fe2769cd2d213dbe7f2e8d3e8e48480d85ff57697bb83bb4d1"
    )


def test_legacy_message_helpers_do_not_require_langchain() -> None:
    template = prompts.formTemplate(
        "{style}|{question}|{related_text1}|{related_text2}|{related_text3}|{message_from_router}"
    )

    messages = prompts.formMessage(
        template,
        "详细",
        "问题",
        ["资料一", "资料二", "资料三"],
        "路由信息",
    )

    assert [message.content for message in messages] == ["详细|问题|资料一|资料二|资料三|路由信息"]
