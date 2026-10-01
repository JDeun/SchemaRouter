from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from typing import Any, TypeVar
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import TypeAdapter

from .adapters.base import AdapterRegistry, SourceAdapter
from .adapters.mcp import MCPClientFactory
from .adapters.openapi import OpenAPIRemoteInvoker
from .adapters.plugins import load_adapter_plugins as _load_adapter_plugins
from .adapters.python import PythonCallableInvoker, callable_options, tool_from_callable
from .amendment import validate_amendment
from .errors import (
    BindingDriftError,
    InvocationUnavailableError,
    ProposalApprovalError,
    RegistrationError,
    SchemaSourceError,
)
from .executor import BoundEndpointInvoker, ExecutionBudgetTracker, RegistryExecutor
from .health import AccessHealthMonitor, HealthProbe, HealthProbeSnapshot
from .hooks import ExecutionHooks
from .ingestion import SourceKind, URLSchemaLoader
from .inspection import RouterInspection, inspect_router
from .models import CapabilityRetrieval, ExecutionPlan, PlanRequest, ToolResult, ToolSpec
from .planner import QueryAnalyzer, SchemaPlanner
from .policy import ApprovalCallback, ExecutionPolicy
from .proposals import DocumentationModelCallable, SchemaProposal, inspect_documentation_url
from .registry import InMemoryRegistry, ToolRegistry, replace_if_current
from .runs import RunConfig, RunEvent
from .schema_diff import SchemaRefreshResult, compare_tool_specs
from .schema_watch import SchemaRefreshWatcher, SchemaWatchSnapshot
from .traces import RunTraceStore

_T = TypeVar("_T")


def _coerce_config(config: RunConfig | dict[str, Any] | None) -> RunConfig:
    if config is None:
        return RunConfig()
    if isinstance(config, RunConfig):
        return config
    return RunConfig.model_validate(config)


def _run_sync(factory: Callable[[], Awaitable[_T]]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        async def await_factory() -> _T:
            return await factory()

        return asyncio.run(await_factory())
    raise RuntimeError(
        "synchronous SchemaRouter API cannot run inside an active event loop; "
        "use the async API instead"
    )


def _stream_sync(factory: Callable[[], AsyncIterator[_T]]) -> Iterator[_T]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "synchronous SchemaRouter streaming cannot run inside an active event loop; "
            "use the async streaming API instead"
        )

    loop = asyncio.new_event_loop()
    iterator = factory()
    try:
        while True:
            try:
                yield loop.run_until_complete(iterator.__anext__())
            except StopAsyncIteration:
                break
    finally:
        aclose = getattr(iterator, "aclose", None)

        async def close_iterator() -> None:
            if not callable(aclose):
                return
            close_result = aclose()
            if inspect.isawaitable(close_result):
                await close_result

        loop.run_until_complete(close_iterator())
        loop.close()


