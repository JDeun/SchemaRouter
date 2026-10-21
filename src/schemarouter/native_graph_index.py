"""G5 E0: use one versioned native schema catalog and the canonical typed graph.

The registry remains the only source of tool truth. The dependency graph
is built from source-owned scalar ID outputs and exact required inputs;
current principal/policy/data visibility is enforced BEFORE graph evidence
leaves this opt-in research retrieval. No model, agent or execution logic.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
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
# Absolute research-only model exposure cap; never silently widen fixed K5.
MAX_RESEARCH_RANKABLE_PATHS = 32


def _root_envelope_empty(endpoint: EndpointSpec) -> bool:
    if endpoint.parameters or endpoint.auth_requirements:
        return False
    return not endpoint.input_schema or endpoint.input_schema in (
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": [],
         "additionalProperties": False},
    )

def _host_source_input_names(endpoint: EndpointSpec) -> tuple[str, ...] | None:
    """Only an original, closed 1-4 required scalar source input envelope.

    Semantic meaning of source arguments and their values is HOST supplied.
    This function does not trust free text or source descriptions to add values.
    """
    if not 1 <= len(endpoint.parameters) <= 4 or endpoint.auth_requirements:
        return None
    for param in endpoint.parameters:
        if (
            not param.required
            or param.location in {"header", "body_root"}
            or not _scalar_contract(param.json_schema)
        ):
            return None
    names = tuple(param.name for param in endpoint.parameters)
    schema = endpoint.input_schema
    if (
        len(set(names)) != len(names)
        or type(schema) is not dict
        or set(schema) != {"type", "properties", "required"}
        or schema.get("type") != "object"
        or schema.get("properties")
        != {param.name: param.json_schema for param in endpoint.parameters}
        or type(schema.get("required")) is not list
        or len(schema["required"]) != len(names)
        or set(schema["required"]) != set(names)
    ):
        return None
    return names


def _native_required_inputs(
    endpoint: EndpointSpec,
) -> tuple[tuple[str, CapabilityFieldContract], ...] | None:
    """Prove EVERY declared input is a required, source-typed scalar.

    This is a bounded, conservative one-producer/one-consumer binding
    contract, not an argument synthesizer or arbitrary multi-hop executor.
    Optional/untyped/auth parameters and open object schemas remain no-fit.
    """
    if not 1 <= len(endpoint.parameters) <= 4 or endpoint.auth_requirements:
        return None
    mapped: list[tuple[str, CapabilityFieldContract]] = []
    for param in endpoint.parameters:
        if (
            not param.required
            or param.semantic_id is None
            or param.location in {"header", "body_root"}
            or not _scalar_contract(param.json_schema)
        ):
            return None
        mapped.append((
            param.name,
            CapabilityFieldContract(
                semantic_id=param.semantic_id, json_schema=param.json_schema,
            ),
        ))
    names = [name for name, _ in mapped]
    # One name per source-native parameter, no omitted or implicit inputs.
    if len(set(names)) != len(names):
        return None
    schema = endpoint.input_schema
    if schema and (
        type(schema) is not dict
        or set(schema) != {"type", "properties", "required"}
        or schema.get("type") != "object"
        or schema.get("properties")
        != {param.name: param.json_schema for param in endpoint.parameters}
        or type(schema.get("required")) is not list
        or len(schema["required"]) != len(names)
        or set(schema["required"]) != set(names)
    ):
        return None
    return tuple(mapped)


def _root_field(
    endpoint: EndpointSpec,
    required: CapabilityFieldContract,
) -> FieldSpec | None:
    matches = [
        f for f in endpoint.output_fields
        if (
            f.identifier is True and f.semantic_id == required.semantic_id
            and f.unit is None and f.unit_normalization is None
            and _scalar_contract(f.json_schema)
            and (contract := CapabilityFieldContract.from_field(f)) is not None
            and compare_capability_fields(required, contract).status in {
                "exact", "compatible",
            }
        )
    ]
    # Ambiguous producer outputs cannot be trusted to bind an argument.
    return matches[0] if len(matches) == 1 else None


def _flat_same_record_source_contract(
    source: EndpointSpec,
    visible: EndpointSpec,
    producer_fields: tuple[str, ...],
) -> bool:
    """Conservatively prove a multi-input tuple shares ONE required root object.

    A tool's output_fields may describe different array records. Matching
    semantic IDs is insufficient to join them into a single argument set.
    Only explicit, source-declared required scalar root properties qualify.
    """
    original = source.output_schema
    properties = original.get("properties")
    required = original.get("required")
    if (
        original.get("type") != "object"
        or type(properties) is not dict
        or type(required) is not list
        or any(type(name) is not str for name in required)
        or not set(producer_fields).issubset(required)
    ):
        return False
    by_name = {f.name: f for f in visible.output_fields}
    for name in producer_fields:
        field = by_name.get(name)
        declared_property = properties.get(name)
        if (
            field is None
            or field.projection_path != (name,)
            or field.result_projection_path != (name,)
            or type(declared_property) is not dict
            or not _scalar_contract(declared_property)
            or not _scalar_contract(field.json_schema)
            or declared_property != field.json_schema
        ):
            return False
    return True


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphCandidate:
    """Nonexecuting, native original-source-pinned typed one-hop evidence."""

    producer_route_id: str
    consumer_route_id: str
    producer_tool_fingerprint: str
    producer_endpoint_fingerprint: str
    consumer_tool_fingerprint: str
    consumer_endpoint_fingerprint: str
    # Single-binding legacy fields are intentionally absent for multi-input
    # routes, so hosts cannot mistake a partial mapping for a complete one.
    producer_identifier_field: str | None
    consumer_required_parameter: str | None
    consumer_output_fields: tuple[str, ...]
    parameter_bindings: tuple[tuple[str, str], ...] = ()
    source_root_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "ranker_abstained_unverified",
    ]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedGraphCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False
    experimental_ranked: bool = False


@dataclass(frozen=True, slots=True)
class NativeSchemaGraphIndex:
    """Immutable indexed typed dependency graph of one registered source version."""

    field_index: NativeSchemaPostingIndex
    graph: CapabilityDependencyGraph
    native_root_count: int
    native_consumer_count: int
    edge_consumer_routes: frozenset[str]
    approved_host_roots: frozenset[str] = frozenset()

    @classmethod
    def build(
        cls,
        field_index: NativeSchemaPostingIndex,
        *,
        approved_host_roots: frozenset[str] = frozenset(),
    ) -> NativeSchemaGraphIndex:
        """One full native scan at BUILD, not during every query."""
        registry = field_index.registry_ref
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 native source changed before graph build")
        if (
            type(approved_host_roots) is not frozenset
            or len(approved_host_roots) > 64
            or any(type(route) is not str for route in approved_host_roots)
        ):
            raise ValueError("G5 explicit bounded host-approved route set required")
        accepted_host_roots: set[str] = set()
        contracts: list[CapabilityContract] = []
        roots = consumers = 0
        for tool in registry.tools():
            # The full ToolSpec fingerprint already incorporates every
            # endpoint in this detached registry snapshot. Check all
            # endpoints but hash their shared parent only once per tool.
            tool_fingerprint = tool.fingerprint
            tool_key = tool.key
            for endpoint in tool.endpoints:
                route = f"{tool_key}.{endpoint.name}"
                pinned = field_index.route_fingerprints.get(route)
                if pinned != (tool_fingerprint, endpoint.fingerprint):
                    raise PolicyViolationError("G5 source changed during graph build")
                if (
                    not tool.source_type or not tool.license
                    or endpoint.read_only is not True
                    or endpoint.destructive is True
                ):
                    continue
                empty_root = _root_envelope_empty(endpoint)
                host_root = route in approved_host_roots
                if host_root and (
                    empty_root or _host_source_input_names(endpoint) is None
                ):
                    raise ValueError("G5 invalid explicit host-approved source route")
                if empty_root or host_root:
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
                        if host_root:
                            accepted_host_roots.add(route)
                    elif host_root:
                        raise ValueError("G5 host-approved source has no typed output")
                else:
                    required = _native_required_inputs(endpoint)
                    if required is None:
                        continue
                    contracts.append(CapabilityContract(
                        capability_id=route,
                        requires=[contract for _, contract in required],
                    ))
                    consumers += 1
        if accepted_host_roots != approved_host_roots:
            raise ValueError("G5 host-approved source not accepted by current catalog")
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 native source changed during graph build")
        # Reuse the ONE existing canonical semantic-ID producer index and
        # compare_capability_composition; no duplicate graph ranking engine.
        graph = build_capability_dependency_graph(contracts)
        # The canonical graph already proved which consumers have at
        # least one structurally compatible producer. A route absent from
        # this immutable set can NEVER form an eligible G5 one-hop path.
        # Its output semantic posting should not trigger a registry.get.
        edge_consumers = frozenset(edge.consumer_id for edge in graph.edges)
        return cls(
            field_index, graph, roots, consumers, edge_consumers,
            approved_host_roots,
        )

    def lookup(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
        _research_ranker: Callable[
            [str, tuple[NativeIndexedGraphCandidate, ...], int],
            tuple[int, ...],
        ] | None = None,
    ) -> NativeIndexedGraphResult:
        """Discover source-proven typed paths; default remains unranked at >K.

        An explicitly supplied host-owned E0 callback sees only FULLY
        current-authorized and field-scoped graph candidate evidence. Its
        tuple of offered candidate offsets is untrusted and checked after
        the callback, as is current authority. This is NOT a production
        ranking policy, no-fit classifier, or grant of execution authority.
        """
        if type(k) is not int or k != STRICT_K:
            raise ValueError("G5 strict fixed K5 required")
        if _research_ranker is not None and not callable(_research_ranker):
            raise ValueError("G5 experimental ranker must be callable")
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
        # Structural prefilter only; this set is not a permission grant.
        # Every surviving target AND its original source root still gets
        # current authorization, hidden-field and availability checks.
        targets.intersection_update(self.edge_consumer_routes)

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
            required_inputs = _native_required_inputs(endpoint)
            if required_inputs is None:
                continue
            for root_id in self.graph.predecessors(target_id):
                root = authorized(root_id)
                if root is None:
                    continue
                _root_tool, root_endpoint = root
                root_required: tuple[str, ...] = ()
                if not _root_envelope_empty(root_endpoint):
                    if root_id not in self.approved_host_roots:
                        continue
                    declared = _host_source_input_names(
                        _root_tool.endpoint(root_endpoint.name)
                    )
                    if declared is None:
                        continue
                    root_required = declared
                bindings: list[tuple[str, str]] = []
                for parameter, required in required_inputs:
                    field = _root_field(root_endpoint, required)
                    if field is None or field.name in {
                        producer for _, producer in bindings
                    }:
                        break
                    bindings.append((parameter, field.name))
                if len(bindings) != len(required_inputs):
                    continue
                # All scalars must be jointly present on a single source
                # record. Different nested arrays or optional root properties
                # are not an executable multi-input binding proof.
                if len(bindings) > 1 and not _flat_same_record_source_contract(
                    _root_tool.endpoint(root_endpoint.name),
                    root_endpoint,
                    tuple(source_field for _, source_field in bindings),
                ):
                    continue
                source = self.field_index.route_fingerprints[root_id]
                dest = self.field_index.route_fingerprints[target_id]
                names = tuple(sorted({
                    f.name for f in endpoint.output_fields
                    if any(_complete_fields([f], (req,))
                           for req in demand.required_fields)
                }))
                single = len(bindings) == 1
                found.append(NativeIndexedGraphCandidate(
                    producer_route_id=root_id,
                    consumer_route_id=target_id,
                    producer_tool_fingerprint=source[0],
                    producer_endpoint_fingerprint=source[1],
                    consumer_tool_fingerprint=dest[0],
                    consumer_endpoint_fingerprint=dest[1],
                    producer_identifier_field=bindings[0][1] if single else None,
                    consumer_required_parameter=bindings[0][0] if single else None,
                    consumer_output_fields=names,
                    parameter_bindings=tuple(bindings),
                    source_root_parameters=root_required,
                ))
        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        policy = router.authorization_policy
        if policy is None or (
            policy.default_effect, repr(policy.rules), repr(policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError("G5 authorization rules changed during lookup")
        if len(found) > k:
            if (
                _research_ranker is None
                or len(found) > MAX_RESEARCH_RANKABLE_PATHS
            ):
                return NativeIndexedGraphResult(
                    "over_k_unranked", self.field_index.snapshot_id,
                    self.field_index.registry_version, k, len(found), (),
                )
            # All structural, policy, data-scope, visibility, availability
            # and source checks have already completed, BEFORE disclosure.
            # The research callback is UNTRUSTED. Even frozen dataclasses
            # can be mutated with object.__setattr__. Send detached copies:
            # selected outputs must always be drawn from the original
            # source-verified `found` snapshot, never objects the backend held.
            offered = tuple(replace(candidate) for candidate in found)
            chosen = _research_ranker(query, offered, k)
            self.field_index._assert_source(router)
            router._check_retrieval_authority_witness(witness)
            current_policy = router.authorization_policy
            if current_policy is None or (
                current_policy.default_effect,
                repr(current_policy.rules),
                repr(current_policy.data_rules),
            ) != original_policy:
                raise PolicyViolationError(
                    "G5 authorization rules changed during research ranking"
                )
            if (
                type(chosen) is not tuple
                or len(chosen) not in (0, k)
                or any(type(offset) is not int
                       or not 0 <= offset < len(found) for offset in chosen)
                or len(set(chosen)) != len(chosen)
            ):
                raise PolicyViolationError(
                    "G5 research ranker returned forged, partial or duplicate offsets"
                )
            return NativeIndexedGraphResult(
                "ranked_unverified" if chosen
                else "ranker_abstained_unverified",
                self.field_index.snapshot_id,
                self.field_index.registry_version, k, len(found),
                tuple(found[offset] for offset in chosen),
                experimental_ranked=True,
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
