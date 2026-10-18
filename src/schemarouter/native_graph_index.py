"""G5 E0: use one versioned native schema catalog and the canonical typed graph.

The registry remains the only source of tool truth. The dependency graph
is built from source-owned scalar ID outputs and exact required inputs;
current principal/policy/data visibility is enforced BEFORE graph evidence
leaves this opt-in research retrieval. No model, agent or execution logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    compare_capability_fields,
)
from .capability_graph import (
    CapabilityDependencyGraph,
    build_capability_dependency_graph,
)
from .concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from .errors import PolicyViolationError
from .field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _scalar_contract,
)
from .models import EndpointSpec, FieldSpec, ToolSpec
from .native_semantic_index import NativeSchemaPostingIndex

if TYPE_CHECKING:
    from .runtime import SchemaRouter

STRICT_K = 5


def _root_envelope_empty(endpoint: EndpointSpec) -> bool:
    if endpoint.parameters or endpoint.auth_requirements:
        return False
    return not endpoint.input_schema or endpoint.input_schema in (
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": [],
         "additionalProperties": False},
    )


def _single_native_input(endpoint: EndpointSpec) -> CapabilityFieldContract | None:
    """Only one proven required scalar; no hidden defaults or extra parameters."""
    if len(endpoint.parameters) != 1 or endpoint.auth_requirements:
        return None
    param = endpoint.parameters[0]
    if (
        not param.required
        or param.semantic_id is None
        or param.location in {"header", "body_root"}
        or not _scalar_contract(param.json_schema)
    ):
        return None
    schema = endpoint.input_schema
    if schema and (
        type(schema) is not dict
        or set(schema) != {"type", "properties", "required"}
        or schema.get("type") != "object"
        or schema.get("properties") != {param.name: param.json_schema}
        or schema.get("required") != [param.name]
    ):
        return None
    return CapabilityFieldContract(
        semantic_id=param.semantic_id, json_schema=param.json_schema,
    )


def _root_field(
    endpoint: EndpointSpec,
    required: CapabilityFieldContract,
) -> FieldSpec | None:
    for f in endpoint.output_fields:
        if (
            f.identifier is True and f.semantic_id == required.semantic_id
            and f.unit is None and f.unit_normalization is None
            and _scalar_contract(f.json_schema)
            and (contract := CapabilityFieldContract.from_field(f)) is not None
            and compare_capability_fields(required, contract).status in {
                "exact", "compatible",
            }
        ):
            return f
    return None


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphCandidate:
    """Nonexecuting, native original-source-pinned typed one-hop evidence."""

    producer_route_id: str
    consumer_route_id: str
    producer_tool_fingerprint: str
    producer_endpoint_fingerprint: str
    consumer_tool_fingerprint: str
    consumer_endpoint_fingerprint: str
    producer_identifier_field: str
    consumer_required_parameter: str
    consumer_output_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphResult:
    status: Literal["complete", "no_proven_hit", "over_k_unranked"]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedGraphCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


@dataclass(frozen=True, slots=True)
class NativeSchemaGraphIndex:
    """Immutable indexed typed dependency graph of one registered source version."""

    field_index: NativeSchemaPostingIndex
    graph: CapabilityDependencyGraph
    native_root_count: int
    native_consumer_count: int

    @classmethod
    def build(cls, field_index: NativeSchemaPostingIndex) -> NativeSchemaGraphIndex:
        """One full native scan at BUILD, not during every query."""
        registry = field_index.registry_ref
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 native source changed before graph build")
        contracts: list[CapabilityContract] = []
        roots = consumers = 0
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route = f"{tool.key}.{endpoint.name}"
                pinned = field_index.route_fingerprints.get(route)
                if pinned != (tool.fingerprint, endpoint.fingerprint):
                    raise PolicyViolationError("G5 source changed during graph build")
                if (
                    not tool.source_type or not tool.license
                    or endpoint.read_only is not True
                    or endpoint.destructive is True
                ):
                    continue
                if _root_envelope_empty(endpoint):
                    produced = [
                        contract
                        for f in endpoint.output_fields
                        if f.identifier is True and f.unit is None
                        and f.unit_normalization is None
                        and _scalar_contract(f.json_schema)
                        and (contract := CapabilityFieldContract.from_field(f))
                        is not None
                    ]
                    if produced:
                        contracts.append(CapabilityContract(
                            capability_id=route, produces=produced,
                        ))
                        roots += 1
                else:
                    required = _single_native_input(endpoint)
                    if required is None:
                        continue
                    contracts.append(CapabilityContract(
                        capability_id=route, requires=[required],
                    ))
                    consumers += 1
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 native source changed during graph build")
        # Reuse the ONE existing canonical semantic-ID producer index and
        # compare_capability_composition; no duplicate graph ranking engine.
        graph = build_capability_dependency_graph(contracts)
        return cls(field_index, graph, roots, consumers)

    def lookup(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
    ) -> NativeIndexedGraphResult:
        """Discover output-complete targets AND actual typed producer edges."""
        if type(k) is not int or k != STRICT_K:
            raise ValueError("G5 strict fixed K5 required")
        if type(query) is not str or len(query.encode("utf-8")) > 512:
            raise ValueError("G5 invalid bounded query")
        if not isinstance(principal, PrincipalContext):
            raise PolicyViolationError("G5 explicit principal required")
        if not isinstance(group, NativeDeclaredFieldGroup):
            raise ValueError("G5 approved FieldGroup required")
        try:
            demand = NativeDeclaredFieldGroup.model_validate(
                group.model_dump(mode="python"), strict=True,
            )
            actor = PrincipalContext.model_validate(
                principal.model_dump(mode="python"), strict=True,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("G5 invalid current host declarations") from exc
        if _alias_key(query) not in {_alias_key(a) for a in demand.aliases}:
            raise ValueError("G5 query lacks approved semantic edge")
        self.field_index._assert_source(router)
        if router.authorization_policy is None:
            raise PolicyViolationError("G5 explicit policy required")
        witness = router._retrieval_authority_witness()
        original_policy = (
            router.authorization_policy.default_effect,
            repr(router.authorization_policy.rules),
            repr(router.authorization_policy.data_rules),
        )
        # This graph is not authorization-scoped and must never be surfaced
        # directly. All native endpoints are reloaded and checked at lookup.
        permitted = router._authorization_predicate(actor)
        if permitted is None:
            raise PolicyViolationError("G5 explicit authorization required")
        availability = router.planner.availability_predicate
        wanted = [set(self.field_index.postings.get(x.semantic_id, ()))
                  for x in demand.required_fields]
        targets = set.intersection(*wanted) if wanted else set()

        def authorized(route_id: str) -> tuple[ToolSpec, EndpointSpec] | None:
            where = self.field_index.route_locations.get(route_id)
            pinned = self.field_index.route_fingerprints.get(route_id)
            if where is None or pinned is None:
                raise PolicyViolationError("G5 missing pinned native route")
            tool = router.registry.get(where[0])
            endpoint = tool.endpoint(where[1])
            if (tool.fingerprint, endpoint.fingerprint) != pinned:
                raise PolicyViolationError("G5 native route source drift")
            if (
                not tool.source_type or not tool.license
                or endpoint.read_only is not True
                or endpoint.destructive is True
                or not permitted(tool, endpoint)
                or availability is not None and not availability(tool, endpoint)
            ):
                return None
            scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
            return (tool, scoped) if scoped is not None else None

        found: list[NativeIndexedGraphCandidate] = []
        for target_id in sorted(targets):
            target = authorized(target_id)
            if target is None:
                continue
            target_tool, endpoint = target
            if (demand.source_type is not None
                    and target_tool.source_type != demand.source_type
                    or demand.license is not None
                    and target_tool.license != demand.license
                    or not _complete_fields(
                        endpoint.output_fields, demand.required_fields,
                    )):
                continue
            required = _single_native_input(endpoint)
            if required is None:
                continue
            for root_id in self.graph.predecessors(target_id):
                root = authorized(root_id)
                if root is None:
                    continue
                _root_tool, root_endpoint = root
                if not _root_envelope_empty(root_endpoint):
                    continue
                field = _root_field(root_endpoint, required)
                if field is None:
                    continue
                source = self.field_index.route_fingerprints[root_id]
                dest = self.field_index.route_fingerprints[target_id]
                names = tuple(sorted({
                    f.name for f in endpoint.output_fields
                    if any(_complete_fields([f], (req,))
                           for req in demand.required_fields)
                }))
                found.append(NativeIndexedGraphCandidate(
                    producer_route_id=root_id,
                    consumer_route_id=target_id,
                    producer_tool_fingerprint=source[0],
                    producer_endpoint_fingerprint=source[1],
                    consumer_tool_fingerprint=dest[0],
                    consumer_endpoint_fingerprint=dest[1],
                    producer_identifier_field=field.name,
                    consumer_required_parameter=endpoint.parameters[0].name,
                    consumer_output_fields=names,
                ))
        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        policy = router.authorization_policy
        if policy is None or (
            policy.default_effect, repr(policy.rules), repr(policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError("G5 authorization rules changed during lookup")
        if len(found) > k:
            return NativeIndexedGraphResult(
                "over_k_unranked", self.field_index.snapshot_id,
                self.field_index.registry_version, k, len(found), (),
            )
        return NativeIndexedGraphResult(
            "complete" if found else "no_proven_hit",
            self.field_index.snapshot_id,
            self.field_index.registry_version, k, len(found), tuple(found),
        )

    def lookup_concepts(
        self,
        router: SchemaRouter,
        query: str,
        *,
        catalog: NativeConceptCatalog,
        principal: PrincipalContext,
        k: int = STRICT_K,
    ) -> NativeIndexedGraphResult:
        resolved = resolve_native_concepts(query, catalog=catalog)
        return self.lookup(
            router, query, group=resolved.field_group, principal=principal, k=k,
        )
