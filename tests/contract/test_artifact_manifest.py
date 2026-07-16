import json
from pathlib import Path

from yiyan_dingzhen.config import DEFAULT_EMBEDDING_MODEL


def test_artifact_manifest_matches_runtime_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "artifacts" / "manifest.json").read_text(encoding="utf-8"))

    assert payload["format_version"] == 1
    assert payload["runtime"] == {
        "default_index": "indexes/2018",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "dimension": 768,
        "metric": "dot",
        "normalize_embeddings": True,
    }
    assert {
        "indexes/2018/index.annoy",
        "indexes/2018/documents.json",
    }.issubset(payload["artifacts"])
