import json
from pathlib import Path

from scripts.benchmark_evidence_to_action import score
from scripts.run_evidence_to_action_ablation import row


def test_evidence_gate_eliminates_unsupported_seed_actions() -> None:
    payload = json.loads(
        Path("benchmarks/evidence-to-action-v1/cases.json").read_text(encoding="utf-8")
    )
    cases = payload["cases"]
    routing = score([row(case, "schemarouter_routing") for case in cases])
    gated = score([row(case, "schemarouter_evidence_gate") for case in cases])

    assert routing["unsupported_action_rate"] > 0
    assert gated["unsupported_action_rate"] == 0
    assert gated["premature_action_rate"] == 0
    assert gated["false_refusal_rate"] == 0
    assert gated["exact_action_success"] == 1
