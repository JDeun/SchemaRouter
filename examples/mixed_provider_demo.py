"""Deterministic multi-provider field-coverage and execution example."""

from __future__ import annotations

import asyncio

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperPlanRequest,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolSpec,
)


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
        source_type="materials-fixture",
        license="materials-fixture-license",
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
        source_type="literature-fixture",
        license="literature-fixture-license",
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
    principal = PrincipalContext(subject="example", roles=("reader",))
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="materials.lookup", roles_any=("reader",),
        ), AuthorizationRule(
            effect="allow", operation="papers.search", roles_any=("reader",),
        )),
    ))
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

    catalog = NativeConceptCatalog(concepts=(
        NativeDeclaredConcept(
            concept_id="material.band_gap", aliases=("band gap",),
            source_type="materials-fixture", license="materials-fixture-license",
            required_fields=(CapabilityFieldContract(
                semantic_id="band_gap", unit="eV", json_schema={"type": "number"},
            ),),
        ),
        NativeDeclaredConcept(
            concept_id="literature.abstract", aliases=("paper abstract",),
            source_type="literature-fixture", license="literature-fixture-license",
            required_fields=(CapabilityFieldContract(
                semantic_id="document_abstract", json_schema={"type": "string"},
            ),),
        ),
    ))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id="research.summary",
            required_concept_ids=("material.band_gap", "literature.abstract"),
            recall_group_ids=("materials", "literature"),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={
            "materials.lookup": {"materials": ("band_gap",)},
            "papers.search": {"literature": ("abstract",)},
        },
    )

    def owner_model(_payload):
        # Deterministic local Understand fixture, not a model quality measurement.
        return {
            "intent_id": "research.summary",
            "needs": [
                {"concept": "band gap", "unit": "eV", "source_type": None,
                 "qualifiers": {}},
                {"concept": "paper abstract", "unit": None, "source_type": None,
                 "qualifiers": {}},
            ],
            "needs_truncated": False,
            "excluded_concepts": [],
            "named_tools": [],
            "parameter_hints": {},
            "source_type": None,
        }

    router.configure_field_routing(
        session, model=owner_model, intent_registry=intents,
        rank_policy=PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        ),
        model_visible_intent_ids=("research.summary",),
    )
    request = PaperPlanRequest(query="band gap and paper abstract", max_calls=2)
    plan = await router.aplan_authorized(request, principal=principal)

    assert {call.tool for call in plan.calls} == {"materials", "papers"}
    assert plan.planning_status == "ready" and plan.executable
    assert plan.coverage is not None and plan.coverage.complete

    results = await router.execute(plan, config=RunConfig(principal=principal))
    by_tool = {result.tool: result.data for result in results}

    assert by_tool["materials"]["band_gap"] == 1.42
    assert "abstract" in by_tool["papers"]
    print(by_tool)


if __name__ == "__main__":
    asyncio.run(main())
