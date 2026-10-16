"""Verify the actual external-source DEV sweep can never claim E2 readiness."""
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/v018-native-external-dev-sweep.yml"


def verify(text: str) -> None:
    required = (
        "repository: retail-ecommerce/ClicShopping",
        "ref: 8ada7f1f392f3dd2800e825dac8d245dfd53944a",
        "SERVICENOW_MCP_REVISION: 5bcb83b29ab5b30aee07cabaa8df974881c47126",
        "python -m scripts.verify_clicshopping_v433_repin",
        "scripts/capture_servicenow_platform_mcp_tools.py",
        "scripts/external_validation_servicenow_platform_mcp.py validate",
        "scripts/external_validation_servicenow_platform_mcp.py score",
        '"supported_required_input_field_recall"',
        '"unsupported_nonempty_candidate_rate"',
        "DEV_ONLY_NOT_INDEPENDENT",
        '"independent_confirmation": False',
        '"real_tool_calls": 0',
        '"may_release": False',
        "persist-credentials: false",
        "permissions:\n  contents: read",
        "if-no-files-found: error",
    )
    if any(x not in text for x in required):
        raise ValueError("source identity, DEV evidence or permission boundary missing")
    if any(x in text for x in ("issues: write", "contents: write",
                              "secrets.", "gh release create", "pull_request_target:")):
        raise ValueError("unapproved mutable/elevated native sweep")


def test_source_pins_real_native_surface_and_no_promotion_guards():
    verify(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize("old,new", [
    ("DEV_ONLY_NOT_INDEPENDENT", "INDEPENDENT_CONFIRMATION"),
    ('"independent_confirmation": False', '"independent_confirmation": True'),
    ('"may_release": False', '"may_release": True'),
    ("persist-credentials: false", "persist-credentials: true"),
    ("8ada7f1f392f3dd2800e825dac8d245dfd53944a", "f" * 40),
    ("5bcb83b29ab5b30aee07cabaa8df974881c47126", "f" * 40),
])
def test_forged_evidence_or_changed_provider_source_rejected(old: str, new: str):
    content = WORKFLOW.read_text(encoding="utf-8")
    assert old in content
    with pytest.raises(ValueError):
        verify(content.replace(old, new))
