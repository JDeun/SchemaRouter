from pathlib import Path


def test_hyset_retraining_protocol_preserves_independent_label_and_holdout() -> None:
    text = Path("docs/research/hyset-external-validation.md").read_text(encoding="utf-8")
    assert "independently retrained HYSET" in text
    assert "93808cb8d633b6b685f0f9353923b27c2ad7ad81" in text
    assert "reasonwang/ToolGen-Qwen2.5-1.5B-Tool-Retriever" in text
    assert "do not tune against the six held-out test splits" in text
    assert "Do not infer output-field labels from ToolBench" in text
