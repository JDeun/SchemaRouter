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
from .errors import InvocationUnavailableError, ProposalApprovalError, RegistrationError
from .executor import ExecutionBudgetTracker, RegistryExecutor
from .hooks import ExecutionHooks
from .ingestion import SourceKind, URLSchemaLoader
from .inspection import RouterInspection, inspect_router
from .models import ExecutionPlan, PlanRequest, ToolResult, ToolSpec
from .planner import QueryAnalyzer, SchemaPlanner
from .policy import ApprovalCallback, ExecutionPolicy
from .proposals import DocumentationModelCallable, SchemaProposal, inspect_documentation_url
from .registry import InMemoryRegistry, ToolRegistry
from .runs import RunConfig, RunEvent
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
        unavailable_cooldown_seconds: float = 30.0,
    ) -> None:
        self.registry = registry if registry is not None else InMemoryRegistry()
        self.planner = SchemaPlanner(self.registry, analyzer=analyzer)
        self.executor = RegistryExecutor(
            self.registry,
            policy=policy,
            approval_callback=approval_callback,
            hooks=execution_hooks,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
        )
        self.loader = URLSchemaLoader(
            self.registry,
            self.executor,
            http_client=http_client,
            adapters=adapter_registry,
        )

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
        key = self.registry.register(tool, replace=replace)
        self.executor.bind(key, invoker)
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
        self.registry.register(updated, replace=True)
        self.executor.bind(tool_key, invoker)

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
        key = self.registry.register(tool, replace=replace)
        self.executor.bind(key, invoker)
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

    def plan(self, request: PlanRequest | str) -> ExecutionPlan:
        return self.planner.plan(request)

    async def aplan(self, request: PlanRequest | str) -> ExecutionPlan:
        return await self.planner.aplan(request)

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
        plan = await self.aplan(request)
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
        plan = await self.aplan(request)
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
            plan = await self.aplan(request)
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
                        await event_queue.put(
                            ("start", index, call, candidate_index)
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
                                    (exc, next_call, candidate_index),
                                )
                            )
                            if has_next:
                                continue
                            return
                        except Exception as exc:
                            await event_queue.put(("error", index, call, exc))
                            return
                        await event_queue.put(
                            ("end", index, call, (result, candidate_index))
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
                                "reason": "cooldown",
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
                        "reason": "cooldown",
                        "skipped_unavailable": skipped,
                    },
                ))
                sequence += 1
                fallback_count += 1

            for candidate_index, call in enumerate(chain):
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
