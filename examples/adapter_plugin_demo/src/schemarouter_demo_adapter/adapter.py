from __future__ import annotations

from typing import Any

from schemarouter import (
    AdapterContext,
    AdapterLoadResult,
    DiscoveryProfile,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    RefreshProfile,
    ToolSpec,
)


class DemoStaticAdapter:
    """Network-independent example of a third-party SourceAdapter plugin."""

    kind = "demo_static"
    priority = 10
    discovery = DiscoveryProfile(activity="passive")
    refresh = RefreshProfile()

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        if context.url != "https://example.invalid/demo-static":
            return None

        tool = ToolSpec(
            name=context.name or "demo_catalog",
            namespace=context.namespace,
            description="Deterministic capability supplied by an installed SourceAdapter plugin.",
            provider=context.provider or "schemarouter-demo",
            access_mode=context.access_mode or self.kind,
            remote=False,
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    description="Return a deterministic integer derived from item_id.",
                    read_only=True,
                    destructive=False,
                    parameters=[
                        ParameterSpec(
                            name="item_id",
                            required=True,
                            json_schema={"type": "string", "minLength": 1},
                        )
                    ],
                    input_schema={
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "minLength": 1},
                        },
                        "required": ["item_id"],
                        "additionalProperties": False,
                    },
                    output_fields=[
                        FieldSpec(
                            name="value",
                            semantic_id="demo.value",
                            description="Length of the supplied item identifier.",
                            json_schema={"type": "integer"},
                        )
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {"value": {"type": "integer"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                )
            ],
        )

        def invoke(endpoint_name: str, arguments: dict[str, Any]) -> dict[str, int]:
            if endpoint_name != "lookup":
                raise KeyError(endpoint_name)
            item_id = arguments["item_id"]
            if not isinstance(item_id, str):
                raise TypeError("item_id must be a string")
            return {"value": len(item_id)}

        return AdapterLoadResult(tool=tool, invoker=invoke)
