from __future__ import annotations

import pytest

from examples.external_validation.safeact_v1.contract_loader import build_gate


@pytest.mark.parametrize("path", [
    "../env/case_evidence.json",
    "/tmp/public-policy.json",
    "env/../env/case_manifest.json",
    "C:/temp/contract.json",
    "ENV/CASE_EVIDENCE.JSON",
])
def test_contract_loader_rejects_unsafe_source_paths(path: str) -> None:
    doc = {"contracts": [{
        "action": "refund_issue",
        "sources": [{"kind": "public_policy", "path": path}],
        "required_observations": [
            {"tool": "charge_read", "record_id": "C2", "fields": ["owner"]}
        ],
    }]}
    with pytest.raises(ValueError, match="untrusted contract"):
        build_gate(doc, "refund_issue")