class SchemaRouter:
    """High-level facade for schema-aware planning and execution."""

    def __init__(
        self,
        *,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
        policy: ExecutionPolicy | None = None,
        approval_callback: ApprovalCallback | None = None,
        execution_hooks: ExecutionHooks | None = None,
        registry: ToolRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        structural_retrieval: bool = False,
        unavailable_cooldown_seconds: float = 30.0,
    ) -> None:
        self.registry = registry if registry is not None else InMemoryRegistry()
        self.executor = RegistryExecutor(
            self.registry,
            policy=policy,
            approval_callback=approval_callback,
            hooks=execution_hooks,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
        )
        self.planner = SchemaPlanner(
            self.registry,
            analyzer=analyzer,
            structural_retrieval=structural_retrieval,
            availability_predicate=(
                lambda tool, endpoint: self.executor.is_access_available_for_contract(
                    tool.key,
                    endpoint.name,
                    tool.fingerprint,
                )
            ),
        )
        self.health_monitor = AccessHealthMonitor(self.executor)
        self.loader = URLSchemaLoader(
            self.registry,
            self.executor,
            http_client=http_client,
            adapters=adapter_registry,
        )
        self.schema_watcher = SchemaRefreshWatcher(self.arefresh_schema)

    @property
    def input_schema(self) -> dict[str, Any]:
        return PlanRequest.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any]:
        return TypeAdapter(list[ToolResult]).json_schema()

    @property
    def config_schema(self) -> dict[str, Any]:
        return RunConfig.model_json_schema()

    def inspect(self) -> RouterInspection:
        """Return a privacy-safe live operational snapshot."""
        return inspect_router(self)

    def mark_access_unavailable(
        self,
        tool_key: str,
        endpoint: str,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        """Mark one trusted access path temporarily unavailable."""

        self.executor.mark_access_unavailable(
            tool_key,
            endpoint,
            cooldown_seconds=cooldown_seconds,
        )

    def mark_access_available(self, tool_key: str, endpoint: str) -> None:
        """Clear temporary unavailability for one trusted access path."""

        self.executor.mark_access_available(tool_key, endpoint)

    def unavailable_access_paths(self) -> tuple[tuple[str, str], ...]:
        """Return access paths currently held in the bounded cooldown window."""

        return self.executor.unavailable_access_paths()

    def register_health_probe(
        self,
        tool_key: str,
        endpoint: str,
        probe: HealthProbe,
    ) -> None:
        """Register a trusted local health probe for one read-only access path."""

        self.health_monitor.register(tool_key, endpoint, probe)

    def unregister_health_probe(self, tool_key: str, endpoint: str) -> None:
        self.health_monitor.unregister(tool_key, endpoint)

    def health_snapshots(self) -> tuple[HealthProbeSnapshot, ...]:
        return self.health_monitor.snapshots()

    async def check_health_once(self) -> tuple[HealthProbeSnapshot, ...]:
        return await self.health_monitor.run_once()

    async def start_health_monitor(
        self,
        *,
        interval_seconds: float = 30.0,
        probe_timeout_seconds: float = 5.0,
        max_concurrency: int = 4,
    ) -> None:
        await self.health_monitor.start(
            interval_seconds=interval_seconds,
            probe_timeout_seconds=probe_timeout_seconds,
            max_concurrency=max_concurrency,
        )

    async def stop_health_monitor(self) -> None:
        await self.health_monitor.stop()

    def register_schema_watch(
        self,
        tool_key: str,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
        refresh_timeout_seconds: float = 30.0,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
    ) -> None:
        """Register trusted local periodic refresh configuration for one provider schema."""

        self.registry.get(tool_key)
        self.schema_watcher.register(
            tool_key,
            interval_seconds=interval_seconds,
            apply_compatible=apply_compatible,
            refresh_timeout_seconds=refresh_timeout_seconds,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
        )

    def unregister_schema_watch(self, tool_key: str) -> None:
        self.schema_watcher.unregister(tool_key)

    def schema_watch_snapshots(self) -> tuple[SchemaWatchSnapshot, ...]:
        return self.schema_watcher.snapshots()

    async def check_schema_watches_once(
        self,
        *,
        max_concurrency: int | None = None,
    ) -> tuple[SchemaWatchSnapshot, ...]:
        return await self.schema_watcher.run_once(
            force=True,
            max_concurrency=max_concurrency,
        )

    async def start_schema_watcher(
        self,
        *,
        max_concurrency: int = 4,
        idle_sleep_seconds: float = 30.0,
    ) -> None:
        await self.schema_watcher.start(
            max_concurrency=max_concurrency,
            idle_sleep_seconds=idle_sleep_seconds,
        )

    async def stop_schema_watcher(self) -> None:
        await self.schema_watcher.stop()

    def with_config(
        self,
        config: RunConfig | dict[str, Any],
    ) -> ConfiguredSchemaRouter:
        return ConfiguredSchemaRouter(self, _coerce_config(config))

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
        policy: ExecutionPolicy | None = None,
        approval_callback: ApprovalCallback | None = None,
        execution_hooks: ExecutionHooks | None = None,
        registry: ToolRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        unavailable_cooldown_seconds: float = 30.0,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = 3,
        openapi_ref_max_documents: int = 8,
        openapi_ref_max_bytes: int = 10 * 1024 * 1024,
    ) -> SchemaRouter:
        router = cls(
            analyzer=analyzer,
            http_client=http_client,
            policy=policy,
            approval_callback=approval_callback,
            execution_hooks=execution_hooks,
            registry=registry,
            adapter_registry=adapter_registry,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
        )
        await router.add_url(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
        )
        return router

    def add_tool(self, tool: ToolSpec, *, replace: bool = False) -> str:
        return self.registry.register(tool, replace=replace)

    def add_bound_tool(
        self,
        tool: ToolSpec,
        invoker: BoundEndpointInvoker,
        *,
        replace: bool = False,
    ) -> str:
        """Register a canonical ToolSpec and bind one trusted invoker.

        This is the explicit escape hatch for SDKs and protocol clients that do not expose a
        safely introspectable Python signature. The ToolSpec remains the complete model-visible
        contract; client objects, credentials, and transport state stay inside trusted invoker
        state.
        """

        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(tool.key)
            except KeyError:
                key = self.registry.register(tool)
            else:
                key = replace_if_current(
                    self.registry,
                    tool,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(tool)

        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=tool.fingerprint,
        )
        return key

    def amend_capability(self, tool_key: str, amended: ToolSpec) -> str:
        """Declare or annotate the result contract of an already registered capability.

        Trusted local code may add output-field declarations and annotate their
        meaning: semantic IDs, aliases, paths, units, normalization, qualifiers,
        identifier flags, provenance and licence. It may not change execution
        identity or validation shape; see `amendment.validate_amendment`.

        This is more than cosmetic annotation. Accepted aspects can change what
        the caller receives and which routes are reachable:

        - `path` / `result_path` on an existing field re-point which value a
          sanctioned field name resolves to. Projection is the redaction
          boundary for a field-selecting call, so amending these can move
          previously unprojected response content into the answer under the
          same field name.
        - `unit` and `unit_normalization` change how a numeric value is
          rescaled before it reaches the caller, on the result path (see
          `RegistryExecutor._normalize_projected_units` in `executor.py`).
        - `source_type`, `license`, and `unit` feed evidence availability
          (`evidence.py`), which the executor enforces as a hard gate. An
          amendment can unblock an evidence-gated route by declaration alone,
          with no change to what the underlying source actually returns.
        - Declaring a semantic ID or unit can also change routing outright: it
          may make a cross-provider fallback compatible that previously was
          not.

        Because of this, `amend_capability` is trusted local code, at the same
        grade as `RegistryExecutor.bind()`. It must never be reachable from a
        decision backend, remote content, or model output.

        The execution binding is carried across the amendment, so a capability
        SchemaRouter imported on the application's behalf stays executable. The
        invoker is never exposed to the caller.

        If the capability was already bound and re-stamping the binding fails
        — only possible if another writer replaced the registered spec between
        validation and this call, e.g. a concurrent thread or another process
        on a shared registry — this raises `BindingDriftError` immediately
        instead of returning a key whose binding will only be discovered stale
        at execution time. The amendment itself is still registered; call
        `RegistryExecutor.bind()` again to recover.
        """
        expected_version = self.registry.version
        current = self.registry.get(tool_key)
        validate_amendment(current, amended)
        was_bound = tool_key in self.executor.bound_keys()
        key = replace_if_current(
            self.registry,
            amended,
            expected_fingerprint=current.fingerprint,
            expected_version=expected_version,
        )
        restamped = self.executor.restamp_binding(key, amended.fingerprint)
        if was_bound and not restamped:
            raise BindingDriftError(
                f"amendment of {key!r} was registered, but its existing binding "
                "could not be re-stamped because the registered contract changed "
                "concurrently; the binding is stale until it is bound again"
            )
        return key

    def register_adapter(
        self,
        adapter: SourceAdapter,
        *,
        replace: bool = False,
    ) -> None:
        self.loader.register_adapter(adapter, replace=replace)

    @property
    def adapter_registry(self) -> AdapterRegistry:
        return self.loader.adapters

    def load_adapter_plugins(
        self,
        *,
        allowlist: set[str] | list[str] | tuple[str, ...],
        replace: bool = False,
    ) -> tuple[str, ...]:
        return _load_adapter_plugins(
            self.loader.adapters,
            allowlist=allowlist,
            replace=replace,
        )

    def add_callable(
        self,
        function: Callable[..., Any],
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        description: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        replace: bool = False,
    ) -> str:
        decorated = callable_options(function)
        tool = tool_from_callable(
            function,
            name=name if name is not None else decorated.get("name"),
            namespace=(
                namespace if namespace is not None else decorated.get("namespace")
            ),
            provider=(
                provider if provider is not None else decorated.get("provider")
            ),
            access_mode=(
                access_mode if access_mode is not None else decorated.get("access_mode")
            ),
            description=(
                description if description is not None else decorated.get("description")
            ),
            read_only=(
                read_only if read_only is not None else decorated.get("read_only")
            ),
            destructive=(
                destructive if destructive is not None else decorated.get("destructive")
            ),
        )
        invoker = PythonCallableInvoker(function)
        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(tool.key)
            except KeyError:
                key = self.registry.register(tool)
            else:
                key = replace_if_current(
                    self.registry,
                    tool,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(tool)
        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=tool.fingerprint,
        )
        return key

    def add_langchain_tool(
        self,
        tool: Any,
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        remote: bool = True,
        replace: bool = False,
    ) -> str:
        """Import and bind one LangChain BaseTool-like object.

        SchemaRouter trusts only the tool's declared input/output schemas plus the explicit
        local authority classification supplied here. Descriptions and foreign metadata do not
        grant read/write permission.
        """

        from .integrations.langchain import LangChainToolInvoker, tool_from_langchain

        spec = tool_from_langchain(
            tool,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            read_only=read_only,
            destructive=destructive,
            remote=remote,
        )
        invoker = LangChainToolInvoker(tool)
        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(spec.key)
            except KeyError:
                key = self.registry.register(spec)
            else:
                key = replace_if_current(
                    self.registry,
                    spec,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(spec)

        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=spec.fingerprint,
        )
        return key

    def add_llamaindex_tool(
        self,
        tool: Any,
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        remote: bool = True,
        replace: bool = False,
    ) -> str:
        """Import and bind one LlamaIndex BaseTool-like object."""

        from .integrations.llamaindex import (
            LlamaIndexToolInvoker,
            tool_from_llamaindex,
        )

        spec = tool_from_llamaindex(
            tool,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            read_only=read_only,
            destructive=destructive,
            remote=remote,
        )
        invoker = LlamaIndexToolInvoker(tool)
        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(spec.key)
            except KeyError:
                key = self.registry.register(spec)
            else:
                key = replace_if_current(
                    self.registry,
                    spec,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(spec)

        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=spec.fingerprint,
        )
        return key

    def add_http_tool(
        self,
        tool: ToolSpec,
        *,
        base_url: str,
        provider: str | None = None,
        access_mode: str | None = None,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_response_bytes: int = 10 * 1024 * 1024,
        replace: bool = False,
    ) -> str:
        """Register and bind a trusted declarative HTTP/JSON ToolSpec.

        The supplied ToolSpec is the machine-readable manifest. Authentication remains only in
        trusted_headers and is never copied into model-visible schema metadata.
        """

        from .adapters.http_json import (
            build_http_json_invoker,
            prepare_http_json_tool,
        )

        prepared = prepare_http_json_tool(
            tool,
            base_url=base_url,
            provider=provider,
            access_mode=access_mode,
        )
        invoker = build_http_json_invoker(
            prepared,
            base_url=base_url,
            trusted_headers=trusted_headers,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
            http_client=self.loader.http_client,
        )

        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(prepared.key)
            except KeyError:
                key = self.registry.register(prepared)
            else:
                key = replace_if_current(
                    self.registry,
                    prepared,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(prepared)

        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=prepared.fingerprint,
        )
        return key

    async def inspect_url(
        self,
        url: str,
        *,
        model: DocumentationModelCallable,
        timeout: float = 20.0,
        max_document_chars: int = 60_000,
    ) -> SchemaProposal:
        return await inspect_documentation_url(
            url,
            model=model,
            http_client=self.loader.http_client,
            timeout=timeout,
            max_document_chars=max_document_chars,
        )

    def bind_openapi(
        self,
        tool_key: str,
        *,
        base_url: str,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> None:
        expected_version = self.registry.version
        tool = self.registry.get(tool_key)
        if tool.execution_metadata.get("adapter") != "openapi":
            raise RegistrationError(
                f"tool {tool_key!r} was not imported from OpenAPI"
            )
        try:
            invoker = OpenAPIRemoteInvoker(
                tool,
                base_url,
                trusted_headers=trusted_headers,
                timeout=timeout,
            )
        except ValueError as exc:
            raise RegistrationError("invalid OpenAPI execution binding") from exc
        updated = tool.model_copy(deep=True)
        updated.execution_metadata.update(
            {
                "execution_bound": True,
                "approved_base_url": base_url,
                "requires_explicit_base_url": False,
            }
        )
        updated.metadata.update(
            {
                "execution_bound": True,
                "approved_base_url": base_url,
                "requires_explicit_base_url": False,
            }
        )
        replace_if_current(
            self.registry,
            updated,
            expected_fingerprint=tool.fingerprint,
            expected_version=expected_version,
        )
        self.executor.bind(
            tool_key,
            invoker,
            expected_fingerprint=updated.fingerprint,
        )

    def approve_proposal(
        self,
        proposal: SchemaProposal,
        *,
        base_url: str,
        min_grounding_score: float = 0.8,
        allow_mutations: bool = False,
        replace: bool = False,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> str:
        if proposal.status != "grounded" or proposal.tool is None:
            raise ProposalApprovalError("proposal has no grounded tool to approve")
        if proposal.grounding_score < min_grounding_score:
            raise ProposalApprovalError(
                "proposal grounding score is below the required threshold"
            )

        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProposalApprovalError("base_url must be an absolute http(s) URL")
        if parsed.username or parsed.password:
            raise ProposalApprovalError(
                "credentials must not be embedded in base_url; use trusted runtime auth"
            )

        mutating = [
            endpoint.name
            for endpoint in proposal.tool.endpoints
            if endpoint.method not in {"GET", "HEAD", "OPTIONS"}
        ]
        if mutating and not allow_mutations:
            raise ProposalApprovalError(
                "proposal contains mutating endpoints; set allow_mutations=True "
                "after explicit review"
            )

        tool = proposal.tool.model_copy(deep=True)
        tool.execution_metadata.update(
            {
                "executable": True,
                "approved_base_url": base_url,
            }
        )
        tool.metadata.update(
            {
                "approved_from_proposal": True,
                "executable": True,
                "grounding_score": proposal.grounding_score,
                "approved_base_url": base_url,
            }
        )
        try:
            invoker = OpenAPIRemoteInvoker(
                tool,
                base_url,
                trusted_headers=trusted_headers,
                timeout=timeout,
            )
        except ValueError as exc:
            raise ProposalApprovalError("invalid proposal execution binding") from exc
        if replace:
            expected_version = self.registry.version
            try:
                current = self.registry.get(tool.key)
            except KeyError:
                key = self.registry.register(tool)
            else:
                key = replace_if_current(
                    self.registry,
                    tool,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )
        else:
            key = self.registry.register(tool)
        self.executor.bind(
            key,
            invoker,
            expected_fingerprint=tool.fingerprint,
        )
        return key

    async def add_url(
        self,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        replace: bool = False,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = 3,
        openapi_ref_max_documents: int = 8,
        openapi_ref_max_bytes: int = 10 * 1024 * 1024,
        timeout: float = 20.0,
    ) -> ToolSpec:
        return await self.loader.load(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            replace=replace,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
            timeout=timeout,
        )

    async def arefresh_schema(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        timeout: float = 20.0,
    ) -> SchemaRefreshResult:
        """Reinspect a registered remote schema and apply only proven-compatible drift."""

        expected_version = self.registry.version
        try:
            current = self.registry.get(tool_key)
        except KeyError as exc:
            raise RegistrationError(f"unknown tool: {tool_key}") from exc

        adapter = current.execution_metadata.get("adapter")
        if not isinstance(adapter, str):
            adapter = current.metadata.get("adapter")
        refreshable = {"openapi", "mcp", "optimade", "graphql", "openrpc", "odata"}
        if adapter not in refreshable:
            raise SchemaSourceError(
                f"tool {tool_key!r} does not have a refreshable structured-source adapter"
            )

        source_url: str | None = None
        base_url: str | None = None
        openapi_external_refs = False
        openapi_ref_max_depth = 3
        openapi_ref_max_documents = 8
        openapi_ref_max_bytes = 10 * 1024 * 1024

        if adapter == "optimade":
            raw_source = current.execution_metadata.get("versioned_base_url")
            if not isinstance(raw_source, str) or not raw_source:
                raw_source = current.metadata.get("versioned_base_url")
            if isinstance(raw_source, str) and raw_source:
                source_url = raw_source
        else:
            raw_source = current.metadata.get("source_url")
            if not isinstance(raw_source, str) or not raw_source:
                raw_source = current.execution_metadata.get("source_url")
            if isinstance(raw_source, str) and raw_source:
                source_url = raw_source

        if adapter in {"openapi", "openrpc"}:
            approved_base = current.execution_metadata.get("approved_base_url")
            if isinstance(approved_base, str) and approved_base:
                base_url = approved_base

        if adapter == "openapi":
            openapi_external_refs = bool(
                current.metadata.get("external_refs_enabled", False)
            )
            limits = current.metadata.get("external_ref_limits")
            if isinstance(limits, dict):
                depth = limits.get("max_depth")
                documents = limits.get("max_documents")
                byte_limit = limits.get("max_bytes")
                if isinstance(depth, int) and not isinstance(depth, bool) and depth > 0:
                    openapi_ref_max_depth = depth
                if (
                    isinstance(documents, int)
                    and not isinstance(documents, bool)
                    and documents > 0
                ):
                    openapi_ref_max_documents = documents
                if (
                    isinstance(byte_limit, int)
                    and not isinstance(byte_limit, bool)
                    and byte_limit > 0
                ):
                    openapi_ref_max_bytes = byte_limit

        if source_url is None:
            raise SchemaSourceError(
                f"tool {tool_key!r} is missing persisted source provenance for refresh"
            )

        candidate = await self.loader.inspect(
            source_url,
            kind=adapter,
            name=current.name,
            namespace=current.namespace,
            provider=current.provider,
            access_mode=current.access_mode,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
            timeout=timeout,
        )
        if candidate.tool.key != tool_key:
            raise SchemaSourceError(
                "refreshed schema changed the registered tool key unexpectedly"
            )

        report = compare_tool_specs(current, candidate.tool)
        if report.compatibility == "identical":
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="unchanged",
                applied=False,
                report=report,
            )

        if report.compatibility == "compatible" and apply_compatible:
            self.loader.commit_candidate_if_current(
                candidate,
                expected_fingerprint=current.fingerprint,
                expected_version=expected_version,
            )
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="applied",
                applied=True,
                report=report,
            )

        action = (
            "report_only"
            if report.compatibility == "compatible"
            else "pending_review"
        )
        return SchemaRefreshResult(
            tool_key=tool_key,
            action=action,
            applied=False,
            report=report,
        )

    def refresh_schema(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        timeout: float = 20.0,
    ) -> SchemaRefreshResult:
        """Synchronous wrapper for :meth:`arefresh_schema`."""

        return _run_sync(
            lambda: self.arefresh_schema(
                tool_key,
                apply_compatible=apply_compatible,
                schema_headers=schema_headers,
                trusted_headers=trusted_headers,
                mcp_client_factory=mcp_client_factory,
                timeout=timeout,
            )
        )

    def plan(self, request: PlanRequest | str) -> ExecutionPlan:
        """Schema-aware planning without requiring a currently bound invoker."""

        return self.planner.plan(request)

    async def aplan(self, request: PlanRequest | str) -> ExecutionPlan:
        """Async schema-aware planning without requiring a currently bound invoker."""

        return await self.planner.aplan(request)

    def retrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Return Top-K typed registered capabilities without executing them."""

        return self.planner.retrieve(request, k=k)

    async def aretrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve`."""

        return await self.planner.aretrieve(request, k=k)

    def _binding_ready(self, tool: ToolSpec, endpoint: Any) -> bool:
        del endpoint
        return self.executor.is_binding_ready_for_contract(
            tool.key,
            tool.fingerprint,
        )

    def plan_executable(self, request: PlanRequest | str) -> ExecutionPlan:
        """Plan only across routes that are currently executable by this router instance."""

        return self.planner.plan_with_additional_availability(
            request,
            self._binding_ready,
        )

    async def aplan_executable(self, request: PlanRequest | str) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_executable`."""

        return await self.planner.aplan_with_additional_availability(
            request,
            self._binding_ready,
        )

    def retrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Return Top-K capabilities with a currently ready local binding."""

        return self.planner.retrieve_with_additional_availability(
            request,
            self._binding_ready,
            k=k,
            executable_only=True,
        )

    async def aretrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_executable`."""

        return await self.planner.aretrieve_with_additional_availability(
            request,
            self._binding_ready,
            k=k,
            executable_only=True,
        )

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        run_config: RunConfig,
    ) -> list[ToolResult]:
        if run_config.execution_mode == "parallel_read_only":
            return await self.executor.execute_parallel_read_only(
                plan,
                retry=run_config.retry,
                budget=run_config.budget,
                max_concurrency=run_config.max_parallel_calls,
            )
        return await self.executor.execute(
            plan,
            retry=run_config.retry,
            budget=run_config.budget,
        )

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        run_config = _coerce_config(config)
        return await self._execute_plan(plan, run_config)

    async def ainvoke(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        run_config = _coerce_config(config)
        plan = await self.aplan_executable(request)
        return await self._execute_plan(plan, run_config)

    def invoke(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return _run_sync(lambda: self.ainvoke(request, config=config))

    async def abatch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        run_config = _coerce_config(config)
        semaphore = asyncio.Semaphore(run_config.max_concurrency)

        async def invoke_one(request: PlanRequest | str) -> list[ToolResult]:
            async with semaphore:
                return await self.ainvoke(request, config=run_config)

        return await asyncio.gather(
            *(invoke_one(request) for request in requests),
            return_exceptions=return_exceptions,
        )

    def batch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return _run_sync(
            lambda: self.abatch(
                requests,
                config=config,
                return_exceptions=return_exceptions,
            )
        )

    async def abatch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> AsyncIterator[tuple[int, list[ToolResult] | Exception]]:
        run_config = _coerce_config(config)
        semaphore = asyncio.Semaphore(run_config.max_concurrency)

        async def invoke_indexed(
            index: int,
            request: PlanRequest | str,
        ) -> tuple[int, list[ToolResult] | Exception]:
            try:
                async with semaphore:
                    result = await self.ainvoke(request, config=run_config)
                return index, result
            except Exception as exc:
                if return_exceptions:
                    return index, exc
                raise

        tasks = [
            asyncio.create_task(invoke_indexed(index, request))
            for index, request in enumerate(requests)
        ]
        try:
            for completed in asyncio.as_completed(tasks):
                yield await completed
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def batch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> Iterator[tuple[int, list[ToolResult] | Exception]]:
        return _stream_sync(
            lambda: self.abatch_as_completed(
                requests,
                config=config,
                return_exceptions=return_exceptions,
            )
        )

    async def astream(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> AsyncIterator[ToolResult]:
        run_config = _coerce_config(config)
        plan = await self.aplan_executable(request)
        if run_config.execution_mode == "parallel_read_only":
            async for _, result in self.executor.execute_parallel_read_only_iter(
                plan,
                retry=run_config.retry,
                budget=run_config.budget,
                max_concurrency=run_config.max_parallel_calls,
            ):
                yield result
            return

        async for result in self.executor.execute_iter(
            plan,
            retry=run_config.retry,
            budget=run_config.budget,
        ):
            yield result

    def stream(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> Iterator[ToolResult]:
        return _stream_sync(lambda: self.astream(request, config=config))

    async def astream_events(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
        trace_store: RunTraceStore | None = None,
    ) -> AsyncIterator[RunEvent]:
        run_config = _coerce_config(config)

        async def emit(event: RunEvent) -> RunEvent:
            if trace_store is not None:
                trace_store.append(event)
            return event
        run_id = uuid4().hex
        sequence = 0

        request_payload: dict[str, Any] = {
            "input_type": type(request).__name__,
        }
        if run_config.include_payloads:
            request_payload["input"] = (
                request.model_dump(mode="json")
                if isinstance(request, PlanRequest)
                else request
            )

        yield await emit(RunEvent.create(
            event="run.start",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data=request_payload,
        ))
        sequence += 1

        try:
            plan = await self.aplan_executable(request)
        except Exception as exc:
            data = {"error_type": type(exc).__name__, "stage": "planning"}
            if run_config.include_payloads:
                data["message"] = str(exc)
            yield await emit(RunEvent.create(
                event="run.error",
                run_id=run_id,
                sequence=sequence,
                config=run_config,
                data=data,
            ))
            raise

        plan_data: dict[str, Any] = {
            "call_count": len(plan.calls),
            "fallback_route_count": len(plan.fallback_routes),
            "warnings": list(plan.warnings),
            "execution_mode": run_config.execution_mode,
        }
        if run_config.include_payloads:
            plan_data["plan"] = plan.model_dump(mode="json")
        yield await emit(RunEvent.create(
            event="plan.end",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data=plan_data,
        ))
        sequence += 1

        if run_config.execution_mode == "parallel_read_only":
            try:
                self.executor.validate_parallel_read_only(plan)
            except Exception as exc:
                error_data: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "stage": "execution",
                    "phase": "parallel_preflight",
                }
                if run_config.include_payloads:
                    error_data["message"] = str(exc)
                yield await emit(RunEvent.create(
                    event="run.error",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    data=error_data,
                ))
                raise

            budget_tracker = ExecutionBudgetTracker(run_config.budget)
            semaphore = asyncio.Semaphore(run_config.max_parallel_calls)
            event_queue: asyncio.Queue[
                tuple[str, int, Any, Any]
            ] = asyncio.Queue()

            async def run_parallel_call(
                index: int,
                primary_call: Any,
            ) -> None:
                async with semaphore:
                    route = plan.fallback_route(index)
                    alternatives = route.alternatives if route is not None else []
                    original_chain = [primary_call, *alternatives]
                    try:
                        chain = (
                            self.executor.ordered_available_fallback_chain(
                                primary_call,
                                alternatives,
                            )
                            if alternatives
                            else [primary_call]
                        )
                    except Exception as exc:
                        await event_queue.put(
                            ("preflight_error", index, primary_call, exc)
                        )
                        return

                    if chain and chain[0] is not primary_call:
                        await event_queue.put(
                            (
                                "cooldown_fallback",
                                index,
                                primary_call,
                                (chain[0], original_chain, chain),
                            )
                        )

                    for candidate_index, call in enumerate(chain):
                        original_candidate_index = next(
                            position
                            for position, candidate in enumerate(original_chain)
                            if candidate is call
                        )
                        await event_queue.put(
                            ("start", index, call, original_candidate_index)
                        )
                        try:
                            result = await self.executor.execute_call(
                                call,
                                retry=run_config.retry,
                                budget=run_config.budget,
                                _tracker=budget_tracker,
                            )
                        except InvocationUnavailableError as exc:
                            has_next = candidate_index + 1 < len(chain)
                            next_call = (
                                chain[candidate_index + 1]
                                if has_next
                                else None
                            )
                            await event_queue.put(
                                (
                                    "unavailable",
                                    index,
                                    call,
                                    (exc, next_call, original_candidate_index),
                                )
                            )
                            if has_next:
                                continue
                            return
                        except Exception as exc:
                            await event_queue.put(("error", index, call, exc))
                            return
                        await event_queue.put(
                            ("end", index, call, (result, original_candidate_index))
                        )
                        return

            tasks = [
                asyncio.create_task(run_parallel_call(index, call))
                for index, call in enumerate(plan.calls)
            ]

            result_count = 0
            fallback_count = 0
            terminal_count = 0
            try:
                while terminal_count < len(tasks):
                    kind, index, call, payload = await event_queue.get()

                    if kind == "preflight_error":
                        terminal_count += 1
                        assert isinstance(payload, Exception)
                        error_data: dict[str, Any] = {
                            "error_type": type(payload).__name__,
                            "stage": "execution",
                            "phase": "fallback_preflight",
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(payload)
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data=error_data,
                        ))
                        raise payload

                    if kind == "cooldown_fallback":
                        next_call, original_chain, available_chain = payload
                        current_tool = self.registry.get(call.tool)
                        next_tool = self.registry.get(next_call.tool)
                        scope = (
                            "same_provider"
                            if current_tool.provider is not None
                            and current_tool.provider == next_tool.provider
                            else "cross_provider"
                        )
                        skipped = [
                            f"{candidate.tool}.{candidate.endpoint}"
                            for candidate in original_chain
                            if candidate not in available_chain
                        ]
                        reason = (
                            "binding_unavailable"
                            if call.tool_fingerprint is not None
                            and not self.executor.is_binding_ready_for_contract(
                                call.tool,
                                call.tool_fingerprint,
                            )
                            else "cooldown"
                        )
                        yield await emit(RunEvent.create(
                            event="tool.fallback",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=next_call.tool,
                            endpoint=next_call.endpoint,
                            data={
                                "from_tool": call.tool,
                                "from_endpoint": call.endpoint,
                                "to_tool": next_call.tool,
                                "to_endpoint": next_call.endpoint,
                                "scope": scope,
                                "provider": next_tool.provider,
                                "access_mode": next_tool.access_mode,
                                "reason": reason,
                                "skipped_unavailable": skipped,
                            },
                        ))
                        sequence += 1
                        fallback_count += 1
                        continue

                    if kind == "start":
                        candidate_index = int(payload)
                        start_data: dict[str, Any] = {
                            "argument_names": sorted(call.arguments),
                            "fields": list(call.fields),
                            "fallback_candidate_index": candidate_index,
                        }
                        if run_config.include_payloads:
                            start_data["arguments"] = dict(call.arguments)
                        yield await emit(RunEvent.create(
                            event="tool.start",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=start_data,
                        ))
                        sequence += 1
                        continue

                    if kind == "unavailable":
                        exc, next_call, candidate_index = payload
                        assert isinstance(exc, InvocationUnavailableError)
                        has_next = next_call is not None
                        error_data: dict[str, Any] = {
                            "error_type": type(exc).__name__,
                            "fallback_eligible": has_next,
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(exc)
                        yield await emit(RunEvent.create(
                            event="tool.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=error_data,
                        ))
                        sequence += 1

                        if not has_next:
                            terminal_count += 1
                            yield await emit(RunEvent.create(
                                event="run.error",
                                run_id=run_id,
                                sequence=sequence,
                                config=run_config,
                                data={
                                    "error_type": type(exc).__name__,
                                    "stage": "execution",
                                },
                            ))
                            raise exc

                        current_tool = self.registry.get(call.tool)
                        next_tool = self.registry.get(next_call.tool)
                        scope = (
                            "same_provider"
                            if current_tool.provider is not None
                            and current_tool.provider == next_tool.provider
                            else "cross_provider"
                        )
                        yield await emit(RunEvent.create(
                            event="tool.fallback",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=next_call.tool,
                            endpoint=next_call.endpoint,
                            data={
                                "from_tool": call.tool,
                                "from_endpoint": call.endpoint,
                                "to_tool": next_call.tool,
                                "to_endpoint": next_call.endpoint,
                                "scope": scope,
                                "provider": next_tool.provider,
                                "access_mode": next_tool.access_mode,
                                "fallback_candidate_index": candidate_index + 1,
                            },
                        ))
                        sequence += 1
                        fallback_count += 1
                        continue

                    if kind == "error":
                        terminal_count += 1
                        assert isinstance(payload, Exception)
                        error_data = {"error_type": type(payload).__name__}
                        if run_config.include_payloads:
                            error_data["message"] = str(payload)
                        yield await emit(RunEvent.create(
                            event="tool.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=error_data,
                        ))
                        sequence += 1
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data={
                                "error_type": type(payload).__name__,
                                "stage": "execution",
                            },
                        ))
                        raise payload

                    if kind != "end":
                        raise RuntimeError("invalid parallel execution event")

                    terminal_count += 1
                    result, candidate_index = payload
                    if not isinstance(result, ToolResult):
                        raise RuntimeError("invalid parallel execution result")
                    end_data: dict[str, Any] = {
                        "projected_fields": list(result.projected_fields),
                        "fallback_used": candidate_index > 0,
                    }
                    if run_config.include_payloads:
                        end_data["result"] = result.model_dump(mode="json")
                    yield await emit(RunEvent.create(
                        event="tool.end",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=result.tool,
                        endpoint=result.endpoint,
                        data=end_data,
                    ))
                    sequence += 1
                    result_count += 1
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            yield await emit(RunEvent.create(
                event="run.end",
                run_id=run_id,
                sequence=sequence,
                config=run_config,
                data={
                    "result_count": result_count,
                    "fallback_count": fallback_count,
                },
            ))
            return

        result_count = 0
        fallback_count = 0
        budget_tracker = ExecutionBudgetTracker(run_config.budget)
        for primary_index, primary_call in enumerate(plan.calls):
            route = plan.fallback_route(primary_index)
            alternatives = route.alternatives if route is not None else []
            original_chain = [primary_call, *alternatives]
            result: ToolResult | None = None

            try:
                chain = (
                    self.executor.ordered_available_fallback_chain(
                        primary_call,
                        alternatives,
                    )
                    if alternatives
                    else [primary_call]
                )
            except Exception as exc:
                error_data: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "stage": "execution",
                    "phase": "fallback_preflight",
                }
                if run_config.include_payloads:
                    error_data["message"] = str(exc)
                yield await emit(RunEvent.create(
                    event="run.error",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    data=error_data,
                ))
                raise

            if chain and chain[0] is not primary_call:
                next_call = chain[0]
                next_tool = self.registry.get(next_call.tool)
                current_tool = self.registry.get(primary_call.tool)
                scope = (
                    "same_provider"
                    if current_tool.provider is not None
                    and current_tool.provider == next_tool.provider
                    else "cross_provider"
                )
                skipped = [
                    f"{call.tool}.{call.endpoint}"
                    for call in original_chain
                    if call not in chain
                ]
                reason = (
                    "binding_unavailable"
                    if primary_call.tool_fingerprint is not None
                    and not self.executor.is_binding_ready_for_contract(
                        primary_call.tool,
                        primary_call.tool_fingerprint,
                    )
                    else "cooldown"
                )
                yield await emit(RunEvent.create(
                    event="tool.fallback",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=next_call.tool,
                    endpoint=next_call.endpoint,
                    data={
                        "from_tool": primary_call.tool,
                        "from_endpoint": primary_call.endpoint,
                        "to_tool": next_call.tool,
                        "to_endpoint": next_call.endpoint,
                        "scope": scope,
                        "provider": next_tool.provider,
                        "access_mode": next_tool.access_mode,
                        "reason": reason,
                        "skipped_unavailable": skipped,
                    },
                ))
                sequence += 1
                fallback_count += 1

            for candidate_index, call in enumerate(chain):
                original_candidate_index = next(
                    index
                    for index, candidate in enumerate(original_chain)
                    if candidate is call
                )
                start_data: dict[str, Any] = {
                    "argument_names": sorted(call.arguments),
                    "fields": list(call.fields),
                    "fallback_candidate_index": original_candidate_index,
                }
                if run_config.include_payloads:
                    start_data["arguments"] = dict(call.arguments)
                yield await emit(RunEvent.create(
                    event="tool.start",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=start_data,
                ))
                sequence += 1

                try:
                    result = await self.executor.execute_call(
                        call,
                        retry=run_config.retry,
                        budget=run_config.budget,
                        _tracker=budget_tracker,
                    )
                except InvocationUnavailableError as exc:
                    has_next = candidate_index + 1 < len(chain)
                    error_data: dict[str, Any] = {
                        "error_type": type(exc).__name__,
                        "fallback_eligible": has_next,
                    }
                    if run_config.include_payloads:
                        error_data["message"] = str(exc)
                    yield await emit(RunEvent.create(
                        event="tool.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=call.tool,
                        endpoint=call.endpoint,
                        data=error_data,
                    ))
                    sequence += 1

                    if not has_next:
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data={
                                "error_type": type(exc).__name__,
                                "stage": "execution",
                            },
                        ))
                        raise

                    next_call = chain[candidate_index + 1]
                    current_tool = self.registry.get(call.tool)
                    next_tool = self.registry.get(next_call.tool)
                    scope = (
                        "same_provider"
                        if current_tool.provider is not None
                        and current_tool.provider == next_tool.provider
                        else "cross_provider"
                    )
                    yield await emit(RunEvent.create(
                        event="tool.fallback",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=next_call.tool,
                        endpoint=next_call.endpoint,
                        data={
                            "from_tool": call.tool,
                            "from_endpoint": call.endpoint,
                            "to_tool": next_call.tool,
                            "to_endpoint": next_call.endpoint,
                            "scope": scope,
                            "provider": next_tool.provider,
                            "access_mode": next_tool.access_mode,
                        },
                    ))
                    sequence += 1
                    fallback_count += 1
                    continue
                except Exception as exc:
                    error_data = {"error_type": type(exc).__name__}
                    if run_config.include_payloads:
                        error_data["message"] = str(exc)
                    yield await emit(RunEvent.create(
                        event="tool.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=call.tool,
                        endpoint=call.endpoint,
                        data=error_data,
                    ))
                    sequence += 1
                    yield await emit(RunEvent.create(
                        event="run.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        data={
                            "error_type": type(exc).__name__,
                            "stage": "execution",
                        },
                    ))
                    raise

                end_data: dict[str, Any] = {
                    "projected_fields": list(result.projected_fields),
                    "fallback_used": candidate_index > 0,
                }
                if run_config.include_payloads:
                    end_data["result"] = result.model_dump(mode="json")
                yield await emit(RunEvent.create(
                    event="tool.end",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=result.tool,
                    endpoint=result.endpoint,
                    data=end_data,
                ))
                sequence += 1
                result_count += 1
                break

            if result is None:
                raise RuntimeError("fallback chain produced no terminal result")

        yield await emit(RunEvent.create(
            event="run.end",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data={
                "result_count": result_count,
                "fallback_count": fallback_count,
            },
        ))

    async def run(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return await self.ainvoke(request, config=config)

    async def arun(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return await self.ainvoke(request, config=config)


class ConfiguredSchemaRouter:
    """SchemaRouter with an immutable default RunConfig."""

    def __init__(self, router: SchemaRouter, config: RunConfig) -> None:
        self.router = router
        self.config = config

    def retrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        return self.router.retrieve(request, k=k)

    async def aretrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        return await self.router.aretrieve(request, k=k)

    def retrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        return self.router.retrieve_executable(request, k=k)

    async def aretrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        return await self.router.aretrieve_executable(request, k=k)

    def invoke(self, request: PlanRequest | str) -> list[ToolResult]:
        return self.router.invoke(request, config=self.config)

    async def ainvoke(self, request: PlanRequest | str) -> list[ToolResult]:
        return await self.router.ainvoke(request, config=self.config)

    def batch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return self.router.batch(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    async def abatch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return await self.router.abatch(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def batch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> Iterator[tuple[int, list[ToolResult] | Exception]]:
        return self.router.batch_as_completed(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def abatch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> AsyncIterator[tuple[int, list[ToolResult] | Exception]]:
        return self.router.abatch_as_completed(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def stream(self, request: PlanRequest | str) -> Iterator[ToolResult]:
        return self.router.stream(request, config=self.config)

    def astream(self, request: PlanRequest | str) -> AsyncIterator[ToolResult]:
        return self.router.astream(request, config=self.config)

    def astream_events(
        self,
        request: PlanRequest | str,
        *,
        trace_store: RunTraceStore | None = None,
    ) -> AsyncIterator[RunEvent]:
        return self.router.astream_events(
            request,
            config=self.config,
            trace_store=trace_store,
        )
