"""G2 opt-in: bounded, authorized, typed one/two-edge graph path HINTS.

No autonomous agent, execution, parameter values, translation or inferred
input semantics. All consumer semantic bindings are host-declared against
pinned registered endpoint fingerprints; graph edges are native comparators.
"""
from __future__ import annotations

from dataclasses import dataclass

from schemarouter import PrincipalContext, SchemaRouter
from schemarouter.canonical_json import canonical_json_sha256
from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    compare_capability_fields,
)
from schemarouter.capability_snapshot import (
    CapabilitySourceRevision,
    build_capability_snapshot,
    validate_capability_snapshot,
)
from schemarouter.models import EndpointSpec, FieldSpec, ToolSpec
from scripts.research_authorized_native_graph_edges_g1 import (
    _norm,
    _produced_fields,
    _safe_routes,
    _simple_scalar_schema,
)

STRICT_K = 5
MAX_HOPS = 2
MAX_BINDINGS = 32
MAX_EDGES = 2048
MAX_WALK_STATES = 128


def _safe_declared_text(text: str) -> bool:
    return type(text) is str and 0 < len(text) <= 160 and text.strip() == text


@dataclass(frozen=True)
class DeclaredInputBindingG2:
    """Trusted host mapping of one *real required* parameter to semantic ID."""

    route_id: str
    parameter_name: str
    semantic_id: str
    expected_endpoint_fingerprint: str
    unit: str | None = None
    qualifiers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if (
            any(not _safe_declared_text(value) for value in (
                self.route_id, self.parameter_name, self.semantic_id,
                self.expected_endpoint_fingerprint,
            ))
            or self.unit is not None and not _safe_declared_text(self.unit)
            or type(self.qualifiers) is not tuple
            or len(self.qualifiers) > 8
            or any(
                type(pair) is not tuple or len(pair) != 2
                or any(not _safe_declared_text(v) for v in pair)
                for pair in self.qualifiers
            )
            or len({name for name, _ in self.qualifiers}) != len(self.qualifiers)
        ):
            raise ValueError("invalid trusted input binding")


@dataclass(frozen=True)
class DeclaredGraphGoalG2:
    aliases: tuple[str, ...]
    target_route_id: str
    required_outputs: tuple[CapabilityFieldContract, ...]
    bindings: tuple[DeclaredInputBindingG2, ...]

    def __post_init__(self) -> None:
        if (
            type(self.aliases) is not tuple
            or not 1 <= len(self.aliases) <= 16
            or any(not _safe_declared_text(x) for x in self.aliases)
            or len({_norm(x) for x in self.aliases}) != len(self.aliases)
            or not _safe_declared_text(self.target_route_id)
            or type(self.required_outputs) is not tuple
            or not 1 <= len(self.required_outputs) <= 8
            or any(type(x) is not CapabilityFieldContract for x in self.required_outputs)
            or len({x.semantic_id for x in self.required_outputs}) != len(self.required_outputs)
            or type(self.bindings) is not tuple
            or not 1 <= len(self.bindings) <= MAX_BINDINGS
            or any(type(x) is not DeclaredInputBindingG2 for x in self.bindings)
            or len({x.route_id for x in self.bindings}) != len(self.bindings)
            or self.target_route_id not in {x.route_id for x in self.bindings}
        ):
            raise ValueError("invalid bounded declared graph goal")


@dataclass(frozen=True)
class GraphEdgeBindingG2:
    producer_route_id: str
    producer_output_field: str
    consumer_route_id: str
    consumer_input_parameter: str
    semantic_id: str


@dataclass(frozen=True)
class NonExecutableGraphPathG2:
    route_ids: tuple[str, ...]
    edges: tuple[GraphEdgeBindingG2, ...]
    target_output_fields: tuple[str, ...]
    scoped_snapshot_id: str


def _proved_empty_root_envelope(endpoint: EndpointSpec) -> bool:
    """Prove an adapter-declared empty argument object is truly parameter-free.

    OpenAPI emits an explicit `additionalProperties: false` envelope even for
    GET operations with no parameters. It is not permission to erase provider
    input schemas or to ignore unknown keywords and required arguments.
    """
    if not endpoint.input_schema:
        return True
    if endpoint.parameters:
        return False
    return endpoint.input_schema in (
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": [],
         "additionalProperties": False},
    )


