"""Host-prepared Algorithm 1 configuration for the existing router and executor.

The private witnesses below add current-source restrictions to issued plans.
They are not serialized permissions and never replace executor authorization.
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext, _current_principal_context
from .errors import PolicyViolationError
from .field_routing_session import SchemaFieldRoutingSession
from .models import ExecutionPlan, PaperPlanRequest, PlanRequest, ToolCall
from .paper_native_rank import PaperNativeRankPolicy
from .paper_query_needs import PaperQueryUnderstanding
from .paper_query_understanding import PaperFieldModel, _prepare_model_query, _PreparedModelQuery
from .paper_typed_tool_plan import PaperTypedToolPlan
from .paper_understood_direct_plan import PaperIntentRegistry, PaperUnderstanding

if TYPE_CHECKING:
    from ._source_availability import _SourceAvailability
    from .executor import RegistryExecutor, _BindingSnapshot
    from .registry import ToolRegistry
    from .runtime import SchemaRouter


def _declaration_json(value: Any) -> str:
    """Do not expose callback-injected object names or private validation details."""
    try:
        return value.model_dump_json()
    except Exception:
        raise PolicyViolationError("paper planning declaration changed or invalid") from None


def _build_paper_direct_plan(
    registry: ToolRegistry, query: str, receipt: PaperTypedToolPlan,
) -> ExecutionPlan:
    """Assemble a freshly proven Algorithm 1 plan for the ordinary executor.

    The field session owns compilation and live proof revalidation. This
    private bridge never ranks again, binds model proposals, or treats a
    diagnostic's partial calls as a complete executable plan.
    """
    if (
        receipt.status != "ready" or receipt.executable_authority is not False
        or receipt.bindings or receipt.requested_k != 5
        or not 1 <= len(receipt.calls) <= receipt.requested_k
        or len({(item.call.tool, item.call.endpoint) for item in receipt.calls})
        != len(receipt.calls)
        or receipt.coverage is not None and (
            receipt.coverage.complete is not True or receipt.coverage.uncovered
        )
    ):
        raise PolicyViolationError(
            "paper direct execution requires a ready independent field-complete plan"
        )
    if any(not item.call.executable for item in receipt.calls):
        raise PolicyViolationError("paper direct execution has unresolved inputs")
    if receipt.registry_version != registry.version:
        raise PolicyViolationError("paper direct plan source revision changed")
    return ExecutionPlan(
        query=query,
        registry_version=receipt.registry_version,
        calls=[item.call.model_copy(deep=True) for item in receipt.calls],
        coverage=receipt.coverage.model_copy(deep=True) if receipt.coverage else None,
    )


def _build_paper_query_plan(
    registry: ToolRegistry, query: str, receipt: PaperTypedToolPlan, *, max_calls: int,
) -> ExecutionPlan:
    """Preserve incomplete paper diagnostics without declaring them executable."""
    status = receipt.status if len(receipt.calls) <= max_calls else "budget_unsatisfied"
    if status == "ready":
        plan = _build_paper_direct_plan(registry, query, receipt)
        plan.planning_status = status
        return plan
    if receipt.executable_authority or receipt.bindings:
        raise PolicyViolationError("paper query plan must contain independent source calls")
    if receipt.registry_version != registry.version:
        raise PolicyViolationError("paper query plan source revision changed")
    return ExecutionPlan(
        query=query, registry_version=receipt.registry_version,
        calls=[item.call.model_copy(deep=True) for item in receipt.calls],
        coverage=receipt.coverage.model_copy(deep=True) if receipt.coverage else None,
        planning_status=status,
        warnings=[f"Algorithm 1 planning status: {status}"],
    )


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class _PreparedPaperPlanning:
    router: SchemaRouter
    session: SchemaFieldRoutingSession
    model: PaperFieldModel
    intents: PaperIntentRegistry
    rank: PaperNativeRankPolicy
    intent_ids: tuple[str, ...]
    input_bytes: int
    output_bytes: int
    authority: _SourceAvailability
    executor: RegistryExecutor
    owner: tuple[str, str, str]

    @classmethod
    def prepare(
        cls, router: SchemaRouter, session: SchemaFieldRoutingSession, *,
        model: PaperFieldModel, intent_registry: PaperIntentRegistry,
        rank_policy: PaperNativeRankPolicy, model_visible_intent_ids: tuple[str, ...],
        max_model_input_bytes: int, max_model_output_bytes: int,
    ) -> _PreparedPaperPlanning:
        if not isinstance(session, SchemaFieldRoutingSession) or session._router is not router:
            raise ValueError("paper planning requires a session owned by this router")
        if not callable(model):
            raise ValueError("paper planning requires an explicit model callback")
        if not isinstance(intent_registry, PaperIntentRegistry):
            raise ValueError("paper planning requires a reviewed intent registry")
        if not isinstance(rank_policy, PaperNativeRankPolicy):
            raise ValueError("paper planning requires reviewed paper_v1 Rank")
        intents = PaperIntentRegistry.model_validate(
            intent_registry.model_dump(mode="python"), strict=True,
        )
        rank = PaperNativeRankPolicy.model_validate(
            rank_policy.model_dump(mode="python"), strict=True,
        )
        if rank.direct_score_mode != "paper_v1" or rank.focus_direct is not True:
            raise ValueError("paper planning requires paper_v1 Rank with focus_direct=True")
        if (
            rank.snapshot_id != session.snapshot_id
            or intents.projection_snapshot_id not in (None, session.snapshot_id)
        ):
            raise PolicyViolationError("paper planning owner snapshot mismatch")
        if (
            type(model_visible_intent_ids) is not tuple
            or not 1 <= len(model_visible_intent_ids) <= 16
            or any(type(value) is not str for value in model_visible_intent_ids)
            or len(set(model_visible_intent_ids)) != len(model_visible_intent_ids)
            or not set(model_visible_intent_ids) <= {item.intent_id for item in intents.intents}
        ):
            raise ValueError("paper planning requires bounded reviewed model intent IDs")
        if (
            type(max_model_input_bytes) is not int or not 1 <= max_model_input_bytes <= 32768
            or type(max_model_output_bytes) is not int or not 1 <= max_model_output_bytes <= 4096
        ):
            raise ValueError("invalid paper model byte budgets")
        if router.authorization_policy is None:
            raise PolicyViolationError("paper planning requires explicit source authorization")
        session._index.field_index._assert_source(router)
        router._source_availability_predicate()
        if router.executor.registry is not router.registry:
            raise PolicyViolationError("paper planning component source mismatch")
        return cls(
            router, session, model, intents, rank, model_visible_intent_ids,
            max_model_input_bytes, max_model_output_bytes,
            router._source_availability, router.executor,
            (session.catalog_revision_id, _declaration_json(intents), _declaration_json(rank)),
        )

    def check_current(self) -> None:
        try:
            if (
                self.router._paper_planning is not self
                or self.router._source_availability is not self.authority
                or self.router.executor is not self.executor
                or self.router.planner is not None
                or self.router._legacy_routing
                or self.executor.registry is not self.router.registry
                or (
                    self.session.catalog_revision_id,
                    _declaration_json(self.intents), _declaration_json(self.rank),
                ) != self.owner
            ):
                raise PolicyViolationError(
                    "paper planning configuration or owner changed; reconfigure"
                )
            self.router._source_availability_predicate()
            self.session._index.field_index._assert_source(self.router)
        except Exception:
            raise PolicyViolationError(
                "paper planning source or configuration changed; reconfigure"
            ) from None

    async def aplan(
        self, request: PaperPlanRequest | PlanRequest | str,
        *, principal: PrincipalContext | None, executable_only: bool = False,
    ) -> ExecutionPlan:
        if isinstance(request, PlanRequest):
            raise ValueError(
                "configured paper planning requires str or PaperPlanRequest, not PlanRequest",
            )
        if type(request) is str:
            request = PaperPlanRequest(query=request)
        if not isinstance(request, PaperPlanRequest):
            raise ValueError("configured paper planning requires PaperPlanRequest")
        if not isinstance(principal, PrincipalContext):
            raise PolicyViolationError("paper planning requires a trusted principal")
        self.check_current()
        request_json = _declaration_json(request)
        pinned_request = PaperPlanRequest.model_validate(
            request.model_dump(mode="python"), strict=True,
        )
        principal_json = _declaration_json(principal)
        pinned_principal = principal.model_copy(deep=True)

        def check_request() -> None:
            self.check_current()
            if (
                _declaration_json(request) != request_json
                or _declaration_json(principal) != principal_json
                or _declaration_json(pinned_principal) != principal_json
            ):
                raise PolicyViolationError("paper planning request or principal changed")

        prepared = _prepare_model_query(
            self.session, pinned_request.query, principal=pinned_principal,
            intent_registry=self.intents, model_visible_intent_ids=self.intent_ids,
            host_source_arguments=pinned_request.host_source_arguments or None,
            rank_policy=self.rank, max_model_input_bytes=self.input_bytes,
            max_model_output_bytes=self.output_bytes,
        )
        check_request()
        decoded = await prepared.understand(self.model)
        check_request()
        raw_json = _declaration_json(decoded)
        receipt = prepared.compile(decoded)
        check_request()
        plan = _build_paper_query_plan(
            self.router.registry, pinned_request.query, receipt, max_calls=pinned_request.max_calls,
        )
        bindings = {call.tool: self.executor._binding_snapshot(call.tool) for call in plan.calls}
        witness = _PaperPlanWitness(
            self, prepared, decoded, raw_json, deepcopy(receipt), principal_json,
            request_json, check_request, _declaration_json(plan),
            {(call.tool, call.endpoint): _declaration_json(call) for call in plan.calls},
            bindings, plan.executable,
        )
        plan._planning_witness = witness
        for call in plan.calls:
            call._planning_witness = witness
        witness.validate_plan(self.executor, plan, principal, execution=executable_only)
        return plan

    def validate_plan(
        self, plan: ExecutionPlan, principal: PrincipalContext | None, *, execution: bool,
    ) -> None:
        witness = plan._planning_witness
        if not isinstance(witness, _PaperPlanWitness) or witness.configuration is not self:
            raise PolicyViolationError(
                "configured paper execution requires a locally issued plan; replan",
            )
        witness.validate_plan(self.executor, plan, principal, execution=execution)


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class _PaperPlanWitness:
    configuration: _PreparedPaperPlanning
    prepared: _PreparedModelQuery
    decoded: PaperQueryUnderstanding | PaperUnderstanding
    decoded_json: str
    receipt: PaperTypedToolPlan
    principal_json: str
    request_json: str
    check_request: Callable[[], None] = field(repr=False)
    plan_json: str
    calls: dict[tuple[str, str], str]
    bindings: dict[str, _BindingSnapshot]
    ready: bool

    def __deepcopy__(self, memo: dict[int, Any]) -> _PaperPlanWitness:
        # Copies share a restrictive local witness, not copied router locks or
        # a new grant. Each copied public shape is still compared before use.
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _PaperPlanWitness):
            return NotImplemented
        return (
            self.configuration is other.configuration
            and self.principal_json == other.principal_json
            and self.request_json == other.request_json and self.decoded_json == other.decoded_json
            and self.plan_json == other.plan_json and self.bindings == other.bindings
        )

    def _check(self, executor: RegistryExecutor, principal: PrincipalContext | None) -> None:
        self.check_request()
        if (
            executor is not self.configuration.executor
            or principal is None or _declaration_json(principal) != self.principal_json
            or _declaration_json(self.decoded) != self.decoded_json
        ):
            raise PolicyViolationError("paper plan principal, executor or understanding changed")
        current = self.prepared.compile(self.decoded)
        self.check_request()
        if _declaration_json(self.decoded) != self.decoded_json or current != self.receipt:
            raise PolicyViolationError("paper query proof changed before execution")

    def _require_bindings(self, executor: RegistryExecutor) -> None:
        if not self.ready:
            raise PolicyViolationError("paper execution requires a ready complete plan")
        for tool_key, binding in self.bindings.items():
            if (
                binding.invoker is None or binding.generation is None
                or executor._binding_snapshot(tool_key) != binding
                or not executor.is_binding_ready_for_contract(
                    tool_key, self.configuration.router.registry.get(tool_key).fingerprint,
                )
            ):
                raise PolicyViolationError(
                    "paper plan selected binding unavailable or changed; replan",
                )

    def validate_plan(
        self, executor: RegistryExecutor, plan: ExecutionPlan,
        principal: PrincipalContext | None, *, execution: bool,
    ) -> None:
        if (
            plan._planning_witness is not self or _declaration_json(plan) != self.plan_json
            or any(call._planning_witness is not self for call in plan.calls)
        ):
            raise PolicyViolationError("paper plan changed or lost its local proof; replan")
        self._check(executor, principal)
        if execution:
            self._require_bindings(executor)
        if (
            plan._planning_witness is not self or _declaration_json(plan) != self.plan_json
            or any(call._planning_witness is not self for call in plan.calls)
        ):
            raise PolicyViolationError("paper plan changed during source verification; replan")

    def validate_call(self, executor: RegistryExecutor, call: ToolCall) -> None:
        if (
            call._planning_witness is not self
            or self.calls.get((call.tool, call.endpoint)) != _declaration_json(call)
        ):
            raise PolicyViolationError("paper call changed or lost its local proof; replan")
        self._check(executor, _current_principal_context())
        self._require_bindings(executor)
        if (
            call._planning_witness is not self
            or self.calls.get((call.tool, call.endpoint)) != _declaration_json(call)
        ):
            raise PolicyViolationError("paper call changed during source verification; replan")

    def generation(self, tool_key: str) -> int:
        generation = self.bindings[tool_key].generation
        if generation is None:
            raise PolicyViolationError("paper plan selected binding unavailable; replan")
        return generation
