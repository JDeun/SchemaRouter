"""Deterministic synthetic MCP catalog for CrewAI filter comparisons.

No CrewAI dependency: this fixture is intentionally reusable by all baselines.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCase:
    name: str
    description: str
    input_schema: dict[str, object]
    authorized: bool = True
    available: bool = True

    def to_mcp(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


def make_catalog(size: int, *, seed: int = 0) -> list[ToolCase]:
    """Generate stable unique tools; exactly one relevant tool for each query family."""
    if size not in (32, 128, 512):
        raise ValueError("size must be 32, 128, or 512")
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    tools = [
        ToolCase(
            name="weather_lookup",
            description="Read current weather forecast by city",
            input_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        ),
        ToolCase(
            name="private_payroll",
            description="Read confidential payroll records",
            input_schema={"type": "object", "properties": {}},
            authorized=False,
        ),
        ToolCase(
            name="offline_inventory",
            description="Read inventory from unavailable warehouse",
            input_schema={"type": "object", "properties": {}},
            available=False,
        ),
    ]
    for index in range(size - len(tools)):
        key = (index * 7919 + seed) % 100003
        tools.append(
            ToolCase(
                name=f"catalog_{index:04d}",
                description=f"Lookup catalog record {key} by identifier",
                input_schema={
                    "type": "object",
                    "properties": {"record_id": {"type": "string"}},
                    "required": ["record_id"],
                },
            )
        )
    return tools


def public_catalog(size: int, *, seed: int = 0) -> list[dict[str, object]]:
    """Only expose permitted and available tools to retrieval baselines."""
    return [
        item.to_mcp()
        for item in make_catalog(size, seed=seed)
        if item.authorized and item.available
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, choices=(32, 128, 512), default=32)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(public_catalog(args.size, seed=args.seed), indent=2))
