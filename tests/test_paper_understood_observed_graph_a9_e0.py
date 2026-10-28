"""A9: source-attested named DAG, real registered executor, no extra executor."""

from __future__ import annotations

import pytest
from test_paper_understood_graph_plan import CATALOG, INTENTS, _node

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.errors import (
    PolicyViolationError,
    SchemaValidationError,
    TransientInvocationError,
)
from schemarouter.paper_understood_direct_plan import PaperUnderstanding
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan


def _fixture(
    *, hops: int = 2, host_root: bool = False, root_value: object = "contact-7",
    middle_value: object = "case-42", target_value: object = "open", on_step=None,
):
    seen: list[tuple[str, dict]] = []
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    root = _node(
        "root", output_semantic="crm.contact_id" if hops == 2 else "crm.case_id",
        identifier=True,
    )
    if host_root:
        root_param = ParameterSpec(
            name="external_id", required=True, json_schema={"type": "string"},
        )
        root = root.model_copy(update={"endpoints": [root.endpoints[0].model_copy(
            update={
                "parameters": [root_param],
                "input_schema": {
                    "type": "object",
                    "properties": {"external_id": {"type": "string"}},
                    "required": ["external_id"],
                },
            },
        )]})

    def invoke(name, data):
        def handler(endpoint, arguments):
            seen.append((name, dict(arguments)))
            if on_step:
                on_step(router, name)
            return data() if callable(data) else data
        return handler

    router.add_bound_tool(root, invoke("root", lambda: {
        "contact_id" if hops == 2 else "case_id": root_value,
    }))
    if hops == 2:
        router.add_bound_tool(_node(
            "middle", input_semantic="crm.contact_id", output_semantic="crm.case_id",
            identifier=True,
        ), invoke("middle", lambda: {"case_id": middle_value}))
    router.add_bound_tool(_node(
        "target_0", input_semantic="crm.case_id",
    ), invoke("target_0", lambda: {"status": target_value}))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=(frozenset({"root.read"}) if host_root else frozenset()),
    )
    return router, index, seen


def _hints(*, target: str = "target_0", parameter_hints=None):
    return PaperUnderstanding(
        intent_id="case.lookup", named_tools=(target,),
        parameter_hints=parameter_hints or {},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hops", [1, 2])
async def test_registered_executor_observes_exact_named_path_and_binds_each_edge(hops):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture(hops=hops)
    receipt = await observe_and_execute_paper_understood_graph(
        router, _hints(parameter_hints={"case_id": "forged-id"}),
        principal=PrincipalContext(subject="reader-a", roles=("reader",)),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
    )
    expected = ([
        ("root", {}), ("middle", {"contact_id": "contact-7"}),
        ("target_0", {"case_id": "case-42"}),
    ] if hops == 2 else [
        ("root", {}), ("target_0", {"case_id": "contact-7"}),
    ])
    assert seen == expected
    assert tuple(result.tool for result in receipt.results) == tuple(
        name for name, _ in expected
    )
    assert [item.call.arguments for item in receipt.plan.calls] == [
        args for _, args in expected
    ]
    assert receipt.plan.status == "ready"
    assert receipt.provider_provenance_verified is False
    assert receipt.executable_authority is False
    assert receipt.independent_e2 is False


@pytest.mark.asyncio
async def test_explicit_host_approved_root_is_required_and_never_model_inferred():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture(host_root=True)
    kwargs = dict(
        principal=PrincipalContext(subject="reader-a", roles=("reader",)),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
    )
    with pytest.raises((SchemaValidationError, PolicyViolationError)):
        await observe_and_execute_paper_understood_graph(
            router, _hints(parameter_hints={"external_id": "forged"}), **kwargs,
        )
    assert not seen
    with pytest.raises((SchemaValidationError, PolicyViolationError)):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            host_source_arguments={"root.read": {"external_id": ["injected"]}},
            **kwargs,
        )
    assert not seen
    receipt = await observe_and_execute_paper_understood_graph(
        router, _hints(),
        host_source_arguments={"root.read": {"external_id": "trusted-host"}},
        **kwargs,
    )
    assert seen == [
        ("root", {"external_id": "trusted-host"}),
        ("middle", {"contact_id": "contact-7"}),
        ("target_0", {"case_id": "case-42"}),
    ]
    assert len(receipt.results) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, ["other"], {"id": "forged"}, 3.0, ""])
async def test_invalid_root_observation_never_reaches_middle(invalid):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture(root_value=invalid)
    with pytest.raises((PolicyViolationError, SchemaValidationError, ValueError)):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, ["other"], {"id": "forged"}, 4.0, ""])
