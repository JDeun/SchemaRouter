"""Prepared schema-only field routing over host-owned provider contracts.

One reusable public entry point for the original-paper P1/P2 proof path.
Schema lookup never invokes *data* providers or retrieves records; the
optional model-assisted method calls only the application's supplied model.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Container
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .canonical_json import canonical_json_sha256
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .host_field_contract import _policy_contents_digest
from .models import ToolResult
from .native_graph_index import NativeSchemaGraphIndex
from .native_semantic_index import (
    NativeSchemaPostingIndex,
    _indexable_semantic_field,
    _native_review_cursor,
)
from .paper_field_retrieval import PaperFieldCoverage, retrieve_paper_field_coverage
from .paper_native_rank import PaperNativeRankPolicy
from .paper_query_understanding import PaperFieldModel, compile_model_query
from .paper_typed_tool_plan import (
    PaperPlanParameterMeta,
    PaperTypedToolPlan,
    _paper_public_parameters,
    compile_paper_typed_tool_plan,
)
from .paper_understood_direct_plan import PaperIntentRegistry, PaperUnderstanding
from .paper_understood_graph_plan import compile_paper_understood_graph_plan
from .registry import InMemoryRegistry, SQLiteRegistry

if TYPE_CHECKING:
    from .runtime import SchemaRouter

_MAX_REVIEW_FIELDS_PER_ROUTE = 512
_MAX_REVIEW_FIELDS_PER_PAGE = 2048
_MAX_REVIEW_PARAMETERS_PER_ROUTE = 512
_MAX_REVIEW_PARAMETERS_PER_PAGE = 2048
_MAX_REVIEW_PAGE_BYTES = 262144


@dataclass(frozen=True, slots=True)
class SchemaFieldReviewField:
    """One authorized public scalar source field, not an approved concept."""

    name: str
    semantic_id: str
    json_type: str
    unit: str | None
    identifier: bool


@dataclass(frozen=True, slots=True)
class SchemaFieldReviewRoute:
    """Minimal current-scoped schema descriptor for a human owner review."""

    route_id: str
    source_type: str | None
    license: str | None
    fields: tuple[SchemaFieldReviewField, ...]
    parameters_meta: tuple[PaperPlanParameterMeta, ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaFieldReviewPage:
    """Bounded current-visible field inventory, never executable authority."""

    snapshot_id: str
    registry_version: int
    routes: tuple[SchemaFieldReviewRoute, ...]
    next_after_route: str | None
    executable_authority: bool = False


def _attest_visible_review_route(
    router: SchemaRouter,
    index: NativeSchemaPostingIndex,
    *,
    route_id: str,
    indexed_semantic_ids: Container[str],
    principal: PrincipalContext,
    permitted: Callable[[Any, Any], bool],
    availability: Callable[[Any, Any], bool] | None,
) -> SchemaFieldReviewRoute | None:
    """Project the ORIGINAL current source; never release index postings raw."""
    try:
        location = index.route_locations[route_id]
        tool = router.registry.get(location[0])
        endpoint = tool.endpoint(location[1])
        if (tool.fingerprint, endpoint.fingerprint) != index.route_fingerprints[route_id]:
            raise PolicyViolationError("field review source fingerprint changed")
        if (
            not tool.source_type or not tool.license
            or endpoint.read_only is not True or endpoint.destructive is True
            or not permitted(tool.model_copy(deep=True), endpoint.model_copy(deep=True))
        ):
            return None
        # A host callback may mutate its argument models; those are not
        # trusted field evidence. Never project or compare the callback's
        # mutable copies against the source-derived posting semantics.
        if availability is not None and not bool(availability(
            tool.model_copy(deep=True), endpoint.model_copy(deep=True),
        )):
            return None
        scoped = router._data_scope_endpoint_view(principal, tool, endpoint)
        if scoped is None:
            return None
        restricted = scoped is not endpoint
        if restricted:
            # The source route identifier itself can echo an output-field
            # name hidden by DataScopeRule. Reuse the runtime's same denied
            # name/alias boundary rather than inventing a weaker tokenizer.
            from .runtime import (
                _scoped_denied_field_markers,
                _scoped_echoes_denied_label,
            )

            visible_names = {field.name for field in scoped.output_fields}
            denied_labels = _scoped_denied_field_markers(
                endpoint.output_fields, visible_names,
            )
            if _scoped_echoes_denied_label(route_id, denied_labels):
                return None
        fields = tuple(sorted((
            SchemaFieldReviewField(
                name=field.name,
                semantic_id=field.semantic_id,
                json_type=field.json_schema["type"],
                unit=field.unit,
                identifier=field.identifier,
            )
            for field in scoped.output_fields
            if field.semantic_id is not None
            and field.semantic_id in indexed_semantic_ids
            and _indexable_semantic_field(field)
        ), key=lambda item: (item.semantic_id, item.name)))
        if not fields:
            return None
        # Detect even callbacks that mutate the registry through another
        # reference rather than their disposable argument objects.
        current_tool = router.registry.get(location[0])
        current_endpoint = current_tool.endpoint(location[1])
        if (
            current_tool.fingerprint, current_endpoint.fingerprint,
        ) != index.route_fingerprints[route_id]:
            raise PolicyViolationError("field review source fingerprint changed")
        # Restricted route-level provenance may carry denied field labels.
        return SchemaFieldReviewRoute(
            route_id=route_id,
            source_type=None if restricted else tool.source_type,
            license=None if restricted else tool.license,
            fields=fields,
            parameters_meta=_paper_public_parameters(scoped),
        )
    except Exception:
        # This includes PolicyViolationError raised BY callbacks/source plugins:
        # even a policy error may contain an unauthorized field name.
        raise PolicyViolationError("field review source verification failed") from None


@dataclass(frozen=True, slots=True)
class SchemaFieldRoutingSession:
    """Reuse an attested index to locate necessary schema fields, not records.

    The index is tied to one exact router registry revision. ``refresh``
    returns a new pinned session after verified schema changes; no background
    provider query is ever performed.
    Authorization and scoped visibility are checked live on *every* query.
    """

    # No authorization-neutral posting IDs, route fingerprints or owner
    # declarations may leak through repr/logging of this public handle.
    _router: SchemaRouter = field(repr=False)
    _catalog: NativeConceptCatalog | None = field(repr=False)
    _index: NativeSchemaGraphIndex = field(repr=False)

    @classmethod
    def prepare(
        cls,
        router: SchemaRouter,
        *,
        catalog: NativeConceptCatalog | None = None,
        approved_host_roots: frozenset[str] = frozenset(),
    ) -> SchemaFieldRoutingSession:
        """Index schemas for review; enable routing only with reviewed concepts."""
        if catalog is not None and not isinstance(catalog, NativeConceptCatalog):
            raise ValueError("owner-reviewed concept catalog required")
        if (
            type(approved_host_roots) is not frozenset
            or len(approved_host_roots) > 64
            or any(type(route) is not str for route in approved_host_roots)
        ):
            raise ValueError("explicit bounded host-approved route set required")
        if router.authorization_policy is None:
            raise PolicyViolationError(
                "field routing requires explicit source authorization policy"
            )

        # Revalidate and detach the owner's declaration so later caller-side
        # Pydantic mutation cannot silently change this prepared contract.
        reviewed = (
            NativeConceptCatalog.model_validate(
                catalog.model_dump(mode="python"), strict=True,
            ) if catalog is not None else None
        )
        field_index = NativeSchemaPostingIndex.build(router.registry)
        index = NativeSchemaGraphIndex.build(
            field_index, approved_host_roots=approved_host_roots,
        )
        field_index._assert_source(router)
        return cls(_router=router, _catalog=reviewed, _index=index)

    def refresh(
        self, *, changed_tool_keys: tuple[str, ...] | None = None,
    ) -> SchemaFieldRoutingSession:
        """Produce a new schema-only snapshot from verified native changes.

        The exact built-in registries own their atomic delta journals. Other
        registry implementations must provide bounded changed-tool hints,
        which are exhaustively verified by the original source manifest.
        This never calls data providers or silently falls back to a rebuild.
        The previous immutable handle remains stale after a source change.
        """
        registry = self._router.registry
        if registry is not self._index.field_index.registry_ref:
            raise PolicyViolationError("field session refresh source mismatch")
        if registry.version <= self._index.field_index.registry_version:
            raise PolicyViolationError("field session refresh needs newer source")
        policy = self._router.authorization_policy
        if policy is None:
            raise PolicyViolationError("field session refresh needs authorization policy")
        policy_digest = _policy_contents_digest(policy)

        if changed_tool_keys is None:
            if type(registry) is InMemoryRegistry:
                updated = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
                    self._index, registry,
                )
            elif type(registry) is SQLiteRegistry:
                updated = NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                    self._index, registry,
                )
            else:
                raise PolicyViolationError(
                    "custom registry requires verified changed-tool keys"
                )
        else:
            posting = NativeSchemaPostingIndex.refresh(
                self._index.field_index, registry,
                changed_tool_keys=changed_tool_keys,
            )
            updated = NativeSchemaGraphIndex.refresh(
                self._index, posting, changed_tool_keys=changed_tool_keys,
            )

        updated.field_index._assert_source(self._router)
        if (
            self._router.authorization_policy is not policy
            or _policy_contents_digest(policy) != policy_digest
        ):
            raise PolicyViolationError(
                "field session authorization policy changed during refresh"
            )
        reviewed = (
            NativeConceptCatalog.model_validate(
                self._catalog.model_dump(mode="python"), strict=True,
            ) if self._catalog is not None else None
        )
        return SchemaFieldRoutingSession(
            _router=self._router, _catalog=reviewed, _index=updated,
        )

    def revise_catalog(
        self, *, catalog: NativeConceptCatalog,
        approved_host_roots: frozenset[str] | None = None,
    ) -> SchemaFieldRoutingSession:
        """Atomically replace host-reviewed meanings and optional input roots.

        Omitted roots retain the exact graph; explicit root replacement uses
        the same-source canonical incremental edge delta, never a full scan.
        Registry changes require ``refresh``; owner review changes do not.
        The host must replace/retire its old session reference explicitly;
        this operation does not revoke separately retained old handles.
        """
        if not isinstance(catalog, NativeConceptCatalog):
            raise ValueError("owner-reviewed concept catalog required")
        policy = self._router.authorization_policy
        if policy is None:
            raise PolicyViolationError(
                "field session catalog revision needs authorization policy"
            )
        policy_digest = _policy_contents_digest(policy)
        try:
            self._index.field_index._assert_source(self._router)
        except Exception:
            raise PolicyViolationError(
                "field session catalog revision source verification failed"
            ) from None

        # Revalidate and detach from the caller's mutable Pydantic object.
        # Neither the source postings nor approved host roots are rebuilt.
        reviewed = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
        updated = (
            self._index if approved_host_roots is None
            else self._index.revise_host_roots(
                approved_host_roots=approved_host_roots,
            )
        )
        try:
            self._index.field_index._assert_source(self._router)
        except Exception:
            raise PolicyViolationError(
                "field session catalog revision source verification failed"
            ) from None
        if (
            self._router.authorization_policy is not policy
            or _policy_contents_digest(policy) != policy_digest
        ):
            raise PolicyViolationError(
                "field session authorization policy changed during catalog revision"
            )
        return SchemaFieldRoutingSession(
            _router=self._router, _catalog=reviewed, _index=updated,
        )

    @property
    def snapshot_id(self) -> str:
        """Original schema index fingerprint used by every result."""
        return self._index.field_index.snapshot_id

    def _require_catalog(self) -> NativeConceptCatalog:
        if self._catalog is None:
            raise PolicyViolationError(
                "owner-reviewed concept catalog required before field routing"
            )
        return self._catalog

    @property
    def catalog_revision_id(self) -> str:
        """Reviewed semantics/root-approval digest; pair with source snapshot."""
        catalog = self._require_catalog().model_dump(mode="json")
        if not self._index.approved_host_roots:
            return canonical_json_sha256(catalog)
        return canonical_json_sha256({
            "catalog": catalog,
            "approved_host_roots": sorted(self._index.approved_host_roots),
        })

    @property
    def indexed_route_count(self) -> int:
        """Registered endpoint count scanned only during preparation."""
        return self._index.field_index.indexed_route_count

    def inspect_visible_fields(
        self,
        *,
        principal: PrincipalContext,
        after_route: str | None = None,
        limit: int = 32,
    ) -> SchemaFieldReviewPage:
        """Page current authorized native scalar fields for human catalog review.

        This does not infer/approve concepts, reuse permission across pages,
        fetch data or issue provider calls. Returned cursors are opaque sort
        anchors tied to this source snapshot, never executable authority.
        """
        if type(limit) is not int or not 1 <= limit <= 64:
            raise ValueError("field review page limit must be 1..64")
        if after_route is not None and (
            type(after_route) is not str
            or not 1 <= len(after_route) <= 256
            or after_route != after_route.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in after_route)
        ):
            raise ValueError("invalid field review page cursor")
        if not isinstance(principal, PrincipalContext):
            raise PolicyViolationError("field review needs a trusted principal")
        policy = self._router.authorization_policy
        if policy is None:
            raise PolicyViolationError("field review needs explicit source policy")
        witness = self._router._retrieval_authority_witness()
        policy_digest = _policy_contents_digest(policy)
        principal_digest = principal.model_dump_json()
        posting = self._index.field_index
        posting._assert_source(self._router)
        permitted = self._router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("field review source authorization missing")
        availability = self._router.planner.availability_predicate

        # Use the original pinned, authorization-neutral reverse index
        # materialized on source build/refresh. No per-page full posting
        # inversion, global sorting or cursor-hash scan is permitted.
        semantic_ids_by_route = posting.route_semantic_ids
        sorted_routes = posting.review_route_ids
        if (
            bool(posting.postings) and not semantic_ids_by_route
            or len(sorted_routes) != len(semantic_ids_by_route)
            or len(posting.review_cursor_anchors) != len(sorted_routes)
        ):
            raise PolicyViolationError("field review source reverse index missing")
        if after_route is not None and after_route.startswith("sr1:"):
            if len(after_route) != 68 or any(
                char not in "0123456789abcdef" for char in after_route[4:]
            ):
                raise ValueError("invalid field review page cursor")
            anchor = posting.review_cursor_anchors.get(after_route)
            if anchor is None:
                raise ValueError("field review page cursor is not in this source")
            # The hash format is deliberately stable and computable from a
            # public snapshot. A guessed private route must NOT become an
            # existence oracle merely because its source-bound hash exists.
            # Validate current principal visibility before accepting it as a
            # seek anchor; indistinguishable errors cover missing/denied IDs.
            try:
                visible_anchor = _attest_visible_review_route(
                    self._router, posting, route_id=anchor,
                    indexed_semantic_ids=semantic_ids_by_route[anchor],
                    principal=principal, permitted=permitted,
                    availability=availability,
                )
            except Exception:
                visible_anchor = None
            if visible_anchor is None:
                raise ValueError("field review page cursor is not in this source")
            after_route = anchor

        first_index = (
            bisect_right(sorted_routes, after_route) if after_route is not None
            else 0
        )

        reviewed: list[SchemaFieldReviewRoute] = []
        has_more = False
        field_count = 0
        parameter_count = 0
        payload_bytes = 0
        for offset in range(first_index, len(sorted_routes)):
            route_id = sorted_routes[offset]
            current = _attest_visible_review_route(
                self._router, posting, route_id=route_id,
                indexed_semantic_ids=semantic_ids_by_route[route_id],
                principal=principal, permitted=permitted, availability=availability,
            )
            if current is None:
                continue
            if len(reviewed) == limit:
                has_more = True
                break
            # Native route/field names are not size-bounded by their source
            # models. Refuse oversized review pages instead of silently
            # truncating authorized fields or returning unbounded payloads.
            field_count += len(current.fields)
            parameter_count += len(current.parameters_meta)
            payload_bytes += 160 + 6 * sum(
                len(value.encode("utf-8")) for value in (
                    current.route_id,
                    current.source_type or "",
                    current.license or "",
                )
            )
            for item in current.fields:
                payload_bytes += 160 + 6 * sum(
                    len(value.encode("utf-8")) for value in (
                        item.name, item.semantic_id, item.json_type, item.unit or "",
                    )
                )
            for item in current.parameters_meta:
                payload_bytes += 160 + 6 * sum(
                    len(value.encode("utf-8")) for value in (
                        item.name, item.location, *item.json_types,
                    )
                )
            if (
                len(current.fields) > _MAX_REVIEW_FIELDS_PER_ROUTE
                or field_count > _MAX_REVIEW_FIELDS_PER_PAGE
                or len(current.parameters_meta) > _MAX_REVIEW_PARAMETERS_PER_ROUTE
                or parameter_count > _MAX_REVIEW_PARAMETERS_PER_PAGE
                or payload_bytes > _MAX_REVIEW_PAGE_BYTES
            ):
                raise PolicyViolationError("field review page budget exceeded")
            reviewed.append(current)

        # Catch one-shot callback state changes during scanning or a later
        # route's initial recheck. This is NOT an atomic health snapshot:
        # arbitrary stateful availability callbacks need host-side versioning.
        for _ in range(2):
            for emitted in reviewed:
                current = _attest_visible_review_route(
                    self._router, posting, route_id=emitted.route_id,
                    indexed_semantic_ids=semantic_ids_by_route[emitted.route_id],
                    principal=principal, permitted=permitted,
                    availability=availability,
                )
                if current != emitted:
                    raise PolicyViolationError("field review eligibility changed")
        posting._assert_source(self._router)
        self._router._check_retrieval_authority_witness(witness)
        if (
            self._router.authorization_policy is not policy
            or _policy_contents_digest(policy) != policy_digest
            or principal.model_dump_json() != principal_digest
        ):
            raise PolicyViolationError("field review authorization changed")
        return SchemaFieldReviewPage(
            snapshot_id=posting.snapshot_id,
            registry_version=posting.registry_version,
            routes=tuple(reviewed),
            next_after_route=(
                _native_review_cursor(posting.snapshot_id, reviewed[-1].route_id)
                if has_more else None
            ),
        )

    def discover(
        self,
        query: str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> PaperFieldCoverage:
        """Return field-complete route alternatives or abstain; no data I/O."""
        catalog = self._require_catalog()
        return retrieve_paper_field_coverage(
            self._router, query, principal=principal,
            catalog=catalog, index=self._index, k=k,
            experimental_indexed_direct=True,
        )

    def compile(
        self,
        query: str,
        *,
        principal: PrincipalContext,
        alternative_index: int = 0,
        host_source_arguments: dict[str, dict[str, Any]] | None = None,
        k: int = 5,
    ) -> PaperTypedToolPlan:
        """Describe typed call shapes, bindings and field metadata, not execution.

        Even a `ready` receipt is not an executable authorization grant.
        """
        catalog = self._require_catalog()
        return compile_paper_typed_tool_plan(
            self._router, query, principal=principal,
            catalog=catalog, index=self._index,
            alternative_index=alternative_index,
            host_source_arguments=host_source_arguments, k=k,
            experimental_indexed_direct=True,
        )

    def compile_understood(
        self,
        understanding: PaperUnderstanding,
        *,
        principal: PrincipalContext,
        intent_registry: PaperIntentRegistry,
        host_source_arguments: dict[str, dict[str, Any]] | None = None,
        k: int = 5,
        max_hops: int = 2,
        rank_policy: PaperNativeRankPolicy | None = None,
        allow_unnamed_graph_discovery: bool = False,
    ) -> PaperTypedToolPlan:
        """Compile untrusted structured Understand(q) hints to a source-proven plan.

        Only the host-reviewed intent/concept catalog defines field meanings.
        Model parameter hints are never treated as host-supplied arguments.
        No model or provider is invoked, even for a `ready` receipt.
        """
        catalog = self._require_catalog()
        return compile_paper_understood_graph_plan(
            self._router, understanding, principal=principal,
            catalog=catalog, intent_registry=intent_registry,
            index=self._index, host_source_arguments=host_source_arguments,
            k=k, max_hops=max_hops,
            rank_policy=rank_policy,
            allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
        )

    async def aexecute_direct(
        self,
        query: str,
        *,
        principal: PrincipalContext,
        host_source_arguments: dict[str, dict[str, Any]] | None = None,
        alternative_index: int = 0,
        k: int = 5,
    ) -> list[ToolResult]:
        """Opt-in, single read-only P2 direct route via the existing executor.

        A paper receipt never grants execution. Recompile against current
        principal/source state, refuse dependencies and incomplete arguments,
        and pin the native invoker generation across the actual dispatch.
        """
        from copy import deepcopy

        from .executor import _require_bound_invoker_generation
        from .models import ExecutionPlan
        from .paper_typed_tool_plan import _check_current_call_scopes
        from .runs import ExecutionBudget, RunConfig

        catalog = self._require_catalog()
        host_inputs = deepcopy(host_source_arguments)
        plan = compile_paper_typed_tool_plan(
            self._router, query, principal=principal,
            catalog=catalog, index=self._index,
            alternative_index=alternative_index,
            host_source_arguments=host_inputs, k=k,
            experimental_indexed_direct=True,
        )
        if (
            plan.status != "ready" or plan.executable_authority
            or plan.bindings or len(plan.calls) != 1
        ):
            raise PolicyViolationError(
                "paper direct execution requires one ready independent route"
            )
        selected = plan.calls[0]
        if not selected.call.executable or selected.call.missing_required_arguments:
            raise PolicyViolationError("paper direct execution has unresolved inputs")
        executor = self._router.executor
        binding = executor._binding_snapshot(selected.call.tool)
        if binding.invoker is None or binding.generation is None:
            raise PolicyViolationError("paper direct native invoker unavailable")

        def revalidate() -> None:
            self._index.field_index._assert_source(self._router)
            current = compile_paper_typed_tool_plan(
                self._router, query, principal=principal,
                catalog=catalog, index=self._index,
                alternative_index=alternative_index,
                host_source_arguments=deepcopy(host_inputs), k=k,
                experimental_indexed_direct=True,
            )
            if current != plan or self._router.executor is not executor:
                raise PolicyViolationError("paper direct proof changed before dispatch")
            if executor._binding_snapshot(selected.call.tool) != binding:
                raise PolicyViolationError("paper direct invoker binding changed")
            _check_current_call_scopes(self._router, principal, [selected])
            tool = self._router.registry.get(selected.call.tool)
            endpoint = tool.endpoint(selected.call.endpoint)
            if endpoint.read_only is not True or endpoint.destructive is True:
                raise PolicyViolationError("paper direct route is not read-only")
            availability = self._router.planner.availability_predicate
            if availability is not None and not availability(tool, endpoint):
                raise PolicyViolationError("paper direct route unavailable")
            # Availability is host-supplied executable code. It may mutate
            # policy, source declarations or bindings while returning True.
            self._index.field_index._assert_source(self._router)
            if (
                compile_paper_typed_tool_plan(
                    self._router, query, principal=principal,
                    catalog=catalog, index=self._index,
                    alternative_index=alternative_index,
                    host_source_arguments=deepcopy(host_inputs), k=k,
                    experimental_indexed_direct=True,
                ) != plan
                or self._router.executor is not executor
                or executor._binding_snapshot(selected.call.tool) != binding
            ):
                raise PolicyViolationError("paper direct source changed during availability")
            _check_current_call_scopes(self._router, principal, [selected])

        revalidate()
        with _require_bound_invoker_generation(
            executor, selected.call.tool, binding.generation,
        ):
            return await self._router.execute(
                ExecutionPlan(
                    query=query, registry_version=plan.registry_version,
                    calls=[selected.call.model_copy(deep=True)],
                ),
                config=RunConfig(
                    principal=principal.model_copy(deep=True),
                    budget=ExecutionBudget(
                        max_tool_calls=1, max_attempts=1,
                        max_remote_attempts=1,
                    ),
                ),
            )

    async def acompile_query(
        self,
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
        """Use a caller-owned model to suggest IDs, then prove source fields.

        No provider data is fetched. The model cannot authorize a route,
        expand source scope, or bind its proposed argument values.
        """
        self._require_catalog()
        return await compile_model_query(
            self, query, principal=principal, model=model,
            intent_registry=intent_registry,
            model_visible_intent_ids=model_visible_intent_ids,
            model_visible_concept_ids=model_visible_concept_ids,
            model_visible_tool_keys=model_visible_tool_keys,
            host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
            max_model_input_bytes=max_model_input_bytes,
            max_model_output_bytes=max_model_output_bytes,
            rank_policy=rank_policy,
            allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
        )
