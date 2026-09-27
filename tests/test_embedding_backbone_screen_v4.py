from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_embedding_backbone_screen_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_embedding_backbone_screen_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load backbone screen")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_configs_are_frozen_and_role_aware() -> None:
    module = _module()
    assert set(module.MODEL_CONFIGS) == {
        "e5-base",
        "gte-multilingual-base",
        "bge-m3",
    }
    assert module.MODEL_CONFIGS["e5-base"]["query_prefix"] == "query: "
    assert module.MODEL_CONFIGS["e5-base"]["document_prefix"] == "passage: "
    assert module.MODEL_CONFIGS["gte-multilingual-base"]["trust_remote_code"] is True
    assert module.MODEL_CONFIGS["bge-m3"]["trust_remote_code"] is False


def test_prefix_helper_preserves_text_order() -> None:
    module = _module()
    assert module._prefixed("query: ", ["a", "b"]) == [
        "query: a",
        "query: b",
    ]


def test_remote_code_model_is_revision_pinned() -> None:
    module = _module()
    config = module.MODEL_CONFIGS["gte-multilingual-base"]
    assert config["revision"] == "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
