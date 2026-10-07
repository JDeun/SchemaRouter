import json
from pathlib import Path

SPEC = Path("benchmarks/adaptive-context-confirmation-v1/scorer-spec.json")


def test_confirmation_scorer_spec_is_frozen_before_scoring() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["status"] == "scorer_spec_frozen_unscored"
    assert spec["corpus_tasks_sha256"] == (
        "35911573c0d43a023cc9659fa3167a1c8870344701ec61fbccba6f3953c14707"
    )
    assert spec["catalog"]["endpoint_count"] == 100
    assert spec["routing"]["top_k"] == 10
    assert spec["routing"]["prior_weight"] == 0.5
    assert spec["routing"]["history_mutation_during_scoring"] is False
    assert spec["sessions"]["group_by"] == ["language"]
    assert spec["sessions"]["compaction_after_task_ordinal"] == 30
    assert spec["schema_context"]["size_metric"] == "utf8_bytes"
    assert spec["scoring"]["one_shot"] is True
    assert spec["scoring"]["result_mutation_after_first_score"] is False
    assert spec["scoring"]["performance_evidence_before_gate"] is False
