"""Versioned catalog-wide *structural* semantic postings, opt-in E0.

The registry stores ALL native tool contracts; this index stores only
verified scalar semantic postings and source revisions. Query-time checks
use the original principal/policy/data scope and availability. It is not
an execution engine, graph path planner, or new lexical ranker.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from .errors import PolicyViolationError
from .field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _scalar_contract,
)
from .models import ToolSpec
from .registry import ToolRegistry

if TYPE_CHECKING:
    from .runtime import SchemaRouter

STRICT_K = 5


@dataclass(frozen=True, slots=True)
class IndexedNativeFieldCandidate:
    """Source-scoped evidence ONLY; not an authorized tool execution token."""

    route_id: str
    tool_fingerprint: str
    endpoint_fingerprint: str
    required_output_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexedNativeFieldResult:
    status: Literal["complete", "no_proven_hit", "over_k_unranked"]
    registry_version: int
    index_snapshot_id: str
    requested_k: int
    qualified_count: int
    candidates: tuple[IndexedNativeFieldCandidate, ...]


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

    @classmethod
    def build(cls, registry: ToolRegistry) -> NativeSchemaPostingIndex:
        version = registry.version
        semantic: dict[str, set[str]] = {}
        revisions: dict[str, tuple[str, str]] = {}
        locations: dict[str, tuple[str, str]] = {}
        count = 0
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                count += 1
                route = f"{tool.key}.{endpoint.name}"
                if route in revisions:
                    raise ValueError("duplicated registered native route")
                revisions[route] = (tool.fingerprint, endpoint.fingerprint)
                locations[route] = (tool.key, endpoint.name)
                # Index all schema nodes but only scalar source-typed output
                # semantics; no inferred IDs from descriptions or task gold.
                if not tool.source_type or not tool.license:
                    continue
                for field in endpoint.output_fields:
                    if (field.semantic_id is not None
                            and field.unit_normalization is None
                            and _scalar_contract(field.json_schema)):
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
    ) -> IndexedNativeFieldResult:
        """Conjunctive source-owned FieldGroup lookup with strict no-rank K5."""
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
        if _alias_key(query) not in {_alias_key(a) for a in declaration.aliases}:
            raise ValueError("no host-approved query-to-FieldGroup edge")
        if router.authorization_policy is None:
            raise PolicyViolationError("explicit authorization policy required")
        self._assert_source(router)
        witness = router._retrieval_authority_witness()
        original_policy = router.authorization_policy.model_dump(mode="json")
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
            if not permitted(tool, endpoint):
                continue
            if availability is not None and not availability(tool, endpoint):
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
        self._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        if router.authorization_policy.model_dump(mode="json") != original_policy:
            raise PolicyViolationError("authorization policy changed during indexed lookup")
        count = len(qualified)
        return IndexedNativeFieldResult(
            status=(
                "over_k_unranked" if count > k else
                "complete" if count else "no_proven_hit"
            ),
            registry_version=self.registry_version,
            index_snapshot_id=self.snapshot_id,
            requested_k=k,
            qualified_count=count,
            candidates=tuple(qualified) if count <= k else (),
        )

    def lookup_concepts(
        self,
        router: SchemaRouter,
        query: str,
        *,
        catalog: NativeConceptCatalog,
        principal: PrincipalContext,
        k: int = STRICT_K,
    ) -> IndexedNativeFieldResult:
        """Original query → declared concepts → typed field intersection."""
        resolved = resolve_native_concepts(query, catalog=catalog)
        return self.lookup(
            router, query, group=resolved.field_group, principal=principal, k=k,
        )
