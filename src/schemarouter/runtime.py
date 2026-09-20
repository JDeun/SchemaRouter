from __future__ import annotations

import httpx

from .executor import RegistryExecutor
from .ingestion import SourceKind, URLSchemaLoader
from .models import ExecutionPlan, PlanRequest, ToolResult, ToolSpec
from .planner import QueryAnalyzer, SchemaPlanner
from .registry import InMemoryRegistry


class SchemaRouter:
    """High-level facade for registering schemas, planning calls, and executing plans."""

    def __init__(
        self,
        *,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.registry = InMemoryRegistry()
        self.planner = SchemaPlanner(self.registry, analyzer=analyzer)
        self.executor = RegistryExecutor(self.registry)
        self.loader = URLSchemaLoader(
            self.registry,
            self.executor,
            http_client=http_client,
        )

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
        trusted_headers: dict[str, str] | None = None,
    ) -> SchemaRouter:
        router = cls(analyzer=analyzer, http_client=http_client)
        await router.add_url(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            trusted_headers=trusted_headers,
        )
        return router

    def add_tool(self, tool: ToolSpec, *, replace: bool = False) -> str:
        return self.registry.register(tool, replace=replace)

    async def add_url(
        self,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        replace: bool = False,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> ToolSpec:
        return await self.loader.load(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            replace=replace,
            trusted_headers=trusted_headers,
            timeout=timeout,
        )

    def plan(self, request: PlanRequest | str) -> ExecutionPlan:
        return self.planner.plan(request)

    async def execute(self, plan: ExecutionPlan) -> list[ToolResult]:
        return await self.executor.execute(plan)

    async def run(self, request: PlanRequest | str) -> list[ToolResult]:
        plan = self.plan(request)
        return await self.execute(plan)