def _native_required_param(
    endpoint: EndpointSpec,
) -> tuple[str, dict] | None:
    # A source can publish a plain object input envelope (as MCP does).
    # Only prove the exact trivial one-property schema. Do not silently
    # discard unknown JSON Schema constraints, $refs or provider auth.
    if endpoint.auth_requirements:
        return None
    if any(p.location in {"header", "body_root"} for p in endpoint.parameters):
        return None
    required = [p for p in endpoint.parameters if p.required]
    if len(required) != 1 or not _simple_scalar_schema(required[0].json_schema):
        return None
    parameter = required[0]
    declared = endpoint.input_schema
    if declared and (
        type(declared) is not dict
        or set(declared) != {"type", "properties", "required"}
        or declared["type"] != "object"
        or type(declared["properties"]) is not dict
        or declared["properties"] != {parameter.name: parameter.json_schema}
        or declared["required"] != [parameter.name]
        or len(endpoint.parameters) != 1
    ):
        return None
    return (parameter.name, parameter.json_schema)


def _full_target_outputs(
    endpoint: EndpointSpec,
    required: tuple[CapabilityFieldContract, ...],
) -> tuple[str, ...] | None:
    field_names: list[str] = []
    for demand in required:
        if not _simple_scalar_schema(demand.json_schema):
            return None
        eligible = [
            field.name for field in endpoint.output_fields
            if field.semantic_id is not None
            and field.unit_normalization is None
            and _simple_scalar_schema(field.json_schema)
            and (
                contract := CapabilityFieldContract.from_field(field)
            ) is not None
            and (demand.unit is None or contract.unit == demand.unit)
            and compare_capability_fields(demand, contract).status in {
                "exact", "compatible",
            }
        ]
        if not eligible:
            return None
        field_names.append(min(eligible))
    return tuple(field_names)


def _valid_edge_field(
    endpoint: EndpointSpec,
    required: CapabilityFieldContract,
) -> FieldSpec | None:
    # The producer must publish an explicit identifier result, not just a
    # similarly named or semantically equivalent non-identifier property.
    eligible = [
        field for field in endpoint.output_fields
        if field.identifier is True
        and field.unit_normalization is None
        and _simple_scalar_schema(field.json_schema)
        and (
            contract := CapabilityFieldContract.from_field(field)
        ) is not None
        and (required.unit == contract.unit)
        and compare_capability_fields(required, contract).status in {
            "exact", "compatible",
        }
    ]
    return min(eligible, key=lambda field: field.name) if eligible else None


