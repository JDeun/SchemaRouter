from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6f_catalog import development_registry  # noqa: E402
from benchmarks.tool_specialized_retriever import (  # noqa: E402
    ToolSpecializedRouteRetriever,
    build_endpoint_profiles,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_v6f_profiles_are_deterministic_and_schema_grounded() -> None:
    registry = development_registry()
    first = build_endpoint_profiles(registry)
    second = build_endpoint_profiles(registry)

    assert first == second
    assert len(first) == 19
    assert len({profile.route_id for profile in first}) == 19
    assert all("limitations:" not in profile.text for profile in first)
    assert all("function_description:" in profile.text for profile in first)
    assert all("when_to_use:" in profile.text for profile in first)
    assert all("tags:" in profile.text for profile in first)

    modulus = next(
        profile for profile in first
        if profile.route_id == "youngs_modulus.current"
    )
    assert "material.youngs_modulus" in modulus.text
    assert "unit=GPa" in modulus.text
    assert "canonical_unit=Pa" in modulus.text
    assert "dimension=elastic_modulus" in modulus.text
    assert "qualifiers=statistic=instantaneous" in modulus.text


def test_v6f_retriever_is_global_top1_without_abstention() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo operations",
            endpoints=[
                EndpointSpec(
                    name="alpha",
                    description="Retrieve an alpha record",
                    operation_aliases=["retrieve"],
                    read_only=True,
                ),
                EndpointSpec(
                    name="beta",
                    description="Delete a beta record",
                    operation_aliases=["delete"],
                    read_only=False,
                    destructive=True,
                ),
            ],
        )
    )

    def embed(texts: list[str], is_query: bool) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            if is_query:
                vectors.append([0.0, 1.0])
            elif "endpoint: alpha" in text:
                vectors.append([1.0, 0.0])
            elif "endpoint: beta" in text:
                vectors.append([0.0, 1.0])
            else:
                raise AssertionError(text)
        return vectors

    retriever = ToolSpecializedRouteRetriever(registry, embed)
    result = retriever.route("please delete beta")

    assert retriever.route_ids == ("demo.alpha", "demo.beta")
    assert result["predicted"] == "demo.beta"
    assert result["top_score"] == 1.0
    assert result["top2_margin"] == 1.0
    assert [row["route_id"] for row in result["ranking"]] == [
        "demo.beta",
        "demo.alpha",
    ]
