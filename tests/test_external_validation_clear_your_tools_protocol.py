from pathlib import Path
import json


ROOT = Path("benchmarks/external-validation-clear-your-tools-dev-v1")


def test_cyt_development_manifest_separates_state_regimes() -> None:
    payload = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "development_unfrozen"
    assert payload["conditions"] == ["full_catalog", "clear_your_tools", "schemarouter"]
    assert payload["state_regimes"] == [
        "cold_start",
        "persistent_session",
        "sequential_adaptive",
    ]
    assert "ko_bm25" in payload["excluded_modes"]


def test_cyt_development_manifest_is_not_evidence_or_posthoc_tunable() -> None:
    payload = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    governance = payload["governance"]
    assert governance["frozen_before_scoring"] is False
    assert governance["post_freeze_semantic_tuning_allowed"] is False
    assert governance["negative_results_publishable_unchanged"] is True
    assert governance["development_artifacts_are_evidence"] is False
