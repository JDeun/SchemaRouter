"""Versioned catalog-wide *structural* semantic postings, opt-in E0.

The registry stores ALL native tool contracts; this index stores only
verified scalar semantic postings and source revisions. Query-time checks
use the original principal/policy/data scope and availability. It is not
an execution engine, graph path planner, or new lexical ranker.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from .errors import PolicyViolationError, RegistrationError
from .field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
    _scalar_contract,
)
from .models import FieldSpec, ToolSpec
from .registry import InMemoryRegistry, SQLiteRegistry, ToolRegistry

if TYPE_CHECKING:
    from .runtime import SchemaRouter

STRICT_K = 5
# Non-production research rankers never receive an unbounded private candidate menu.
MAX_RESEARCH_RANKABLE_POSTINGS = 32


def _indexable_semantic_field(field: FieldSpec) -> bool:
    """Index only declared scalar semantics, including explicit numeric normalization.

    A provider unit string alone cannot create a conversion. Canonicalized fields
    must carry a source unit and a locally declared UnitNormalizationSpec; the
    source tool and license remain mandatory in build/refresh. Actual candidate
    qualification still uses the original scoped canonical comparator.
    """
    if field.semantic_id is None or not _scalar_contract(field.json_schema):
        return False
    normalization = field.unit_normalization
    if normalization is None:
        return True
    return (
        field.unit is not None
        and field.json_schema.get("type") in {"number", "integer"}
    )


@dataclass(frozen=True, slots=True)
class IndexedNativeFieldCandidate:
    """Source-scoped evidence ONLY; not an authorized tool execution token."""

    route_id: str
    tool_fingerprint: str
    endpoint_fingerprint: str
    required_output_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexedNativeFieldResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "ranker_abstained_unverified",
    ]
    registry_version: int
    index_snapshot_id: str
    requested_k: int
    qualified_count: int
    candidates: tuple[IndexedNativeFieldCandidate, ...]
    experimental_ranked: bool = False


@dataclass(frozen=True, slots=True)
class NativeSchemaPostingIndex:
    """Built once per source registry version, queried by semantic posting.

    This immutable *internal* index is deliberately authorization-neutral;
    the query path must NEVER return raw posting IDs without checking current
    original-source policy/field scope/availability and exact fingerprints.
    """

    registry_ref: ToolRegistry
    registry_version: int
    snapshot_id: str
    indexed_route_count: int
    postings: Mapping[str, tuple[str, ...]]
    route_fingerprints: Mapping[str, tuple[str, str]]
    route_locations: Mapping[str, tuple[str, str]]
    # Include even zero-endpoint tools for exact omitted-change detection.
    tool_fingerprints: Mapping[str, str]

    @classmethod
    def build(cls, registry: ToolRegistry) -> NativeSchemaPostingIndex:
        version = registry.version
        semantic: dict[str, set[str]] = {}
        revisions: dict[str, tuple[str, str]] = {}
        locations: dict[str, tuple[str, str]] = {}
        tool_fingerprints: dict[str, str] = {}
        count = 0
        for tool in registry.tools():
            # Each registry tool is a detached snapshot. Its fingerprint
            # covers all endpoints; recomputing the whole serialized tool
            # for every endpoint makes a broad multi-endpoint catalog costly.
            # No cross-build or cross-request cache is introduced.
            tool_fingerprint = tool.fingerprint
            tool_key = tool.key
            tool_fingerprints[tool_key] = tool_fingerprint
            for endpoint in tool.endpoints:
                count += 1
                route = f"{tool_key}.{endpoint.name}"
                if route in revisions:
                    raise ValueError("duplicated registered native route")
                revisions[route] = (tool_fingerprint, endpoint.fingerprint)
                locations[route] = (tool_key, endpoint.name)
                # Index all schema nodes but only scalar source-typed output
                # semantics; no inferred IDs from descriptions or task gold.
                if not tool.source_type or not tool.license:
                    continue
                for field in endpoint.output_fields:
                    if field.semantic_id is not None and _indexable_semantic_field(field):
                        semantic.setdefault(field.semantic_id, set()).add(route)
        if registry.version != version:
            raise PolicyViolationError("native index source changed during build")
        ordered = {key: tuple(sorted(items)) for key, items in sorted(semantic.items())}
        receipt = json.dumps(
            {"version": version, "routes": sorted(revisions.items()),
             "postings": ordered},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return cls(
            registry_ref=registry,
            registry_version=version,
            snapshot_id=sha256(receipt.encode("utf-8")).hexdigest(),
            indexed_route_count=count,
            postings=MappingProxyType(ordered),
            route_fingerprints=MappingProxyType(revisions),
            route_locations=MappingProxyType(locations),
            tool_fingerprints=MappingProxyType(tool_fingerprints),
        )

    @classmethod
    def refresh(
        cls,
        previous: NativeSchemaPostingIndex,
        registry: ToolRegistry,
        *,
        changed_tool_keys: tuple[str, ...],
    ) -> NativeSchemaPostingIndex:
        """Copy-on-write semantic posting refresh with full manifest validation.

        Changed-key hints are NOT trusted. The current exact fingerprint of
        every otherwise-unmodified registered tool must equal the old pinned
        source. Only changed tools are re-indexed for semantic postings, but
        this method still verifies all tool fingerprints (O(catalog)).
        No incremental graph-edge rebuild or latency speedup is claimed.
        """
        if (
            type(changed_tool_keys) is not tuple
            or not 1 <= len(changed_tool_keys) <= 64
            or any(type(key) is not str or not key for key in changed_tool_keys)
            or len(set(changed_tool_keys)) != len(changed_tool_keys)
        ):
            raise ValueError("bounded exact changed tool keys required")
        if previous.registry_ref is not registry:
            raise PolicyViolationError("native posting refresh source mismatch")
        version = registry.version
        if version <= previous.registry_version:
            raise PolicyViolationError("native posting refresh needs newer source")
        changed = frozenset(changed_tool_keys)
        old_tools = previous.tool_fingerprints
        changed_tools = {}
        fresh_fingerprints: dict[str, str] = {}
        try:
            current_keys = registry.keys()
            if type(current_keys) is not tuple or len(set(current_keys)) != len(current_keys):
                raise PolicyViolationError("native posting refresh invalid tool manifest")
            if not changed.issubset(set(current_keys) | set(old_tools)):
                raise PolicyViolationError("native posting refresh unknown changed tool")
            for key in current_keys:
                tool = registry.get(key)
                if tool.key != key:
                    raise PolicyViolationError("native posting refresh tool key changed")
                fingerprint = tool.fingerprint
                fresh_fingerprints[key] = fingerprint
                if key in changed:
                    changed_tools[key] = tool
                elif old_tools.get(key) != fingerprint:
                    raise PolicyViolationError("native posting refresh omitted changed tool")
            if set(old_tools) - set(current_keys) - changed:
                raise PolicyViolationError("native posting refresh omitted deleted tool")
            if registry.version != version:
                raise PolicyViolationError("native posting refresh source changed")
        except Exception:
            # An untrusted registry implementation might include its own
            # private schema text in an exception. Do not forward it.
            raise PolicyViolationError("native posting refresh cannot verify source") from None

        return cls._assemble_verified_posting_delta(
            previous, registry, version, changed, changed_tools,
            fresh_fingerprints,
        )

    @classmethod
    def refresh_from_inmemory_journal(
        cls,
        previous: NativeSchemaPostingIndex,
        registry: ToolRegistry,
    ) -> NativeSchemaPostingIndex:
        """Opt-in key-only delta from the same exact atomic in-memory source.

        This MUST NOT be used for SQLite, proxies or arbitrary registries:
        their writes have not been proven to emit the source-owned journal.
        Exact version checks reject races before publishing a new snapshot;
        lookup independently rechecks that version before showing evidence.
        """
        if type(registry) is not InMemoryRegistry:
            raise PolicyViolationError(
                "native journal refresh requires exact in-memory registry"
            )
        return cls._refresh_from_source_owned_journal(previous, registry)

    @classmethod
    def refresh_from_sqlite_journal(
        cls,
        previous: NativeSchemaPostingIndex,
        registry: ToolRegistry,
    ) -> NativeSchemaPostingIndex:
        """E0 opt-in durable SQLite source-owned journal posting delta.

        Only exact built-in SQLiteRegistry supports this experiment. No
        custom registry, arbitrary database adapter, or legacy history can
        supply a fast-path receipt. All reads stay original-source-owned.
        """
        if not isinstance(registry, SQLiteRegistry) or type(registry) is not SQLiteRegistry:
            raise PolicyViolationError(
                "native journal refresh requires exact SQLite registry"
            )
        return cls._refresh_from_source_owned_journal(previous, registry)

    @classmethod
    def _refresh_from_source_owned_journal(
        cls,
        previous: NativeSchemaPostingIndex,
        registry: InMemoryRegistry | SQLiteRegistry,
    ) -> NativeSchemaPostingIndex:
        """A single immutable posting-delta assembler for two audited sources."""
        if previous.registry_ref is not registry:
            raise PolicyViolationError("native journal refresh source mismatch")
        try:
            delta = registry.changed_tool_keys_since(previous.registry_version)
        except (RegistrationError, RuntimeError):
            raise PolicyViolationError(
                "native journal refresh unavailable; full rebuild required"
            ) from None
        version = delta.to_version
        if (
            delta.from_version != previous.registry_version
            or version <= previous.registry_version
            or not 1 <= len(delta.changed_tool_keys) <= 64
        ):
            raise PolicyViolationError("native journal refresh invalid delta")
        changed = frozenset(delta.changed_tool_keys)
        current_fingerprints = dict(previous.tool_fingerprints)
        changed_tools: dict[str, ToolSpec] = {}
        try:
            for key in changed:
                try:
                    tool = registry.get(key)
                except KeyError:
                    current_fingerprints.pop(key, None)
                    continue
                if tool.key != key:
                    raise PolicyViolationError("native journal mismatched tool")
                current_fingerprints[key] = tool.fingerprint
                changed_tools[key] = tool
            if registry.version != version:
                raise PolicyViolationError("native journal concurrent source mutation")
        except Exception:
            raise PolicyViolationError(
                "native journal refresh cannot verify changed source"
            ) from None
        return cls._assemble_verified_posting_delta(
            previous, registry, version, changed, changed_tools,
            current_fingerprints,
        )

    @classmethod
    def _assemble_verified_posting_delta(
        cls,
        previous: NativeSchemaPostingIndex,
        registry: ToolRegistry,
        version: int,
        changed: frozenset[str],
        changed_tools: dict[str, ToolSpec],
        fresh_fingerprints: dict[str, str],
    ) -> NativeSchemaPostingIndex:
        """One canonical index-assembly path for full and journal proof."""
        revisions = dict(previous.route_fingerprints)
        locations = dict(previous.route_locations)
        stale_routes = {
            route for route, (tool_key, _endpoint) in locations.items()
            if tool_key in changed
        }
        for route in stale_routes:
            revisions.pop(route)
            locations.pop(route)
        semantic = {
            name: set(routes) - stale_routes
            for name, routes in previous.postings.items()
        }
        for key, tool in changed_tools.items():
            tool_fingerprint = fresh_fingerprints[key]
            for endpoint in tool.endpoints:
                route = f"{key}.{endpoint.name}"
                if route in revisions:
                    raise PolicyViolationError("native posting refresh duplicate route")
                revisions[route] = (tool_fingerprint, endpoint.fingerprint)
                locations[route] = (key, endpoint.name)
                if tool.source_type and tool.license:
                    for field in endpoint.output_fields:
                        if field.semantic_id is not None and _indexable_semantic_field(field):
                            semantic.setdefault(field.semantic_id, set()).add(route)
        if registry.version != version:
            raise PolicyViolationError("native posting refresh source changed")
        ordered = {
            name: tuple(sorted(routes))
            for name, routes in sorted(semantic.items()) if routes
        }
        receipt = json.dumps(
            {"version": version, "routes": sorted(revisions.items()),
             "postings": ordered},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return cls(
            registry_ref=registry,
            registry_version=version,
            snapshot_id=sha256(receipt.encode("utf-8")).hexdigest(),
            indexed_route_count=len(revisions),
            postings=MappingProxyType(ordered),
            route_fingerprints=MappingProxyType(revisions),
            route_locations=MappingProxyType(locations),
            tool_fingerprints=MappingProxyType(fresh_fingerprints),
        )

    def _assert_source(self, router: SchemaRouter) -> None:
        if (
            router.registry is not self.registry_ref
            or router.registry.version != self.registry_version
        ):
            raise PolicyViolationError("native semantic index source revision is stale")

    def lookup(
        self,
        router: SchemaRouter,
        query: str,
        *,
        group: NativeDeclaredFieldGroup,
        principal: PrincipalContext,
        k: int = STRICT_K,
        input_free_only: bool = False,
        allowed_tool_keys: tuple[str, ...] | None = None,
        _research_ranker: Callable[
            [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
        ] | None = None,
    ) -> IndexedNativeFieldResult:
        """Conjunctive source-owned lookup with optional bounded E0 ranking.

        The default >K result abstains. An explicit research callback can
        choose *offsets* among at most 32 fully authorized, visible candidates.
        Such a choice is tagged unverified and confers no execution authority.
        An optional direct-only filter runs BEFORE candidate budgeting.
        """
        if type(input_free_only) is not bool:
            raise ValueError("indexed direct-only flag must be boolean")
        if allowed_tool_keys is not None and (
            type(allowed_tool_keys) is not tuple
            or not 1 <= len(allowed_tool_keys) <= k
            or any(
                type(key) is not str or not 1 <= len(key) <= 160
                or key != key.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in key)
                for key in allowed_tool_keys
            )
            or len(set(allowed_tool_keys)) != len(allowed_tool_keys)
        ):
            raise ValueError("invalid bounded named tool override")
        if _research_ranker is not None and not callable(_research_ranker):
            raise ValueError("indexed research ranker must be callable")
        if type(k) is not int or k != STRICT_K:
            raise ValueError("native indexed lookup requires exact K5")
        if type(query) is not str or len(query.encode("utf-8")) > 512:
            raise ValueError("invalid bounded indexed native query")
        if not isinstance(principal, PrincipalContext):
            raise PolicyViolationError("trusted principal required")
        if not isinstance(group, NativeDeclaredFieldGroup):
            raise ValueError("host-declared typed FieldGroup required")
        try:
            declaration = NativeDeclaredFieldGroup.model_validate(
                group.model_dump(mode="python"), strict=True,
            )
            approved_principal = PrincipalContext.model_validate(
                principal.model_dump(mode="python"), strict=True,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid current indexed declarations") from exc
        try:
            principal_claims = principal.model_dump_json()
            group_claims = group.model_dump_json()
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("cannot attest indexed lookup declarations") from exc
        if _alias_key(query) not in {_alias_key(a) for a in declaration.aliases}:
            raise ValueError("no host-approved query-to-FieldGroup edge")
        if router.authorization_policy is None:
            raise PolicyViolationError("explicit authorization policy required")
        self._assert_source(router)
        witness = router._retrieval_authority_witness()
        original_policy = (
            router.authorization_policy.default_effect,
            repr(router.authorization_policy.rules),
            repr(router.authorization_policy.data_rules),
        )
        # The inverted index is ONLY a conservative candidate prefilter.
        # It never bypasses live access checks or the canonical typed compare.
        ids = [set(self.postings.get(field.semantic_id, ()))
               for field in declaration.required_fields]
        matched = set.intersection(*ids) if ids else set()
        permitted = router._authorization_predicate(approved_principal)
        if permitted is None:
            raise PolicyViolationError("explicit authorization required")
        availability = router.planner.availability_predicate
        qualified: list[IndexedNativeFieldCandidate] = []
        for route in sorted(matched):
            # Key is an opaque exact registered route; never parse a route ID
            # with split because tool namespaces may contain separators.
            revisions = self.route_fingerprints.get(route)
            if revisions is None:
                raise PolicyViolationError("indexed route missing original fingerprint")
            location = self.route_locations.get(route)
            if location is None:
                raise PolicyViolationError("indexed registered route missing")
            tool_key, endpoint_name = location
            if allowed_tool_keys is not None and tool_key not in allowed_tool_keys:
                continue
            tool = router.registry.get(tool_key)
            endpoint = tool.endpoint(endpoint_name)
            if (tool.fingerprint, endpoint.fingerprint) != revisions:
                raise PolicyViolationError("indexed source fingerprint drift")
            if (tool.source_type is None or tool.license is None
                    or declaration.source_type is not None
                    and tool.source_type != declaration.source_type
                    or declaration.license is not None
                    and tool.license != declaration.license):
                continue
            if endpoint.read_only is not True or endpoint.destructive is True:
                continue
            if input_free_only and not _root_envelope_empty(endpoint):
                continue
            if not permitted(tool, endpoint):
                continue
            # Host health callbacks are not a trusted error surface. A provider
            # exception (including __bool__) must never escape with private
            # endpoint details before the later final eligibility pass.
            if availability is not None:
                try:
                    available_now = bool(availability(tool, endpoint))
                except Exception:
                    raise PolicyViolationError(
                        "indexed availability check failed during lookup"
                    ) from None
                if not available_now:
                    continue
            visible = router._data_scope_endpoint_view(
                approved_principal, tool, endpoint,
            )
            if (visible is None or not _complete_fields(
                    visible.output_fields, declaration.required_fields)):
                continue
            matched_names: list[str] = []
            for required in declaration.required_fields:
                matched_names.extend(
                    field.name for field in visible.output_fields
                    if field.semantic_id == required.semantic_id
                    and _complete_fields([field], (required,))
                )
            qualified.append(IndexedNativeFieldCandidate(
                route_id=route,
                tool_fingerprint=tool.fingerprint,
                endpoint_fingerprint=endpoint.fingerprint,
                required_output_fields=tuple(sorted(set(matched_names))),
            ))
        count = len(qualified)
        ranked_offsets: tuple[int, ...] | None = None
        if (
            count > k and _research_ranker is not None
            and count <= MAX_RESEARCH_RANKABLE_POSTINGS
        ):
            # Pass detached read-only-shaped records to an UNTRUSTED ranker.
            # Never trust returned candidate objects, route names or arbitrary
            # ranking values: only unique indices into our verified snapshot.
            offered = tuple(replace(candidate) for candidate in qualified)
            try:
                proposed = _research_ranker(query, offered, k)
            except Exception:
                raise PolicyViolationError("indexed research ranking failed") from None
            if (
                type(proposed) is not tuple
                or len(proposed) not in (0, k)
                or any(
                    type(offset) is not int or not 0 <= offset < count
                    for offset in proposed
                )
                or len(set(proposed)) != len(proposed)
            ):
                raise PolicyViolationError(
                    "indexed ranker returned forged, partial or duplicate offsets"
                )
            ranked_offsets = proposed
        # A live availability callable may keep its identity while a
        # later candidate's health probe revokes an earlier candidate.
        # Recheck every already-qualified route, even when >K ultimately
        # abstains: qualified_count is still disclosed to the caller.
        try:
            for candidate in qualified:
                where = self.route_locations[candidate.route_id]
                pinned = self.route_fingerprints[candidate.route_id]
                tool = router.registry.get(where[0])
                endpoint = tool.endpoint(where[1])
                if (tool.fingerprint, endpoint.fingerprint) != pinned:
                    raise PolicyViolationError("indexed candidate source changed")
                if (
                    tool.source_type is None or tool.license is None
                    or declaration.source_type is not None
                    and tool.source_type != declaration.source_type
                    or declaration.license is not None
                    and tool.license != declaration.license
                    or endpoint.read_only is not True
                    or endpoint.destructive is True
                    or input_free_only and not _root_envelope_empty(endpoint)
                    or not permitted(tool, endpoint)
                    or availability is not None and not availability(tool, endpoint)
                ):
                    raise PolicyViolationError("indexed candidate no longer available")
                scoped = router._data_scope_endpoint_view(
                    approved_principal, tool, endpoint,
                )
                if (
                    scoped is None or not _complete_fields(
                        scoped.output_fields, declaration.required_fields,
                    )
                ):
                    raise PolicyViolationError("indexed candidate scope changed")
                current_names = tuple(sorted({
                    field.name for required in declaration.required_fields
                    for field in scoped.output_fields
                    if field.semantic_id == required.semantic_id
                    and _complete_fields([field], (required,))
                }))
                if current_names != candidate.required_output_fields:
                    raise PolicyViolationError("indexed candidate projection changed")
        except Exception:
            # Avoid leaking provider/private schema details in callback errors.
            raise PolicyViolationError(
                "indexed candidate eligibility changed during lookup"
            ) from None
        self._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        current_policy = router.authorization_policy
        if (
            current_policy.default_effect,
            repr(current_policy.rules),
            repr(current_policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError("authorization policy changed during indexed lookup")
        try:
            if (
                principal.model_dump_json() != principal_claims
                or group.model_dump_json() != group_claims
            ):
                raise PolicyViolationError("indexed lookup declarations changed")
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError(
                "cannot attest current indexed lookup declarations"
            ) from exc
        status: Literal[
            "complete", "no_proven_hit", "over_k_unranked",
            "ranked_unverified", "ranker_abstained_unverified",
        ]
        if count > k:
            status = (
                "over_k_unranked" if ranked_offsets is None else
                "ranked_unverified" if ranked_offsets else
                "ranker_abstained_unverified"
            )
        else:
            status = "complete" if count else "no_proven_hit"
        return IndexedNativeFieldResult(
            status=status,
            registry_version=self.registry_version,
            index_snapshot_id=self.snapshot_id,
            requested_k=k,
            qualified_count=count,
            candidates=(
                tuple(qualified[offset] for offset in ranked_offsets)
                if ranked_offsets is not None else
                tuple(qualified) if count <= k else ()
            ),
            experimental_ranked=ranked_offsets is not None,
        )

    def lookup_concepts(
        self,
        router: SchemaRouter,
        query: str,
        *,
        catalog: NativeConceptCatalog,
        principal: PrincipalContext,
        k: int = STRICT_K,
        input_free_only: bool = False,
        _research_ranker: Callable[
            [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
        ] | None = None,
    ) -> IndexedNativeFieldResult:
        """Original query → declared concepts → typed field intersection."""
        resolved = resolve_native_concepts(query, catalog=catalog)
        return self.lookup(
            router, query, group=resolved.field_group, principal=principal,
            k=k, input_free_only=input_free_only, _research_ranker=_research_ranker,
        )
