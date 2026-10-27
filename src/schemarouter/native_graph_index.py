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
    update_capability_dependency_graph,
)
from .concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from .errors import PolicyViolationError, RegistrationError
from .field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
    _scalar_contract,
)
from .models import EndpointSpec, FieldSpec, ToolSpec
from .native_semantic_index import NativeSchemaPostingIndex
from .registry import InMemoryRegistry, SQLiteRegistry, ToolRegistry

if TYPE_CHECKING:
    from .native_deep_paths import NativeIndexedPathResult
    from .native_fork_index import NativeIndexedSharedRootForkResult
    from .runtime import SchemaRouter

STRICT_K = 5
# Absolute research-only model exposure cap; never silently widen fixed K5.
MAX_RESEARCH_RANKABLE_PATHS = 32


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
            or not (
                _scalar_contract(param.json_schema)
                or (
                    param.name == "id"
                    and param.location == "path"
                    and param.json_schema == {"type": "string", "minLength": 1}
                )
            )
        ):
            return None
    names = tuple(param.name for param in endpoint.parameters)
    schema = endpoint.input_schema
    if (
        len(set(names)) != len(names)
        or type(schema) is not dict
        or set(schema) not in (
            {"type", "properties", "required"},
            {"type", "properties", "required", "additionalProperties"},
        )
        or schema.get("additionalProperties", False) is not False
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
        or set(schema) not in (
            {"type", "properties", "required"},
            {"type", "properties", "required", "additionalProperties"},
        )
        or schema.get("additionalProperties", False) is not False
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
        "internal_fork_arm",
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
class NativeIndexedTwoHopCandidate:
    """Three current source-native routes, two verified typed joins, no execution."""

    route_ids: tuple[str, str, str]
    route_fingerprints: tuple[tuple[str, str], tuple[str, str], tuple[str, str]]
    root_to_intermediate: tuple[tuple[str, str], ...]
    intermediate_to_target: tuple[tuple[str, str], ...]
    target_output_fields: tuple[str, ...]
    source_root_parameters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeIndexedTwoHopResult:
    status: Literal["complete", "no_proven_hit", "over_k_unranked"]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedTwoHopCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


def _source_native_graph_contracts(
    tool: ToolSpec,
    approved_host_roots: frozenset[str],
) -> tuple[list[CapabilityContract], int, int, set[str]]:
    """Only the old canonical G5 root/consumer proof, for one current tool."""
    contracts: list[CapabilityContract] = []
    roots = consumers = 0
    accepted: set[str] = set()
    if not tool.source_type or not tool.license:
        return contracts, roots, consumers, accepted
    for endpoint in tool.endpoints:
        route = f"{tool.key}.{endpoint.name}"
        if endpoint.read_only is not True or endpoint.destructive is True:
            continue
        empty_root = _root_envelope_empty(endpoint)
        host_root = route in approved_host_roots
        if host_root and (
            empty_root or _host_source_input_names(endpoint) is None
        ):
            raise ValueError("G5 invalid explicit host-approved source route")
        if host_root and tool.source_type == "optimade":
            # A provider-discovered OPTIMADE ID is not automatically a trusted
            # graph root: only the host review receipt may authorize this
            # bounded minLength=1 ID contract for original-paper planning.
            review = tool.metadata.get("paper_optimade_review")
            output_fields = {field.name: field for field in endpoint.output_fields}
            identifier = next(
                (parameter for parameter in endpoint.parameters if parameter.name == "id"),
                None,
            )
            if (
                not isinstance(review, dict)
                or not isinstance(review.get("source_tool_fingerprint"), str)
                or not review.get("source_tool_fingerprint")
                or review.get("source_base_url") != tool.metadata.get("versioned_base_url")
                or review.get("entry_type") != endpoint.execution_metadata.get("entry_type")
                or not isinstance(review.get("reviewed_fields"), dict)
                or any(
                    name not in output_fields
                    or output_fields[name].semantic_id != semantic_id
                    for name, semantic_id in review["reviewed_fields"].items()
                )
                or not review.get("identifier_semantic_id")
                or identifier is None
                or identifier.semantic_id != review.get("identifier_semantic_id")
                or output_fields.get("id") is None
                or output_fields["id"].semantic_id != review.get("identifier_semantic_id")
            ):
                raise ValueError("G5 invalid explicit host-approved source route")
        if empty_root or host_root:
            produced = [
                contract
                for field in endpoint.output_fields
                if field.identifier is True and field.unit is None
                and field.unit_normalization is None
                and _scalar_contract(field.json_schema)
                and (contract := CapabilityFieldContract.from_field(field))
                is not None
            ]
            if produced:
                contracts.append(CapabilityContract(
                    capability_id=route, produces=produced,
                ))
                roots += 1
                if host_root:
                    accepted.add(route)
            elif host_root:
                # A reviewed remote source may expose a genuine scalar value
                # (for example MCP `result: string`) without an identifier.
                # Such a route is eligible for source-owned *direct* P2
                # lookup, but MUST NOT become a dependency producer: graph
                # consumers can bind only genuine identifier fields.
                scalar_output = any(
                    field.unit is None and field.unit_normalization is None
                    and _scalar_contract(field.json_schema)
                    and CapabilityFieldContract.from_field(field) is not None
                    for field in endpoint.output_fields
                )
                if not scalar_output:
                    raise ValueError("G5 host-approved source has no typed output")
                contracts.append(CapabilityContract(capability_id=route))
                roots += 1
                accepted.add(route)
        else:
            required = _native_required_inputs(endpoint)
            if required is not None:
                # Source-native intermediate routes can BOTH consume typed
                # identifiers and produce new identifiers. The canonical
                # graph must preserve both edges for opt-in two-hop lookup;
                # they are never accepted as zero-input roots by default.
                produced = [
                    contract
                    for field in endpoint.output_fields
                    if field.identifier is True and field.unit is None
                    and field.unit_normalization is None
                    and _scalar_contract(field.json_schema)
                    and (contract := CapabilityFieldContract.from_field(field))
                    is not None
                ]
                contracts.append(CapabilityContract(
                    capability_id=route,
                    requires=[contract for _, contract in required],
                    produces=produced,
                ))
                consumers += 1
    return contracts, roots, consumers, accepted


@dataclass(frozen=True, slots=True)
class NativeSchemaGraphIndex:
    """Immutable indexed typed dependency graph of one registered source version."""

    field_index: NativeSchemaPostingIndex
    graph: CapabilityDependencyGraph
    native_root_count: int
    native_consumer_count: int
    edge_consumer_routes: frozenset[str]
    approved_host_roots: frozenset[str] = frozenset()
    # Private source-derived contracts from exact index build, not user gold.
    # Required to reuse the EXISTING canonical incremental edge updater.
    _source_contracts: tuple[CapabilityContract, ...] = ()

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
            # Verify the original registry snapshot before projecting native
            # G5 root/consumer contracts; this is an all-tool BUILD scan.
            tool_fingerprint = tool.fingerprint
            if field_index.tool_fingerprints.get(tool.key) != tool_fingerprint:
                raise PolicyViolationError("G5 source changed during graph build")
            for endpoint in tool.endpoints:
                route = f"{tool.key}.{endpoint.name}"
                if field_index.route_fingerprints.get(route) != (
                    tool_fingerprint, endpoint.fingerprint,
                ):
                    raise PolicyViolationError("G5 source changed during graph build")
            portion, new_roots, new_consumers, accepted = (
                _source_native_graph_contracts(tool, approved_host_roots)
            )
            contracts.extend(portion)
            roots += new_roots
            consumers += new_consumers
            accepted_host_roots.update(accepted)
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
            tuple(sorted(contracts, key=lambda item: item.capability_id)),
        )

    @classmethod
    def refresh(
        cls,
        previous: NativeSchemaGraphIndex,
        field_index: NativeSchemaPostingIndex,
        *,
        changed_tool_keys: tuple[str, ...],
    ) -> NativeSchemaGraphIndex:
        """Canonical incremental edge update for a verified posting delta.

        Only original-source root/consumer contracts for named changed tools
        are re-derived. The previous graph and unchanged contracts are
        reused by update_capability_dependency_graph, never a second edge
        comparator. The posting refresh is responsible for the full
        tool-fingerprint manifest check, not the caller's change hints.
        """
        old = previous.field_index
        registry = field_index.registry_ref
        if old.registry_ref is not registry:
            raise PolicyViolationError("G5 graph refresh source mismatch")
        if field_index.registry_version <= old.registry_version:
            raise PolicyViolationError("G5 graph refresh needs a newer source")
        if (
            type(changed_tool_keys) is not tuple
            or not 1 <= len(changed_tool_keys) <= 64
            or any(type(key) is not str or not key for key in changed_tool_keys)
            or len(set(changed_tool_keys)) != len(changed_tool_keys)
        ):
            raise ValueError("G5 graph refresh needs bounded changed-tool keys")
        changed = set(changed_tool_keys)
        if changed != {
            key
            for key in set(old.tool_fingerprints) | set(field_index.tool_fingerprints)
            if old.tool_fingerprints.get(key) != field_index.tool_fingerprints.get(key)
        }:
            raise PolicyViolationError("G5 graph refresh changed-key mismatch")
        # Do not trust a newer version label alone: verify that an immutable
        # posting delta really matches every current native source fingerprint.
        # This remains O(all tools) until the registry has atomic receipts.
        current_keys = registry.keys()
        if set(current_keys) != set(field_index.tool_fingerprints):
            raise PolicyViolationError("G5 graph refresh incomplete source manifest")
        for key in current_keys:
            if registry.get(key).fingerprint != field_index.tool_fingerprints[key]:
                raise PolicyViolationError("G5 graph refresh source fingerprint drift")
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 graph refresh source changed")

        return cls._refresh_changed_contracts(
            previous, field_index, changed_tool_keys,
        )

    @classmethod
    def refresh_from_inmemory_journal(
        cls,
        previous: NativeSchemaGraphIndex,
        registry: ToolRegistry,
    ) -> NativeSchemaGraphIndex:
        """Refresh canonical G5 graph edges from exact in-memory source receipts.

        Only the builtin InMemoryRegistry's lock-atomic change history is
        trusted. SQLite, proxies and user-managed registries continue to
        require the full-fingerprint-verified refresh API.
        """
        if not isinstance(registry, InMemoryRegistry) or type(registry) is not InMemoryRegistry:
            raise PolicyViolationError("G5 journal graph requires exact in-memory source")
        return cls._refresh_from_source_journal(previous, registry, sqlite=False)

    @classmethod
    def refresh_from_sqlite_journal(
        cls,
        previous: NativeSchemaGraphIndex,
        registry: ToolRegistry,
    ) -> NativeSchemaGraphIndex:
        """E0 original SQLite journal verified one-hop G5 edge delta.

        Opt-in only for the *exact* builtin SQLiteRegistry backed by a
        trusted, API-owned database. An externally writable DB can forge
        syntactically complete journals and is out of this E0 trust model.
        """
        if not isinstance(registry, SQLiteRegistry) or type(registry) is not SQLiteRegistry:
            raise PolicyViolationError("G5 journal graph requires exact SQLite source")
        return cls._refresh_from_source_journal(previous, registry, sqlite=True)

    @classmethod
    def _refresh_from_source_journal(
        cls,
        previous: NativeSchemaGraphIndex,
        registry: InMemoryRegistry | SQLiteRegistry,
        *,
        sqlite: bool,
    ) -> NativeSchemaGraphIndex:
        """Canonical delta on a pinned source-owned atomic changed-key receipt."""
        if previous.field_index.registry_ref is not registry:
            raise PolicyViolationError("G5 journal graph source mismatch")
        try:
            receipt = registry.changed_tool_keys_since(
                previous.field_index.registry_version,
            )
        except RegistrationError:
            raise PolicyViolationError(
                "G5 journal graph history unavailable; full build required"
            ) from None
        if (
            receipt.from_version != previous.field_index.registry_version
            or receipt.to_version <= receipt.from_version
            or not 1 <= len(receipt.changed_tool_keys) <= 64
        ):
            raise PolicyViolationError("G5 journal graph invalid versioned changes")
        field_index = (
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(
                previous.field_index, registry,
            ) if sqlite else NativeSchemaPostingIndex.refresh_from_inmemory_journal(
                previous.field_index, registry,
            )
        )
        if (
            field_index.registry_version != receipt.to_version
            or registry.version != receipt.to_version
        ):
            raise PolicyViolationError("G5 journal graph source changed mid-refresh")
        return cls._refresh_changed_contracts(
            previous, field_index, receipt.changed_tool_keys,
        )

    @classmethod
    def _refresh_changed_contracts(
        cls,
        previous: NativeSchemaGraphIndex,
        field_index: NativeSchemaPostingIndex,
        changed_tool_keys: tuple[str, ...],
    ) -> NativeSchemaGraphIndex:
        """Canonical edge-delta assembler, shared by verified refresh arms."""
        old = previous.field_index
        registry = field_index.registry_ref
        if old.registry_ref is not registry:
            raise PolicyViolationError("G5 graph delta source mismatch")
        if field_index.registry_version <= old.registry_version:
            raise PolicyViolationError("G5 graph delta needs newer source")
        if (
            type(changed_tool_keys) is not tuple
            or not 1 <= len(changed_tool_keys) <= 64
            or any(type(key) is not str or not key for key in changed_tool_keys)
            or len(set(changed_tool_keys)) != len(changed_tool_keys)
        ):
            raise ValueError("G5 graph delta needs bounded changed tool keys")
        changed = set(changed_tool_keys)
        kept = [
            contract.model_copy(deep=True)
            for contract in previous._source_contracts
            if old.route_locations.get(contract.capability_id, ("", ""))[0]
            not in changed
        ]
        old_contract_routes = {contract.capability_id for contract in kept}
        # An in-memory sidecar is only useful when it matches the graph's
        # recorded node set and stable unchanged source routes.
        if (
            {contract.capability_id for contract in previous._source_contracts}
            != set(previous.graph.capability_ids)
            or not old_contract_routes.issubset(field_index.route_locations)
        ):
            raise PolicyViolationError("G5 graph refresh corrupt prior contracts")
        accepted_host_roots = set(previous.approved_host_roots) - {
            route for route in previous.approved_host_roots
            if old.route_locations.get(route, ("", ""))[0] in changed
        }
        roots = sum(bool(contract.produces) and not contract.requires for contract in kept)
        consumers = sum(bool(contract.requires) for contract in kept)
        for key in changed_tool_keys:
            if key not in field_index.tool_fingerprints:
                continue
            tool = registry.get(key)
            pinned = field_index.tool_fingerprints[key]
            if tool.fingerprint != pinned:
                raise PolicyViolationError("G5 graph refresh changed tool drift")
            for endpoint in tool.endpoints:
                if field_index.route_fingerprints.get(
                    f"{key}.{endpoint.name}"
                ) != (pinned, endpoint.fingerprint):
                    raise PolicyViolationError("G5 graph refresh endpoint drift")
            portion, nr, nc, accepted = _source_native_graph_contracts(
                tool, previous.approved_host_roots,
            )
            kept.extend(portion)
            roots += nr
            consumers += nc
            accepted_host_roots.update(accepted)
        if accepted_host_roots != previous.approved_host_roots:
            raise ValueError("G5 approved host source removed or changed")
        updated = update_capability_dependency_graph(
            previous.graph,
            list(previous._source_contracts),
            kept,
        )
        if registry.version != field_index.registry_version:
            raise PolicyViolationError("G5 graph refresh source changed")
        edge_consumers = frozenset(edge.consumer_id for edge in updated.edges)
        return cls(
            field_index, updated, roots, consumers, edge_consumers,
            previous.approved_host_roots,
            tuple(sorted(kept, key=lambda item: item.capability_id)),
        )

    def lookup(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
        allowed_target_routes: frozenset[str] | None = None,
        _research_ranker: Callable[
            [str, tuple[NativeIndexedGraphCandidate, ...], int],
            tuple[int, ...],
        ] | None = None,
    ) -> NativeIndexedGraphResult:
        """Public G5 lookup: strict K5, never exposes private fork arms."""
        return self._lookup_native_paths(
            router, query, group=group, principal=principal, k=k,
            allowed_target_routes=allowed_target_routes,
            _research_ranker=_research_ranker,
        )

    def _lookup_native_paths(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
        allowed_target_routes: frozenset[str] | None = None,
        _research_ranker: Callable[
            [str, tuple[NativeIndexedGraphCandidate, ...], int],
            tuple[int, ...],
        ] | None = None,
        _fork_arm_internal: bool = False,
        _fork_root_filter: frozenset[str] | None = None,
        _fork_target_filter: frozenset[str] | None = None,
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
        if allowed_target_routes is not None and (
            type(allowed_target_routes) is not frozenset
            or len(allowed_target_routes) > MAX_RESEARCH_RANKABLE_PATHS
            or any(
                type(route) is not str or not 1 <= len(route) <= 320
                for route in allowed_target_routes
            )
        ):
            raise ValueError("G5 invalid bounded target route prefilter")
        if _research_ranker is not None and not callable(_research_ranker):
            raise ValueError("G5 experimental ranker must be callable")
        if type(_fork_arm_internal) is not bool or (
            _fork_arm_internal and _research_ranker is not None
        ):
            raise ValueError("G5 internal fork arm forbids external ranking")
        if _fork_root_filter is not None and (
            not _fork_arm_internal
            or type(_fork_root_filter) is not frozenset
            or any(type(route) is not str for route in _fork_root_filter)
        ):
            raise ValueError("G5 root prefilter requires private typed fork mode")
        if _fork_target_filter is not None and (
            not _fork_arm_internal
            or type(_fork_target_filter) is not frozenset
            or any(type(route) is not str for route in _fork_target_filter)
        ):
            raise ValueError("G5 consumer prefilter requires private typed fork mode")
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
        if allowed_target_routes is not None:
            # Model/host target IDs only NARROW graph structure before K;
            # normal principal, scope, source and typed checks still apply.
            targets.intersection_update(allowed_target_routes)
        if _fork_target_filter is not None:
            # Candidate-only optimization; current authorization is NEVER
            # inferred from route IDs supplied to the private collector.
            targets.intersection_update(_fork_target_filter)

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
            ):
                return None
            # The first pass must be as private as the final recheck: an
            # untrusted health callback may throw or return a value whose
            # truthiness evaluation raises with provider-owned information.
            if availability is not None:
                try:
                    available_now = bool(availability(tool, endpoint))
                except Exception:
                    raise PolicyViolationError(
                        "G5 availability check failed during lookup"
                    ) from None
                if not available_now:
                    return None
            scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
            return (tool, scoped) if scoped is not None else None

        found: list[NativeIndexedGraphCandidate] = []
        for target_id in sorted(targets):
            # Source-graph-only optimization, NOT an authorization grant.
            # Skip routes whose typed indexed producers cannot be part of a
            # two-field common-root fork; authorization remains downstream.
            if _fork_root_filter is not None and not any(
                root in _fork_root_filter
                for root in self.graph.predecessors(target_id)
            ):
                continue
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
                if (_fork_root_filter is not None
                        and root_id not in _fork_root_filter):
                    continue
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
        # The availability predicate can be the SAME callable while its
        # underlying live health set changes during a multi-route lookup.
        # Revalidate *all* qualified paths before publishing either a
        # candidate OR the qualified count, including over-K abstention.
        # A registry version/authorization witness alone cannot detect
        # closure-state revocation from another candidate's callback.
        try:
            for candidate in found:
                root_now = authorized(candidate.producer_route_id)
                target_now = authorized(candidate.consumer_route_id)
                if root_now is None or target_now is None:
                    raise PolicyViolationError("G5 candidate no longer available")
                _root_tool_now, root_ep_now = root_now
                _target_tool_now, target_ep_now = target_now
                if not _complete_fields(
                    target_ep_now.output_fields, demand.required_fields,
                ):
                    raise PolicyViolationError("G5 candidate scope changed")
                visible_names = tuple(sorted({
                    field.name for field in target_ep_now.output_fields
                    if any(
                        _complete_fields([field], (required,))
                        for required in demand.required_fields
                    )
                }))
                if visible_names != candidate.consumer_output_fields:
                    raise PolicyViolationError("G5 candidate projection changed")
                # A later health/scope callback may keep source identities
                # stable while withdrawing a previously proven typed join.
                # The default (unranked) K5 path needs the same binding proof
                # already required after an optional research ranker.
                current_inputs = _native_required_inputs(target_ep_now)
                if (
                    current_inputs is None
                    or len(current_inputs) != len(candidate.parameter_bindings)
                    or any(
                        required_name != bound_name
                        or (field := _root_field(root_ep_now, contract))
                        is None or field.name != bound_field
                        for (required_name, contract), (bound_name, bound_field)
                        in zip(
                            current_inputs, candidate.parameter_bindings,
                            strict=True,
                        )
                    )
                ):
                    raise PolicyViolationError("G5 candidate binding changed")
                if len(candidate.parameter_bindings) > 1 and not (
                    _flat_same_record_source_contract(
                        _root_tool_now.endpoint(root_ep_now.name),
                        root_ep_now,
                        tuple(field for _, field in candidate.parameter_bindings),
                    )
                ):
                    raise PolicyViolationError("G5 candidate record contract changed")
        except Exception:
            # A native provider callback may embed private field names or
            # endpoint IDs in exceptions. Never forward that message.
            raise PolicyViolationError(
                "G5 candidate eligibility changed during lookup"
            ) from None
        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        policy = router.authorization_policy
        if policy is None or (
            policy.default_effect, repr(policy.rules), repr(policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError("G5 authorization rules changed during lookup")
        if len(found) > k:
            # Source-private composition mode: authorize and recheck each
            # one-hop witness exactly as in ordinary G5, but do NOT apply
            # final public K to each arm before proving the shared root.
            # Never expose >K arms from ordinary lookup or return >32 arms.
            if _fork_arm_internal:
                if len(found) > MAX_RESEARCH_RANKABLE_PATHS:
                    return NativeIndexedGraphResult(
                        "over_k_unranked", self.field_index.snapshot_id,
                        self.field_index.registry_version, k, len(found), (),
                    )
                return NativeIndexedGraphResult(
                    "internal_fork_arm", self.field_index.snapshot_id,
                    self.field_index.registry_version, k, len(found), tuple(found),
                )
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
            # A caller-owned availability callable can change state without
            # changing its object identity (or registry/policy version) while
            # the untrusted research ranker runs. Recheck ALL at-most-32
            # originally qualified paths, not only the chosen K, because
            # qualified_path_count is also published to the caller.
            # These checks never grant access or invoke source tools.
            try:
                for candidate in found:
                    current_root = authorized(candidate.producer_route_id)
                    current_target = authorized(candidate.consumer_route_id)
                    if current_root is None or current_target is None:
                        raise PolicyViolationError(
                            "G5 source eligibility changed during research ranking"
                        )
                    source_tool, source_endpoint = current_root
                    _target_tool, target_endpoint = current_target
                    if not _complete_fields(
                        target_endpoint.output_fields, demand.required_fields,
                    ):
                        raise PolicyViolationError(
                            "G5 visible field contract changed during research ranking"
                        )
                    current_inputs = _native_required_inputs(target_endpoint)
                    if (
                        current_inputs is None
                        or len(current_inputs) != len(candidate.parameter_bindings)
                        or any(
                            required_name != bound_name
                            or (field := _root_field(source_endpoint, contract))
                            is None or field.name != bound_field
                            for (required_name, contract), (bound_name, bound_field)
                            in zip(
                                current_inputs, candidate.parameter_bindings,
                                strict=True,
                            )
                        )
                    ):
                        raise PolicyViolationError(
                            "G5 source binding changed during research ranking"
                        )
                    if len(candidate.parameter_bindings) > 1 and not (
                        _flat_same_record_source_contract(
                            source_tool.endpoint(source_endpoint.name),
                            source_endpoint,
                            tuple(field for _, field in candidate.parameter_bindings),
                        )
                    ):
                        raise PolicyViolationError(
                            "G5 source record contract changed during research ranking"
                        )
                    public_names = tuple(sorted({
                        field.name for field in target_endpoint.output_fields
                        if any(
                            _complete_fields([field], (required,))
                            for required in demand.required_fields
                        )
                    }))
                    if public_names != candidate.consumer_output_fields:
                        raise PolicyViolationError(
                            "G5 source projection changed during research ranking"
                        )
            except Exception:
                # Source/host callbacks may contain private route/field text
                # in an exception. Never expose it through this optional API.
                raise PolicyViolationError(
                    "G5 authorized graph changed during research ranking"
                ) from None
            self.field_index._assert_source(router)
            router._check_retrieval_authority_witness(witness)
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


    def lookup_two_hop(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
        allowed_target_routes: frozenset[str] | None = None,
    ) -> NativeIndexedTwoHopResult:
        """Opt-in E0: root -> typed intermediary -> target, without execution.

        Reuses the existing canonical source graph and index. Every endpoint
        and both join maps must be current, source-pinned, principal-visible,
        and explicitly typed. No unknown input, mixed-record join, inferred
        alias, unapproved parameterized root or model-driven path is allowed.
        """
        if type(k) is not int or k != STRICT_K:
            raise ValueError("G5 two-hop strict fixed K5 required")
        if allowed_target_routes is not None and (
            type(allowed_target_routes) is not frozenset
            or len(allowed_target_routes) > MAX_RESEARCH_RANKABLE_PATHS
            or any(
                type(route) is not str or not 1 <= len(route) <= 320
                for route in allowed_target_routes
            )
        ):
            raise ValueError("G5 two-hop invalid bounded target route prefilter")
        if type(query) is not str or len(query.encode("utf-8")) > 512:
            raise ValueError("G5 two-hop invalid bounded query")
        if not isinstance(group, NativeDeclaredFieldGroup):
            raise ValueError("G5 two-hop host FieldGroup required")
        if not isinstance(principal, PrincipalContext):
            raise PolicyViolationError("G5 two-hop explicit principal required")
        try:
            demand = NativeDeclaredFieldGroup.model_validate(
                group.model_dump(mode="python"), strict=True,
            )
            actor = PrincipalContext.model_validate(
                principal.model_dump(mode="python"), strict=True,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("G5 two-hop invalid current declarations") from exc
        if _alias_key(query) not in {_alias_key(a) for a in demand.aliases}:
            raise ValueError("G5 two-hop query lacks approved semantic edge")
        self.field_index._assert_source(router)
        if router.authorization_policy is None:
            raise PolicyViolationError("G5 two-hop explicit authorization policy required")
        witness = router._retrieval_authority_witness()
        original_policy = (
            router.authorization_policy.default_effect,
            repr(router.authorization_policy.rules),
            repr(router.authorization_policy.data_rules),
        )
        permitted = router._authorization_predicate(actor)
        if permitted is None:
            raise PolicyViolationError("G5 two-hop explicit authorization required")
        availability = router.planner.availability_predicate

        def authorized(route: str) -> tuple[ToolSpec, EndpointSpec] | None:
            where = self.field_index.route_locations.get(route)
            pinned = self.field_index.route_fingerprints.get(route)
            if where is None or pinned is None:
                raise PolicyViolationError("G5 two-hop original route missing")
            tool = router.registry.get(where[0])
            endpoint = tool.endpoint(where[1])
            if (tool.fingerprint, endpoint.fingerprint) != pinned:
                raise PolicyViolationError("G5 two-hop original source changed")
            if (
                not tool.source_type or not tool.license
                or endpoint.read_only is not True or endpoint.destructive is True
                or not permitted(tool, endpoint)
            ):
                return None
            if availability is not None and not bool(availability(tool, endpoint)):
                return None
            scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
            return (tool, scoped) if scoped is not None else None

        def bind(
            source_tool: ToolSpec,
            source: EndpointSpec,
            consumer: EndpointSpec,
        ) -> tuple[tuple[str, str], ...] | None:
            inputs = _native_required_inputs(consumer)
            if inputs is None:
                return None
            found_bindings: list[tuple[str, str]] = []
            for parameter, required in inputs:
                field = _root_field(source, required)
                if (
                    field is None or field.name in {
                        name for _, name in found_bindings
                    }
                ):
                    return None
                found_bindings.append((parameter, field.name))
            result = tuple(found_bindings)
            if len(result) > 1 and not _flat_same_record_source_contract(
                source_tool.endpoint(source.name), source,
                tuple(field for _, field in result),
            ):
                return None
            return result

        def root_inputs(
            route: str, tool: ToolSpec, endpoint: EndpointSpec,
        ) -> tuple[str, ...] | None:
            if _root_envelope_empty(endpoint):
                return ()
            if route not in self.approved_host_roots:
                return None
            return _host_source_input_names(tool.endpoint(endpoint.name))

        wanted = [
            set(self.field_index.postings.get(field.semantic_id, ()))
            for field in demand.required_fields
        ]
        targets = set.intersection(*wanted) if wanted else set()
        targets.intersection_update(self.edge_consumer_routes)
        if allowed_target_routes is not None:
            targets.intersection_update(allowed_target_routes)
        qualified: list[NativeIndexedTwoHopCandidate] = []

        # Query the indexed predecessor lists only. This does not enumerate
        # the full registered catalog or grant any source execution access.
        try:
            for target_id in sorted(targets):
                target = authorized(target_id)
                if target is None:
                    continue
                target_tool, target_ep = target
                if (
                    demand.source_type is not None
                    and target_tool.source_type != demand.source_type
                    or demand.license is not None
                    and target_tool.license != demand.license
                    or not _complete_fields(
                        target_ep.output_fields, demand.required_fields,
                    )
                ):
                    continue
                names = tuple(sorted({
                    field.name for field in target_ep.output_fields
                    if any(
                        _complete_fields([field], (required,))
                        for required in demand.required_fields
                    )
                }))
                for middle_id in self.graph.predecessors(target_id):
                    middle = authorized(middle_id)
                    if middle is None or middle_id == target_id:
                        continue
                    middle_tool, middle_ep = middle
                    # An intermediary must genuinely consume source inputs
                    # and produce the typed identifier needed by the target.
                    if _native_required_inputs(middle_ep) is None:
                        continue
                    second = bind(middle_tool, middle_ep, target_ep)
                    if second is None:
                        continue
                    for root_id in self.graph.predecessors(middle_id):
                        if len({root_id, middle_id, target_id}) != 3:
                            continue
                        root = authorized(root_id)
                        if root is None:
                            continue
                        root_tool, root_ep = root
                        external_inputs = root_inputs(root_id, root_tool, root_ep)
                        if external_inputs is None:
                            continue
                        first = bind(root_tool, root_ep, middle_ep)
                        if first is None:
                            continue
                        qualified.append(NativeIndexedTwoHopCandidate(
                            route_ids=(root_id, middle_id, target_id),
                            route_fingerprints=(
                                self.field_index.route_fingerprints[root_id],
                                self.field_index.route_fingerprints[middle_id],
                                self.field_index.route_fingerprints[target_id],
                            ),
                            root_to_intermediate=first,
                            intermediate_to_target=second,
                            target_output_fields=names,
                            source_root_parameters=external_inputs,
                        ))
                        if len(qualified) > MAX_RESEARCH_RANKABLE_PATHS:
                            raise PolicyViolationError(
                                "G5 two-hop source expansion exceeds E0 limit"
                            )
            # Every previously qualified route is re-read AFTER all health
            # callbacks, even if >K would return a count-only abstention.
            for candidate in qualified:
                root_id, middle_id, target_id = candidate.route_ids
                reread = tuple(authorized(route) for route in candidate.route_ids)
                if any(source is None for source in reread):
                    raise PolicyViolationError("G5 two-hop route withdrawn")
                root_current, middle_current, target_current = reread
                assert root_current is not None
                assert middle_current is not None
                assert target_current is not None
                root_tool, root_ep = root_current
                middle_tool, middle_ep = middle_current
                target_tool, target_ep = target_current
                if (
                    root_inputs(root_id, root_tool, root_ep)
                    != candidate.source_root_parameters
                    or _native_required_inputs(middle_ep) is None
                    or bind(root_tool, root_ep, middle_ep)
                    != candidate.root_to_intermediate
                    or bind(middle_tool, middle_ep, target_ep)
                    != candidate.intermediate_to_target
                    or demand.source_type is not None
                    and target_tool.source_type != demand.source_type
                    or demand.license is not None
                    and target_tool.license != demand.license
                    or not _complete_fields(
                        target_ep.output_fields, demand.required_fields,
                    )
                ):
                    raise PolicyViolationError("G5 two-hop binding or scope withdrawn")
                latest_names = tuple(sorted({
                    field.name for field in target_ep.output_fields
                    if any(
                        _complete_fields([field], (required,))
                        for required in demand.required_fields
                    )
                }))
                if latest_names != candidate.target_output_fields:
                    raise PolicyViolationError("G5 two-hop output scope changed")
        except Exception:
            # Provider/host callbacks may throw messages containing private
            # source fields; only generic failure reaches an external agent.
            raise PolicyViolationError(
                "G5 two-hop source eligibility changed during lookup"
            ) from None

        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        policy = router.authorization_policy
        if policy is None or (
            policy.default_effect, repr(policy.rules), repr(policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError(
                "G5 two-hop authorization policy changed during lookup"
            )
        count = len(qualified)
        return NativeIndexedTwoHopResult(
            "over_k_unranked" if count > k else
            "complete" if count else "no_proven_hit",
            self.field_index.snapshot_id,
            self.field_index.registry_version,
            k,
            count,
            tuple(qualified) if count <= k else (),
        )

    def lookup_bounded_paths(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        hops: int = 3,
        k: int = STRICT_K,
    ) -> NativeIndexedPathResult:
        """Explicit research-only 2–4-edge typed route proof, no execution.

        This delegates to the existing graph's adjacency and original
        source/field comparators. It never creates an additional index.
        """
        from .native_deep_paths import lookup_bounded_native_paths

        return lookup_bounded_native_paths(
            self, router, query, group=group, principal=principal,
            hops=hops, k=k,
        )

    def lookup_shared_root_forks(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
    ) -> NativeIndexedSharedRootForkResult:
        """Research-only common-source two-leaf field AND (no row merge).

        Delegates all authorization and typed joins to the existing native
        G5 single-field lookups; does not create a new retrieval index.
        """
        from .native_fork_index import lookup_native_shared_root_forks

        return lookup_native_shared_root_forks(
            self, router, query, group=group, principal=principal, k=k,
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
