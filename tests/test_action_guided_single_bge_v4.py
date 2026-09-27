from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from schemarouter.decisions import DecisionOption

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "benchmarks" / "action_guided_single_bge.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "action_guided_single_bge",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load action-guided BGE module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_option_payload_keeps_action_surface_separate_from_bge_text(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "_action_text_map",
        lambda: {"support.create_ticket": "create ticket ; open support case"},
    )
    option = DecisionOption(
        id="support.create_ticket",
        label="create_ticket",
        description=(
            "create ticket\n"
            "create support ticket\n"
            "open support case\n"
            "Create a customer support ticket"
        ),
    )

    payload = json.loads(module.option_payload(option))

    assert payload["route_id"] == "support.create_ticket"
    assert payload["action_text"] == "create ticket ; open support case"
    assert "customer support ticket" not in payload["action_text"]
    assert "Create a customer support ticket" in payload["bge_text"]


def test_score_pairs_runs_bge_for_only_action_selected_option(monkeypatch) -> None:
    module = _module()
    module._ACTION_VECTOR_CACHE.clear()

    vectors = {
        "query": [1.0, 0.0],
        "alpha action": [0.0, 1.0],
        "beta action": [1.0, 0.0],
    }

    monkeypatch.setattr(
        module,
        "_embed",
        lambda texts: [vectors[text] for text in texts],
    )
    captured: list[list[tuple[str, str]]] = []

    def fake_bge(pairs: list[tuple[str, str]]) -> list[float]:
        captured.append(pairs)
        return [0.8]

    monkeypatch.setattr(module, "_bge_score_pairs", fake_bge)

    alpha = json.dumps(
        {
            "route_id": "tool.alpha",
            "action_text": "alpha action",
            "bge_text": "alpha full text",
        }
    )
    beta = json.dumps(
        {
            "route_id": "tool.beta",
            "action_text": "beta action",
            "bge_text": "beta full text",
        }
    )

    scores = module.score_pairs([("query", alpha), ("query", beta)])

    assert scores == [0.0, 0.8]
    assert captured == [[("query", "beta full text")]]
