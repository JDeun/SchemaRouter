from pathlib import Path


def test_hyset_retraining_protocol_preserves_independent_label_and_holdout() -> None:
    text = Path("docs/research/hyset-external-validation.md").read_text(encoding="utf-8")
    assert "independently retrained HYSET" in text
    assert "93808cb8d633b6b685f0f9353923b27c2ad7ad81" in text
    assert "reasonwang/ToolGen-Qwen2.5-1.5B-Tool-Retriever" in text
    normalized = " ".join(text.split())
    assert "do not tune against the six held-out test splits" in normalized
    assert "Do not infer output-field labels from ToolBench" in normalized


def test_hyset_retraining_manifest_forbids_paper_checkpoint_claim() -> None:
    import json

    payload = json.loads(
        Path("benchmarks/external-validation-hyset-retrain-dev-v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["upstream"]["paper_checkpoint_available"] is False
    assert payload["upstream"]["result_label"] == "independently retrained HYSET"
    assert payload["governance"]["paper_checkpoint_reproduction_claim_allowed"] is False
    assert payload["governance"]["heldout_tuning_allowed"] is False
