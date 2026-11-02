"""Multi-domain source-owned K5 benchmark: strict typed original oracle."""
from __future__ import annotations

import pytest

from scripts.research_g5_multidomain_paired_k5_e0 import (
    DOMAINS,
    SCHEMA_VERSION,
    analyze_multidomain_source,
    build_multidomain_source,
    source_scan_oracle,
)
from scripts.research_g5_vs_scoped_lexical_k5_e0 import (
    scoped_source_lexical_k5,
)


@pytest.mark.parametrize("mixed", [False, True])
def test_three_distinct_source_domains_use_original_contracts(mixed):
    router = build_multidomain_source(500, mixed_scope=mixed)
    actual = sum(len(t.endpoints) for t in router.registry.tools())
    assert actual == 512
    assert {d.identity_kind for d in DOMAINS} == {"integer", "string"}
    for domain in DOMAINS:
        oracle = source_scan_oracle(router, domain)
        assert len(oracle) == 1
        root, left, right = oracle[0]
        assert len({root, left, right}) == 3
        assert all(key.startswith(domain.name + "_") for key in (
            root, left, right,
        ))
        for query in domain.aliases:
            ranked, original = scoped_source_lexical_k5(
                router, query=query, group=domain.group(),
            )
            assert len(ranked) <= 5
            assert set(ranked).issubset(original)
            assert all(
                key.startswith(domain.name + "_") for key in ranked
            )
            assert not any(
                "wrong_id" in key or "unlicensed" in key or "other_source" in key
                for key in oracle[0]
            )


@pytest.mark.parametrize("mixed", [False, True])
def test_multidomain_500_source_oracle_and_revocation(mixed):
    result = analyze_multidomain_source(base_routes=500, mixed_scope=mixed)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["evidence_tier"] == "E0_MULTIDOMAIN_DEVELOPER_SOURCE_NOT_E2"
    assert result["actual_registered_native_routes"] == 512
    assert result["three_source_domains"] == ["crm", "lab", "inventory"]
    assert result["strict_k"] == 5
    assert len(result["rows"]) == 9
    assert result["all_domain_revocations_denied"] is True
    assert result["independent_e2_qualified"] is False
    assert result["model_token_measurement"] is False
    assert result["actual_provider_calls"] is False
    assert result["release_qualified"] is False
    assert sum(v for k, v in result["paired"].items() if k.endswith("_complete")) == 9
    for row in result["rows"]:
        assert row["g5_source_complete"] is True
        assert row["g5_route_count"] == 3
        assert row["lexical_route_count"] <= 5
        assert row["same_host_scope_k"] is True
        assert row["shared_complete_cost_eligible"] == (
            row["g5_source_complete"] and row["lexical_source_complete"]
        )


@pytest.mark.parametrize("base", [True, False, 499, 501, 500.0, "500"])
def test_unsupported_source_catalog_size_fails_closed(base):
    with pytest.raises(ValueError, match="preregistered"):
        build_multidomain_source(base, mixed_scope=False)


@pytest.mark.parametrize("scope", [None, 1, "true"])
def test_unsupported_source_scope_type_fails_closed(scope):
    with pytest.raises(ValueError, match="mixed scope"):
        build_multidomain_source(500, mixed_scope=scope)


def test_invalid_source_oracle_domain_fails_closed():
    router = build_multidomain_source(500, mixed_scope=False)
    with pytest.raises(ValueError, match="unqualified"):
        source_scan_oracle(router, "lab")


def test_original_source_health_blocks_lab_consumers():
    router = build_multidomain_source(500, mixed_scope=True)
    domain = DOMAINS[0]
    initial = source_scan_oracle(router, domain)
    assert len(initial) == 1
    right = initial[0][-1].rsplit(".", 1)[0]
    router.planner.availability_predicate = lambda tool, _ep: tool.key != right
    assert source_scan_oracle(router, domain) == ()
    ranked, budget = scoped_source_lexical_k5(
        router, query=domain.aliases[0], group=domain.group(),
    )
    assert right + ".read" not in budget
    assert right + ".read" not in ranked