async def test_invalid_middle_observation_never_reaches_target(invalid):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture(middle_value=invalid)
    with pytest.raises((PolicyViolationError, SchemaValidationError, ValueError)):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert seen == [
        ("root", {}), ("middle", {"contact_id": "contact-7"}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_at, blocked", [
    ("root", "middle"), ("middle", "target_0"),
])
async def test_midflight_permission_revocation_blocks_downstream(revoke_at, blocked):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    def revoke(router, name):
        if name == revoke_at:
            router.authorization_policy = AuthorizationPolicy(
                default_effect="deny", rules=(
                    AuthorizationRule(
                        effect="deny", operation=f"{blocked}.read",
                        roles_any=("reader",),
                    ),
                    AuthorizationRule(
                        effect="allow", operation="*.read", roles_any=("reader",),
                    ),
                ),
            )

    router, index, seen = _fixture(on_step=revoke)
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert len(seen) == (1 if revoke_at == "root" else 2)


@pytest.mark.asyncio
async def test_principal_mutation_during_middle_invalidates_original_observation():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    actor = PrincipalContext(subject="reader-a", roles=("reader",))

    def swap(_router, name):
        if name == "middle":
            actor.subject = "reader-b"

    router, index, seen = _fixture(on_step=swap)
    with pytest.raises(PolicyViolationError, match="principal"):
        await observe_and_execute_paper_understood_graph(
            router, _hints(), principal=actor,
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_unknown_named_tool_never_triggers_executor():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture()
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(target="unknown"),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_transient_middle_error_does_not_retry_or_publish_partial_result():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    def fail(_router, name):
        if name == "middle":
            raise TransientInvocationError("offline")

    router, index, seen = _fixture(on_step=fail)
    with pytest.raises(TransientInvocationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_source_owned_understanding_mutation_during_root_aborts_following_calls():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    hints = _hints()

    def mutate(_router, name):
        if name == "root":
            hints.named_tools = ("untrusted",)

    router, index, seen = _fixture(on_step=mutate)
    with pytest.raises(PolicyViolationError, match="source declarations"):
        await observe_and_execute_paper_understood_graph(
            router, hints,
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_source_owned_host_arguments_mutation_during_middle_aborts_target():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    host = {"root.read": {"external_id": "trusted"}}

    def mutate(_router, name):
        if name == "middle":
            host["root.read"]["external_id"] = "attacker"

    router, index, seen = _fixture(host_root=True, on_step=mutate)
    with pytest.raises(PolicyViolationError, match="source declarations"):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
            host_source_arguments=host,
        )
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_middle_output_data_scope_hidden_during_root_stops_before_middle():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    def hide(router, name):
        if name == "root":
            router.authorization_policy = AuthorizationPolicy(
                default_effect="deny",
                rules=(AuthorizationRule(
                    effect="allow", operation="*.read", roles_any=("reader",),
                ),),
                data_rules=(DataScopeRule(
                    operation="middle.read", roles_any=("reader",),
                    hidden_fields=("case_id",),
                ),),
            )

    router, index, seen = _fixture(on_step=hide)
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_bad_last_result_identity_does_not_publish_fake_completed_graph(monkeypatch):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture()
    executor = router.execute

    async def wrong_identity(plan, *, config=None):
        result = await executor(plan, config=config)
        if plan.calls[0].tool == "target_0":
            return [result[0].model_copy(update={"tool": "unregistered"})]
        return result

    monkeypatch.setattr(router, "execute", wrong_identity)
    with pytest.raises(SchemaValidationError, match="unexpected tool result"):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_exact_one_attempt_one_call_budget_per_node(monkeypatch):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture()
    executor = router.execute
    budgets: list[tuple[int, int, int, int]] = []

    async def record_budget(plan, *, config=None):
        assert config is not None and config.budget is not None
        budget = config.budget
        budgets.append((
            len(plan.calls), budget.max_tool_calls,
            budget.max_attempts, budget.max_remote_attempts,
        ))
        return await executor(plan, config=config)

    monkeypatch.setattr(router, "execute", record_budget)
    receipt = await observe_and_execute_paper_understood_graph(
        router, _hints(),
        principal=PrincipalContext(subject="reader-a", roles=("reader",)),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
    )
    assert budgets == [(1, 1, 1, 1)] * 3
    assert len(seen) == len(receipt.results) == 3


@pytest.mark.asyncio
async def test_max_hops_bound_disallows_two_hop_without_any_invocation():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture()
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(), max_hops=1,
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert not seen


@pytest.mark.asyncio
async def test_missing_last_required_field_rejects_combined_success():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _fixture(target_value=None)
    with pytest.raises(SchemaValidationError):
        await observe_and_execute_paper_understood_graph(
            router, _hints(),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
        )
    assert len(seen) == 3


def test_named_graph_host_arg_compilation_is_source_scoped():
    router, index, _ = _fixture(host_root=True)
    actor = PrincipalContext(subject="reader-a", roles=("reader",))
    with pytest.raises(PolicyViolationError):
        compile_paper_understood_graph_plan(
            router, _hints(), principal=actor,
            catalog=CATALOG, intent_registry=INTENTS, index=index,
            host_source_arguments={"target_0.read": {"case_id": "forged"}},
        )
    plan = compile_paper_understood_graph_plan(
        router, _hints(), principal=actor,
        catalog=CATALOG, intent_registry=INTENTS, index=index,
        host_source_arguments={"root.read": {"external_id": "approved"}},
    )
    assert plan.calls[0].call.arguments == {"external_id": "approved"}
    assert plan.calls[1].call.arguments == {}


def test_named_graph_execution_api_is_explicitly_exported():
    from schemarouter import (
        PaperUnderstoodExecutedGraph,
        observe_and_execute_paper_understood_graph,
    )

    assert PaperUnderstoodExecutedGraph.__name__ == "PaperUnderstoodExecutedGraph"
    assert callable(observe_and_execute_paper_understood_graph)


def _ranked_fixture(*, hops: int = 2, n_targets: int = 6, on_step=None):
    router, _index, seen = _fixture(hops=hops, on_step=on_step)
    for i in range(1, n_targets):
        name = f"target_{i}"
        def invoke(_endpoint, arguments, *, target=name):
            seen.append((target, dict(arguments)))
            return {"status": "open"}
        router.add_bound_tool(
            _node(name, input_semantic="crm.case_id"), invoke,
        )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return router, index, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("hops", [1, 2])
async def test_ranked_unnamed_g5_executes_only_one_original_complete_dag(hops):
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router, index, seen = _ranked_fixture(hops=hops)
    winner = "target_5.read"
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={winner: 100},
    )
    receipt = await observe_and_execute_paper_understood_graph(
        router, PaperUnderstanding(intent_id="case.lookup", named_tools=()),
        principal=PrincipalContext(subject="reader-a", roles=("reader",)),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
        rank_policy=policy, allow_unnamed_graph_discovery=True,
    )
    assert [name for name, _ in seen] == (
        ["root", "target_5"] if hops == 1
        else ["root", "middle", "target_5"]
    )
    assert receipt.plan.ranked_unverified
    assert receipt.plan.status == "ready"
    assert len(receipt.results) == hops + 1
    assert receipt.executable_authority is False
    assert receipt.independent_e2 is False


@pytest.mark.asyncio
async def test_ranked_named_six_target_g5_executes_top_owner_path_only():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router, index, seen = _ranked_fixture(hops=1)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_4.read": 80},
    )
    receipt = await observe_and_execute_paper_understood_graph(
        router, PaperUnderstanding(
            intent_id="case.lookup",
            named_tools=tuple(f"target_{i}" for i in range(6)),
        ),
        principal=PrincipalContext(subject="reader-a", roles=("reader",)),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
        rank_policy=policy,
    )
    assert [name for name, _ in seen] == ["root", "target_4"]
    assert len(receipt.results) == 2
    assert receipt.plan.ranked_unverified


