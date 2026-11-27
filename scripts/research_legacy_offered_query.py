"""Checkout-only historical offered Concept-ID model protocol.

Retains the original source-scoped disclosure, bounded model receipt and
post-callback source/owner reattestation. Not the installed Algorithm 1 route.
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from schemarouter._authorization_witness import _policy_contents_digest
from schemarouter.authorization import PrincipalContext
from schemarouter.canonical_json import canonical_json_text
from schemarouter.concept_retrieval import (
    MAX_QUERY_BYTES,
    MAX_QUERY_CHARS,
    NativeConceptCatalog,
    NativeDeclaredConcept,
)
from schemarouter.errors import ModelAnalysisError, PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.models import PlanCoverage, SemanticFieldRequirement
from schemarouter.paper_field_retrieval import retrieve_paper_field_coverage
from schemarouter.paper_native_rank import PaperNativeRankPolicy
from schemarouter.paper_query_conditions import _apply_query_input_conditions
from schemarouter.paper_query_needs import PaperQueryUnderstanding
from schemarouter.paper_query_understanding import (
    PaperFieldModel,
    _decode_model_response,
    _understand_query,
)
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    _bounded_name,
)

if TYPE_CHECKING:
    from schemarouter.field_routing_session import SchemaFieldRoutingSession


def _decode_bounded_response(raw: dict[str, Any] | str, limit: int) -> PaperUnderstanding:
    return _decode_model_response(raw, limit, PaperUnderstanding)


def _owner_query_field_coverage(
    understood: PaperUnderstanding,
    *,
    concepts: dict[str, NativeDeclaredConcept],
    intents: dict[str, PaperIntentDeclaration],
    source_proven: bool,
) -> PlanCoverage:
    """Owner field ledger for query receipts whose core proof has no ledger.

    Query input conditions cannot stand in for the intent/concept output
    requirements. Only an already source-proven core receipt covers them.
    """
    concept_ids = list(understood.concept_ids)
    if understood.intent_id is not None:
        concept_ids = sorted(set(concept_ids) | set(
            intents[understood.intent_id].required_concept_ids,
        ))
    fields = [
        SemanticFieldRequirement(
            semantic_id=field.semantic_id,
            qualifiers=[
                f"concept_id={concept_id}",
                *([f"source_type={concept.source_type}"] if concept.source_type else []),
                *([f"license={concept.license}"] if concept.license else []),
                *(f"{key}={value}" for key, value in sorted(field.qualifiers.items())),
            ],
        )
        for concept_id in concept_ids
        for concept in [concepts[concept_id]]
        for field in concept.required_fields
    ]
    if not source_proven:
        # A failed current proof does not disclose owner field/source/license
        # metadata. These meaning IDs were already offered in the query payload.
        fields = [SemanticFieldRequirement(semantic_id=concept_id,
            qualifiers=[f"concept_id={concept_id}"],
        ) for concept_id in concept_ids]
    unresolved = [SemanticFieldRequirement(
        semantic_id="unresolved", qualifiers=[f"query_concept={proposal}"],
    ) for proposal in understood.unresolved_concepts]
    uncovered = [*([] if source_proven else fields), *unresolved]
    return PlanCoverage(
        required=[*fields, *unresolved], covered=fields if source_proven else [],
        uncovered=uncovered, complete=bool(fields) and not uncovered,
    )


@dataclass(frozen=True, slots=True)
class _PreparedModelQuery:
    """Pinned model disclosure and repeatable source compilation, never authority."""

    _payload: dict[str, Any] | None = field(repr=False)
    _response_type: type[PaperQueryUnderstanding] | type[PaperUnderstanding] = field(repr=False)
    _compile: Callable[[PaperQueryUnderstanding | PaperUnderstanding], PaperTypedToolPlan] = field(
        repr=False,
    )
    _verify: Callable[[], None] = field(repr=False)
    _max_input_bytes: int = field(repr=False)
    _max_output_bytes: int = field(repr=False)
    _direct_parameters: bool = field(default=False, repr=False)

    def verify(self) -> None:
        """Recheck the exact source, owner declarations and principal witness."""
        self._verify()

    async def understand(
        self, model: PaperFieldModel,
    ) -> PaperQueryUnderstanding | PaperUnderstanding:
        """Call the host model once, or abstain without disclosure when none is allowed."""
        if not callable(model):
            raise ValueError("explicit model callback required")
        self.verify()
        if self._payload is None:
            return PaperUnderstanding(intent_id=None)
        return await _understand_query(
            model, self._payload, response_type=self._response_type,
            max_input_bytes=self._max_input_bytes, max_output_bytes=self._max_output_bytes,
            verify=self.verify, direct_parameters=self._direct_parameters,
        )

    def compile(self, decoded: PaperQueryUnderstanding | PaperUnderstanding) -> PaperTypedToolPlan:
        """Re-prove all decoded query conditions without another model call or event loop."""
        self.verify()
        if type(decoded) is not self._response_type:
            raise ModelAnalysisError("model understanding has the wrong query protocol")
        try:
            # A caller may retain and mutate a decoded Pydantic model. Repeat
            # the same strict validation, including the direct-parameter
            # context, and detach every nested query need before source use.
            current = self._response_type.model_validate(
                decoded.model_dump(mode="python", warnings=False), strict=True,
                context={"paper_direct_parameters": self._direct_parameters},
            )
        except Exception:
            self.verify()
            raise ModelAnalysisError("invalid structured paper model response") from None
        self.verify()
        plan = self._compile(current)
        self.verify()
        return plan


async def compile_offered_model_query(
    session: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    model: PaperFieldModel,
    intent_registry: PaperIntentRegistry,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
    model_visible_tool_keys: tuple[str, ...] = (),
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    max_hops: int = 2,
    max_model_input_bytes: int = 32768,
    max_model_output_bytes: int = 4096,
    rank_policy: PaperNativeRankPolicy | None = None,
    allow_unnamed_graph_discovery: bool = False,
) -> PaperTypedToolPlan:
    """Historical explicitly offered-ID protocol; never an installed product route."""
    if not callable(model):
        raise ValueError("explicit model callback required")
    prepared = _prepare_model_query(
        session, query, principal=principal, intent_registry=intent_registry,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
        model_visible_tool_keys=model_visible_tool_keys,
        host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
        max_model_input_bytes=max_model_input_bytes,
        max_model_output_bytes=max_model_output_bytes,
        rank_policy=rank_policy,
        allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
    )
    return prepared.compile(await prepared.understand(model))


def _prepare_model_query(
    session: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    intent_registry: PaperIntentRegistry,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
    model_visible_tool_keys: tuple[str, ...] = (),
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    max_hops: int = 2,
    max_model_input_bytes: int = 32768,
    max_model_output_bytes: int = 4096,
    rank_policy: PaperNativeRankPolicy | None = None,
    allow_unnamed_graph_discovery: bool = False,
) -> _PreparedModelQuery:
    """Prepare the historical source-proven offered-ID disclosure."""
    if (
        type(query) is not str
        or not 2 <= len(query) <= MAX_QUERY_CHARS
        or len(query.encode("utf-8")) > MAX_QUERY_BYTES
        or query != query.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in query)
    ):
        raise ValueError("invalid bounded paper query")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper query requires trusted principal")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("host-approved intent registry required")
    if rank_policy is not None and not isinstance(rank_policy, PaperNativeRankPolicy):
        raise ValueError("reviewed paper rank policy required")
    if (
        rank_policy is not None
        and rank_policy.direct_score_mode == "paper_v1"
    ):
        raise ValueError("paper v1 Rank requires schema-independent Understand labels")
    if (
        type(allow_unnamed_graph_discovery) is not bool
        or allow_unnamed_graph_discovery and rank_policy is None
    ):
        # This authority comes only from the host call signature. Never
        # allow an LLM to activate graph-wide target discovery.
        raise ValueError(
            "unnamed graph discovery requires host approval and owner Rank"
        )
    if (
        allow_unnamed_graph_discovery and rank_policy is not None
        and rank_policy.direct_score_mode == "paper_v1"
    ):
        raise ValueError("paper v1 does not permit graph dependency discovery")
    if type(k) is not int or k != 5 or type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("paper query requires K5 and one or two graph hops")
    if (
        type(max_model_input_bytes) is not int
        or not 1 <= max_model_input_bytes <= 32768
        or type(max_model_output_bytes) is not int
        or not 1 <= max_model_output_bytes <= 4096
    ):
        raise ValueError("invalid paper model byte budget")

    # Review-only sessions have no approved concept authority. The public
    # session entrypoint already enforces this; the standalone compiler must
    # enforce it too before producing any model-visible disclosure.
    catalog = session._require_catalog()
    try:
        reviewed = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
        intents = PaperIntentRegistry.model_validate(
            intent_registry.model_dump(mode="python"), strict=True,
        )
        before = (catalog.model_dump_json(), intent_registry.model_dump_json(),
                  principal.model_dump_json(), deepcopy(host_source_arguments),
                  canonical_json_text(host_source_arguments),
                  rank_policy.model_dump_json() if rank_policy else None)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise PolicyViolationError("paper query owner declarations invalid") from None

    if rank_policy is not None:
        try:
            reviewed_rank = PaperNativeRankPolicy.model_validate(
                rank_policy.model_dump(mode="python"), strict=True,
            )
            annotated = (
                set(reviewed_rank.route_domains)
                | set(reviewed_rank.route_priorities)
                | set(reviewed_rank.web_route_ids)
            )
            if (
                reviewed_rank.snapshot_id != session.snapshot_id
                or not annotated <= session._index.field_index.route_locations.keys()
            ):
                raise ValueError("stale paper Rank source declaration")
        except Exception:
            # Fail before any external model disclosure; diagnostics must
            # never serialize provider/owner policy internals into errors.
            raise PolicyViolationError("paper query rank source preflight failed") from None

    annotated = intents.annotated_routes()
    if intents.projection_snapshot_id is not None and (
        intents.projection_snapshot_id != session.snapshot_id
        or not annotated <= session._index.field_index.route_locations.keys()
    ):
        raise PolicyViolationError("paper query intent source preflight failed")

    approved_concepts = {c.concept_id: c for c in reviewed.concepts}
    approved_intents = {i.intent_id: i for i in intents.intents}
    if (
        (
            type(model_visible_concept_ids) is not tuple
            or not 1 <= len(model_visible_concept_ids) <= 8
            or any(type(cid) is not str for cid in model_visible_concept_ids)
            or len(set(model_visible_concept_ids)) != len(model_visible_concept_ids)
            or not set(model_visible_concept_ids) <= approved_concepts.keys()
        )
        or type(model_visible_intent_ids) is not tuple
        or not 1 <= len(model_visible_intent_ids) <= 16
        or any(type(iid) is not str for iid in model_visible_intent_ids)
        or len(set(model_visible_intent_ids)) != len(model_visible_intent_ids)
        or not set(model_visible_intent_ids) <= approved_intents.keys()
        or any(not set(approved_intents[iid].required_concept_ids) <= (
            set(model_visible_concept_ids)
        ) for iid in model_visible_intent_ids)
        or type(model_visible_tool_keys) is not tuple
        or len(model_visible_tool_keys) > 5
        or any(not _bounded_name(name) for name in model_visible_tool_keys)
        or len(set(model_visible_tool_keys)) != len(model_visible_tool_keys)
    ):
        raise ValueError("invalid host-approved model disclosure")

    router = session._router
    witness = router._retrieval_authority_witness()
    session._index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper query requires explicit source policy")
    policy_digest = _policy_contents_digest(policy)
    availability = router._source_availability_predicate()

    def verify() -> None:
        session._index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        try:
            current_owner = (
                catalog.model_dump_json(), intent_registry.model_dump_json(),
                principal.model_dump_json(), host_source_arguments,
                canonical_json_text(host_source_arguments),
                rank_policy.model_dump_json() if rank_policy else None,
            )
            owner_changed = current_owner != before
        except Exception:
            # A model callback may mutate the caller's owned nested Pydantic
            # collection to an unserializable object. Never return that
            # object's type, repr or Pydantic diagnostic to a consumer.
            raise PolicyViolationError("paper query owner authority changed") from None
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or router._source_availability_predicate() is not availability
            or owner_changed
        ):
            raise PolicyViolationError("paper query source or owner authority changed")

    def abstain() -> PaperTypedToolPlan:
        verify()
        return PaperTypedToolPlan(
            status="no_proven_hit", snapshot_id=session.snapshot_id,
            registry_version=witness[1], requested_k=k,
        )

    def finalize(
        plan: PaperTypedToolPlan, parameter_hints: dict[str, Any],
    ) -> PaperTypedToolPlan:
        plan = _apply_query_input_conditions(
            router, plan, principal=principal, parameter_hints=parameter_hints,
            resolve_proposals=False, value_aliases=None, shared_parameter_semantics=None,
        )
        verify()
        return plan

    def compile_hint(understood: PaperUnderstanding) -> PaperTypedToolPlan:
        try:
            plan = session.compile_understood(
                understood, principal=principal, intent_registry=intent_registry,
                host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
                rank_policy=rank_policy,
                allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
            )
        except (ValueError, TypeError):
            verify()
            raise ModelAnalysisError("model understanding could not be compiled") from None
        verify()
        return plan

    # These are owner-reviewed concepts that still have a current, accessible,
    # field-complete proof. Never disclose unreachable concepts to the model.
    offered_concepts = []
    for concept_id in model_visible_concept_ids or ():
        concept = approved_concepts[concept_id]
        try:
            coverage = retrieve_paper_field_coverage(
                router, concept.aliases[0], principal=principal,
                catalog=session._require_catalog(), index=session._index, k=k,
            )
        except ValueError:
            # A catalog alias is not an independent proof of current fields.
            continue
        except Exception:
            raise PolicyViolationError("paper query source eligibility check failed") from None
        verify()
        qualified = coverage.status == "complete"
        if not qualified and coverage.status == "over_k_unranked" and rank_policy:
            # A reviewed concept with >K authorized candidates is still a
            # valid disclosure if the same current native source can rank its
            # complete field contract. No route IDs are offered to the model.
            group = NativeDeclaredFieldGroup(
                aliases=(concept.aliases[0],),
                required_fields=concept.required_fields,
                source_type=concept.source_type, license=concept.license,
            )
            ranked = session._index.field_index.lookup(
                router, concept.aliases[0], principal=principal, group=group,
                k=k, _paper_rank_policy=rank_policy,
                _paper_rank_aliases=(tuple(concept.aliases),),
            )
            qualified = ranked.status in ("complete", "ranked_unverified")
            verify()
        if qualified:
            offered_concepts.append(concept)
    offered_ids = {concept.concept_id for concept in offered_concepts}
    if allow_unnamed_graph_discovery:
        # The ordinary per-concept direct posting preflight deliberately
        # excludes outputs available ONLY through typed two-hop joins. A
        # host-approved unnamed G5 path is also a source-owned field proof,
        # provided the ENTIRE reviewed intent FieldGroup can be satisfied.
        # Reuse the current public plan compiler (including owner domain,
        # source ACL, K5, typed joins and live scope reattestation); do not
        # infer concept eligibility from model text or raw graph topology.
        graph_offered: set[str] = set()
        for intent_id in model_visible_intent_ids:
            required = set(approved_intents[intent_id].required_concept_ids)
            if required <= offered_ids:
                continue
            verify()
            try:
                proof = session.compile_understood(
                    PaperUnderstanding(intent_id=intent_id, named_tools=()),
                    principal=principal, intent_registry=intent_registry,
                    host_source_arguments=host_source_arguments,
                    k=k, max_hops=max_hops, rank_policy=rank_policy,
                    allow_unnamed_graph_discovery=True,
                )
            except Exception:
                raise PolicyViolationError(
                    "paper query G5 intent preflight failed"
                ) from None
            verify()
            if (
                proof.status == "requires_observation"
                and len(proof.calls) in (2, 3)
                and len(proof.bindings) == len(proof.calls) - 1
                and not proof.executable_authority
            ):
                graph_offered.update(required)
        for concept_id in model_visible_concept_ids or ():
            if concept_id in graph_offered and concept_id not in offered_ids:
                offered_concepts.append(approved_concepts[concept_id])
                offered_ids.add(concept_id)
    offered_intents = [
        approved_intents[iid] for iid in model_visible_intent_ids
        if set(approved_intents[iid].required_concept_ids) <= offered_ids
    ]
    if not offered_intents:
        verify()
        return _PreparedModelQuery(
            None, PaperUnderstanding, lambda _decoded: abstain(), verify,
            max_model_input_bytes, max_model_output_bytes,
        )

    # Only host-approved, currently scoped, non-destructive tool identities
    # may reach the model. Schema bodies/hidden route IDs are not disclosed.
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper query lacks source authorization")
    offered_tools: list[str] = []
    for tool_key in model_visible_tool_keys:
        allowed = False
        try:
            tool = router.registry.get(tool_key)
            for endpoint in tool.endpoints:
                if (
                    endpoint.read_only is True and endpoint.destructive is not True
                    and permitted(tool, endpoint)
                    and (availability is None or availability(tool, endpoint))
                    and router._data_scope_endpoint_view(principal, tool, endpoint)
                    is not None
                ):
                    allowed = True
                    break
        except Exception:
            raise ValueError("invalid host-approved model disclosure") from None
        verify()
        if not allowed:
            raise ValueError("invalid host-approved model disclosure")
        offered_tools.append(tool_key)

    payload = {
        "task": "Extract all query information needs and constraints for schema field routing",
        "query": query,
        "offered_intents": [
            {"intent_id": i.intent_id, "required_concept_ids": list(i.required_concept_ids)}
            for i in offered_intents
        ],
        "offered_concepts": [
            {"concept_id": c.concept_id, "aliases": list(c.aliases)}
            for c in offered_concepts
        ],
        "offered_tool_keys": offered_tools,
        "response_fields": [
            "intent_id", "concept_ids", "unresolved_concepts", "source_type",
            "named_tools", "parameter_hints",
        ],
        "response_schema": PaperUnderstanding.model_json_schema(),
        "rules": [
            "Use only offered IDs and offered tool keys; return one JSON object.",
            "Return intent_id=null if no offered intent fits the query.",
            "Keep unmatched needs in unresolved_concepts; never drop a required concept.",
            "Preserve temporal and source constraints; partial matches remain incomplete.",
            "Exclude concepts the user negates; do not add unrelated concepts.",
            "Use named_tools only for tool names stated by the user; otherwise return [].",
            "Set source_type only for an explicit source-type constraint; otherwise use null.",
            "Extract parameter_hints from the query; they never authorize execution.",
            "Never invent fields, values, credentials or permissions, or invoke providers.",
        ],
    }
    def compile_offered(decoded: PaperQueryUnderstanding | PaperUnderstanding):
        assert isinstance(decoded, PaperUnderstanding)
        if (
            decoded.intent_id is not None
            and decoded.intent_id not in {i.intent_id for i in offered_intents}
            or not set(decoded.concept_ids) <= offered_ids
            or not set(decoded.named_tools) <= set(offered_tools)
        ):
            raise ModelAnalysisError("model selected unoffered paper identities")
        if decoded.intent_id is None:
            plan = abstain()
        else:
            plan = compile_hint(decoded)
        if plan.coverage is None:
            plan = replace(plan, coverage=_owner_query_field_coverage(
                decoded, concepts=approved_concepts, intents=approved_intents,
                source_proven=bool(plan.calls) and plan.status in {
                    "ready", "requires_arguments", "requires_observation",
                },
            ))
        plan = replace(plan, understanding_hints=decoded.model_dump(mode="json"))
        return finalize(plan, decoded.parameter_hints)

    return _PreparedModelQuery(
        payload, PaperUnderstanding, compile_offered, verify,
        max_model_input_bytes, max_model_output_bytes,
    )