def retrieve_verified_graph_paths_g2(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    goal: DeclaredGraphGoalG2,
    k: int = STRICT_K,
    max_hops: int = MAX_HOPS,
) -> tuple[NonExecutableGraphPathG2, ...]:
    """Return proven, visible, nonexecuting chains; no partial-K backfill."""
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G2 requires exactly fixed K5")
    if type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("G2 allows only one or two verified hops")
    if (
        type(query) is not str
        or len(query.encode("utf-8")) > 512
        or _norm(query) not in {_norm(a) for a in goal.aliases}
    ):
        raise ValueError("no host-declared query-to-graph goal")
    if not isinstance(principal, PrincipalContext):
        raise ValueError("G2 requires an explicit principal")

    witness = router._retrieval_authority_witness()
    routes = _safe_routes(router, principal)
    bindings = {binding.route_id: binding for binding in goal.bindings}
    if goal.target_route_id not in routes:
        router._check_retrieval_authority_witness(witness)
        return ()

    contracts: list[CapabilityContract] = []
    eligible_routes: dict[str, tuple[ToolSpec, EndpointSpec]] = {}
    requirements: dict[str, CapabilityFieldContract] = {}
    roots: set[str] = set()
    raw_source_fingerprints: dict[str, str] = {}
    for route_id, (tool, endpoint) in sorted(routes.items()):
        required_native = [p for p in endpoint.parameters if p.required]
        if not required_native:
            # Zero-input sources may provide the first identifier. Any declared
            # consumer binding to such a route is stale or inconsistent.
            if (route_id in bindings or not _proved_empty_root_envelope(endpoint)
                    or endpoint.auth_requirements):
                continue
            if any(p.location in {"header", "body_root"} for p in endpoint.parameters):
                continue
            roots.add(route_id)
            required_contracts: list[CapabilityFieldContract] = []
        else:
            binding = bindings.get(route_id)
            declared = _native_required_param(endpoint)
            if binding is None or declared is None:
                continue
            name, schema = declared
            if binding.parameter_name != name:
                continue
            # Check the *registered* native endpoint identity, not only its
            # redacted view: scoped metadata can have a different fingerprint.
            original = router.registry.get(tool.key).endpoint(endpoint.name)
            if original.fingerprint != binding.expected_endpoint_fingerprint:
                raise ValueError("declared graph binding source is stale")
            contract = CapabilityFieldContract(
                semantic_id=binding.semantic_id,
                json_schema=schema,
                unit=binding.unit,
                qualifiers=dict(binding.qualifiers),
            )
            requirements[route_id] = contract
            required_contracts = [contract]
        produces = _produced_fields(endpoint)
        if not produces:
            continue
        # License and source labels are provenance requirements, NOT legal
        # clearance; absent declared metadata cannot qualify G2 evidence.
        if not tool.source_type or not tool.license:
            continue
        eligible_routes[route_id] = (tool, endpoint)
        raw_source_fingerprints[route_id] = (
            router.registry.get(tool.key).endpoint(endpoint.name).fingerprint
        )
        contracts.append(CapabilityContract(
            capability_id=route_id,
            requires=required_contracts,
            produces=produces,
        ))

    target = eligible_routes.get(goal.target_route_id)
    if target is None or goal.target_route_id not in requirements:
        router._check_retrieval_authority_witness(witness)
        return ()
    output_fields = _full_target_outputs(target[1], goal.required_outputs)
    if output_fields is None:
        router._check_retrieval_authority_witness(witness)
        return ()
    # A path can only be sourced from a parameter-free, authorized native root.
    roots.intersection_update(eligible_routes)
    declaration_digest = canonical_json_sha256({
        "aliases": list(goal.aliases),
        "target": goal.target_route_id,
        "required_outputs": [
            item.model_dump(mode="json") for item in goal.required_outputs
        ],
        "bindings": [b.__dict__ for b in goal.bindings],
    })
    snapshot = build_capability_snapshot(
        contracts,
        sources=[
            CapabilitySourceRevision(
                provider=route_id,
                access_method="principal_scoped_native_g2",
                schema_fingerprint=endpoint.fingerprint,
            )
            for route_id, (_tool, endpoint) in sorted(eligible_routes.items())
        ],
        builder_version=f"verified_native_g2:{declaration_digest}",
    )
    validate_capability_snapshot(snapshot)
    graph = snapshot.build_graph()
    if len(graph.edges) > MAX_EDGES:
        raise ValueError("G2 graph edge budget exceeded")

    # Traverse graph adjacency BACKWARDS from the verified full target,
    # but publish forward source→target paths. No cycles or unsupported
    # inputs, and no arbitrary truncated candidate results.
    paths: list[NonExecutableGraphPathG2] = []
    stack: list[tuple[str, tuple[str, ...], tuple[GraphEdgeBindingG2, ...]]] = [
        (goal.target_route_id, (goal.target_route_id,), ())
    ]
    expanded = 0
    while stack:
        current, backwards_routes, backwards_edges = stack.pop()
        expanded += 1
        if expanded > MAX_WALK_STATES:
            raise ValueError("G2 graph search budget exceeded")
        if current in roots and len(backwards_routes) > 1:
            paths.append(NonExecutableGraphPathG2(
                route_ids=tuple(reversed(backwards_routes)),
                edges=tuple(reversed(backwards_edges)),
                target_output_fields=output_fields,
                scoped_snapshot_id=snapshot.snapshot_id,
            ))
            if len(paths) > k:
                raise ValueError("G2 verified-path K budget exceeded")
            continue
        if len(backwards_edges) >= max_hops:
            continue
        needed = requirements.get(current)
        if needed is None:
            continue
        for predecessor in sorted(graph.predecessors(current), reverse=True):
            if predecessor in backwards_routes:
                continue
            producer = eligible_routes[predecessor][1]
            field = _valid_edge_field(producer, needed)
            if field is None:
                continue
            binding = bindings[current]
            stack.append((
                predecessor,
                (*backwards_routes, predecessor),
                (*backwards_edges, GraphEdgeBindingG2(
                    producer_route_id=predecessor,
                    producer_output_field=field.name,
                    consumer_route_id=current,
                    consumer_input_parameter=binding.parameter_name,
                    semantic_id=binding.semantic_id,
                )),
            ))
    # Registry.version is useful but cannot prove that an adapter did not
    # mutate a live EndpointSpec object without bumping the registry. Recheck
    # native source identities independently of principal-scoped projections.
    for route_id, (tool, endpoint) in eligible_routes.items():
        try:
            current = router.registry.get(tool.key).endpoint(endpoint.name).fingerprint
        except (KeyError, ValueError) as exc:
            raise ValueError("native graph source changed during query") from exc
        if current != raw_source_fingerprints[route_id]:
            raise ValueError("native graph source changed during query")
    router._check_retrieval_authority_witness(witness)
    return tuple(sorted(paths, key=lambda p: p.route_ids))