@pytest.mark.asyncio
async def test_ranked_unnamed_g5_requires_owner_policy_before_any_provider_call():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )

    router, index, seen = _ranked_fixture()
    with pytest.raises(ValueError, match="owner|Rank|host approval"):
        await observe_and_execute_paper_understood_graph(
            router, PaperUnderstanding(intent_id="case.lookup"),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
            allow_unnamed_graph_discovery=True,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_ranked_unnamed_g5_owner_policy_mutation_after_root_fails_closed():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    policy_holder = {}
    def mutate(_router, step):
        if step == "root":
            policy_holder["policy"].route_priorities["target_4.read"] = 200

    router, index, seen = _ranked_fixture(hops=2, on_step=mutate)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_5.read": 100},
    )
    policy_holder["policy"] = policy
    with pytest.raises(PolicyViolationError, match="owner|rank|changed"):
        await observe_and_execute_paper_understood_graph(
            router, PaperUnderstanding(intent_id="case.lookup"),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
            rank_policy=policy, allow_unnamed_graph_discovery=True,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_ranked_unnamed_g5_changed_live_policy_blocks_downstream_execution():
    from schemarouter.paper_consumer_execution import (
        observe_and_execute_paper_understood_graph,
    )
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    def revoke(router, step):
        if step == "middle":
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    router, index, seen = _ranked_fixture(hops=2, on_step=revoke)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_5.read": 100},
    )
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_understood_graph(
            router, PaperUnderstanding(intent_id="case.lookup"),
            principal=PrincipalContext(subject="reader-a", roles=("reader",)),
            catalog=CATALOG, intent_registry=INTENTS, index=index,
            rank_policy=policy, allow_unnamed_graph_discovery=True,
        )
    assert [name for name, _ in seen] == ["root", "middle"]
