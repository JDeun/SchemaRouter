"""No data disclosure, score drift or executable side effects."""
import pytest

from scripts.research_codegraph_final_answer_diagnostics_e1 import (
    _CATEGORIES,
    classify_strict_final_e1,
)

TRUSTED = {"case_state": "ready", "secret_record_id": "hidden-4"}


@pytest.mark.parametrize(("text", "label"), [
    ('{"case_state":"ready"}', "strict_correct"),
    ('{"case_state":"closed"}', "valid_json_wrong_value"),
    ('{"case_state":true}', "valid_json_wrong_type"),
    ('{"case_state":"ready","extra":1}', "valid_json_wrong_contract"),
    ('{"different":"ready"}', "valid_json_wrong_contract"),
    ('["ready"]', "valid_json_wrong_contract"),
    ('{"case_state":"ready",', "invalid_json_structure"),
    ('{"case_state":"ready","case_state":"ready"}', "invalid_json_structure"),
    ('{"case_state":NaN}', "invalid_json_structure"),
    ('```json\n{"case_state":"ready"}\n```', "markdown_fenced_not_strict_json"),
    ('<think>reason</think>{"case_state":"ready"}',
     "reasoning_wrapped_not_strict_json"),
    ('This is ready: {"case_state":"ready"}', "nonjson_or_prefixed_final"),
    ('ready', "nonjson_or_prefixed_final"),
])
def test_safe_fixed_final_taxonomy(text, label):
    before = TRUSTED.copy()
    observed = classify_strict_final_e1(text, TRUSTED)
    assert observed == label and observed in _CATEGORIES
    assert TRUSTED == before
    assert "hidden-4" not in observed
    assert "ready" not in observed


@pytest.mark.parametrize(("text", "observed"), [
    (None, TRUSTED),
    ('{"case_state":"ready"}', None),
])
def test_refuses_invalid_diagnostic_invocation(text, observed):
    with pytest.raises(ValueError):
        classify_strict_final_e1(text, observed)


def test_diagnostic_never_converts_embedded_correct_json_into_strict_success():
    assert classify_strict_final_e1(
        'The answer is {"case_state":"ready"}', TRUSTED,
    ) == "nonjson_or_prefixed_final"
