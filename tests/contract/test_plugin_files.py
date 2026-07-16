from __future__ import annotations

import json

import yaml

from yiyan_dingzhen.app import create_app


def test_plugin_files_are_parseable_and_use_dynamic_host(settings) -> None:
    app = create_app(settings, service_factory=lambda _settings: None)
    client = app.test_client()

    manifest_response = client.get(
        "/.well-known/ai-plugin.json",
        base_url="https://plugin.example",
    )
    manifest = json.loads(manifest_response.data)
    assert manifest["api"]["url"].startswith("https://plugin.example/")

    openapi = yaml.safe_load(
        client.get(
            "/.well-known/openapi.yaml",
            base_url="https://plugin.example",
        ).data
    )
    examples = yaml.safe_load(client.get("/.well-known/example.yaml").data)
    assert openapi["openapi"] == "3.0.3"
    assert len(examples["examples"]) == 2
