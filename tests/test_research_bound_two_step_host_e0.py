"""A02 two-stage actual Router.execute host-bound contract, not provider E2."""
from __future__ import annotations

import json

import pytest

from schemarouter import AuthorizationPolicy, AuthorizationRule, PolicyViolationError
from scripts.research_bound_two_step_host_e0 import (
    CANARY,
    LANGUAGES,
    PRINCIPAL,
    QUERIES,
    build_bound_two_step_source,
    execute_bound_two_step_e0,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", LANGUAGES)
async def test_actual_router_host_bindings_run_in_two_step_state_chain(lang):
    seen = []
    router = build_bound_two_step_source(seen)
    report = await execute_bound_two_step_e0(
        router, query=QUERIES[lang], principal=PRINCIPAL,
    )
    assert seen == [
        ("marine.read", {"place": "Seoul"}),
        ("papers.read", {"record_id": "record-321"}),
    ]
    assert report["host_result_oracle_confirmed"] is True
    assert report["router_execute_invocations"] == 2
    assert report["host_field_preflights"] == 2
    assert report["real_router_execution_path_used"] is True
    assert report["real_external_native_provider_execution"] is False
    assert report["actual_model_inference_measured"] is False
    assert report["actual_model_final_answer_correctness_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["release_safety_gate_passed"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in (CANARY, "record-321", "Seoul", "marine.read", "papers.read"):
        assert forbidden not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ({}, {"place": ""}, {"place": 42},
                                 {"place": "Seoul", "secret": CANARY}))
async def test_required_fields_block_before_any_real_host_invocation(bad):
    seen = []
    router = build_bound_two_step_source(seen)
    with pytest.raises(PolicyViolationError):
        await execute_bound_two_step_e0(
            router, query=QUERIES["en"], principal=PRINCIPAL,
            first_fields=bad,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_policy_revocation_after_second_capture_prevents_second_host_io():
    seen = []
    router = build_bound_two_step_source(seen)
    existing = router.authorization_policy
    assert existing is not None

    def revoke(view):
        assert "papers.read" in view.visible_route_ids
        # Critically: mutate the SAME policy object, not its identity.
        object.__setattr__(existing.rules[-1], "effect", "deny")

    with pytest.raises(PolicyViolationError, match="authorization policy modified"):
        await execute_bound_two_step_e0(
            router, query=QUERIES["ko"], principal=PRINCIPAL,
            on_second_capture=revoke,
        )
    assert seen == [("marine.read", {"place": "Seoul"})]


@pytest.mark.asyncio
async def test_object_swap_after_second_capture_blocks_stale_host_io():
    seen = []
    router = build_bound_two_step_source(seen)

    def revoke(view):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="deny", operation="*.*", roles_any=("reader",),
            ),),
        )

    with pytest.raises(PolicyViolationError):
        await execute_bound_two_step_e0(
            router, query=QUERIES["ja"], principal=PRINCIPAL,
            on_second_capture=revoke,
        )
    assert seen == [("marine.read", {"place": "Seoul"})]


@pytest.mark.asyncio
async def test_principal_role_revocation_before_second_step_blocks_execution():
    seen = []
    router = build_bound_two_step_source(seen)
    from schemarouter import PrincipalContext
    principal = PrincipalContext(subject="test-reader", roles=("reader",))

    def revoke(view):
        principal.roles = ("outsider",)

    with pytest.raises(PolicyViolationError, match="principal claims"):
        await execute_bound_two_step_e0(
            router, query=QUERIES["en"], principal=principal,
            on_second_capture=revoke,
        )
    assert seen == [("marine.read", {"place": "Seoul"})]


@pytest.mark.asyncio
async def test_second_bound_host_exception_does_not_disclose_secret_or_claim_success():
    seen = []
    router = build_bound_two_step_source(seen)
    tool = router.registry.get("papers")

    def failing(endpoint, arguments):
        seen.append(("papers.read", dict(arguments)))
        raise RuntimeError("secret provider failure " + CANARY)

    router.executor.bind(
        tool.key, failing, expected_fingerprint=tool.fingerprint,
    )
    with pytest.raises(PolicyViolationError) as captured:
        await execute_bound_two_step_e0(
            router, query=QUERIES["en"], principal=PRINCIPAL,
        )
    assert len(seen) == 2
    assert CANARY not in str(captured.value)
    assert "secret provider failure" not in str(captured.value)


@pytest.mark.asyncio
async def test_no_model_generated_state_or_host_gold_can_be_promoted_to_e2():
    seen = []
    router = build_bound_two_step_source(seen)
    report = await execute_bound_two_step_e0(
        router, query=QUERIES["ja"], principal=PRINCIPAL,
    )
    assert report["host_result_oracle_confirmed"]
    assert not report["actual_model_final_answer_correctness_measured"]
    assert not report["real_external_native_provider_execution"]
    assert not report["independent_e2_qualified"]
