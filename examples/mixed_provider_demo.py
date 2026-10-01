"""Deterministic multi-provider field-coverage and execution example."""

from __future__ import annotations

import asyncio

from schemarouter import EndpointSpec, FieldSpec, PlanRequest, SchemaRouter, ToolSpec


class StaticInvoker:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def __call__(
        self,
        endpoint: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        del endpoint, arguments
        return dict(self.payload)


def materials_tool() -> ToolSpec:
    return ToolSpec(
        name="materials",
        provider="example-materials",
        access_mode="sdk",
        endpoints=[
            EndpointSpec(
                name="lookup",
                read_only=True,
                output_schema={
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string"},
                        "band_gap": {"type": "number"},
                    },
                    "required": ["material_id", "band_gap"],
                },
                output_fields=[
                    FieldSpec(
                        name="material_id",
                        identifier=True,
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="band_gap",
                        semantic_id="band_gap",
                        aliases=["band gap"],
                        json_schema={"type": "number"},
                        unit="eV",
                    ),
                ],
            )
        ],
    )


def papers_tool() -> ToolSpec:
    return ToolSpec(
        name="papers",
        provider="example-literature",
        access_mode="sdk",
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                output_schema={
                    "type": "object",
                    "properties": {
                        "paper_id": {"type": "string"},
                        "abstract": {"type": "string"},
                    },
                    "required": ["paper_id", "abstract"],
                },
                output_fields=[
                    FieldSpec(
                        name="paper_id",
                        identifier=True,
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="abstract",
                        semantic_id="document_abstract",
                        aliases=["paper abstract", "abstract"],
                        json_schema={"type": "string"},
                    ),
                ],
            )
        ],
    )


async def main() -> None:
    router = SchemaRouter()
    material = materials_tool()
    paper = papers_tool()
    router.add_bound_tool(
        material,
        StaticInvoker({"material_id": "mat-1", "band_gap": 1.42}),
    )
    router.add_bound_tool(
        paper,
        StaticInvoker(
            {
                "paper_id": "paper-1",
                "abstract": "A compact example abstract about the material.",
            }
        ),
    )

    request = PlanRequest(
        query="band gap and paper abstract",
        max_calls=2,
    )
    plan = router.plan_executable(request)

    assert {call.tool for call in plan.calls} == {"materials", "papers"}
    assert plan.coverage is not None and plan.coverage.complete

    results = await router.execute(plan)
    by_tool = {result.tool: result.data for result in results}

    assert by_tool["materials"]["band_gap"] == 1.42
    assert "abstract" in by_tool["papers"]
    print(by_tool)


if __name__ == "__main__":
    asyncio.run(main())
