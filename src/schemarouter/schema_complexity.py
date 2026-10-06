from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SchemaSourceError


@dataclass(frozen=True)
class SchemaComplexityLimits:
    """Hard safety budgets for untrusted schema documents."""

    max_depth: int = 64
    max_nodes: int = 50_000
    max_combinator_branches: int = 4_096
    max_references: int = 8_192
    max_ref_hops: int = 128


DEFAULT_SCHEMA_COMPLEXITY_LIMITS = SchemaComplexityLimits()


def _complexity_error(source: str, detail: str) -> SchemaSourceError:
    return SchemaSourceError(f"{source} exceeds schema structural complexity limit: {detail}")


def validate_schema_complexity(
    value: Any,
    *,
    source: str = "schema",
    limits: SchemaComplexityLimits = DEFAULT_SCHEMA_COMPLEXITY_LIMITS,
) -> None:
    """Validate an untrusted JSON-like schema without recursive traversal.

    The traversal counts the concrete document structure before recursive normalizers,
    ref walkers, or field discovery code can process it. Cyclic Python/YAML container
    graphs are rejected deterministically.
    """

    stack: list[tuple[bool, Any, int]] = [(False, value, 0)]
    active_containers: set[int] = set()
    node_count = 0
    combinator_branches = 0
    references = 0

    while stack:
        leaving, node, depth = stack.pop()
        if leaving:
            active_containers.discard(id(node))
            continue

        node_count += 1
        if node_count > limits.max_nodes:
            raise _complexity_error(source, f"node count exceeds {limits.max_nodes}")
        if depth > limits.max_depth:
            raise _complexity_error(source, f"depth exceeds {limits.max_depth}")

        if isinstance(node, dict):
            object_id = id(node)
            if object_id in active_containers:
                raise _complexity_error(source, "cyclic container graph")
            active_containers.add(object_id)
            stack.append((True, node, depth))

            if node_count + len(node) > limits.max_nodes:
                raise _complexity_error(source, f"node count exceeds {limits.max_nodes}")

            if isinstance(node.get("$ref"), str):
                references += 1
                if references > limits.max_references:
                    raise _complexity_error(
                        source,
                        f"reference count exceeds {limits.max_references}",
                    )

            for keyword in ("allOf", "anyOf", "oneOf"):
                branches = node.get(keyword)
                if isinstance(branches, list):
                    combinator_branches += len(branches)
                    if combinator_branches > limits.max_combinator_branches:
                        raise _complexity_error(
                            source,
                            "combined allOf/anyOf/oneOf branch count exceeds "
                            f"{limits.max_combinator_branches}",
                        )

            next_depth = depth + 1
            for child in reversed(tuple(node.values())):
                stack.append((False, child, next_depth))
            continue

        if isinstance(node, list):
            object_id = id(node)
            if object_id in active_containers:
                raise _complexity_error(source, "cyclic container graph")
            active_containers.add(object_id)
            stack.append((True, node, depth))

            if node_count + len(node) > limits.max_nodes:
                raise _complexity_error(source, f"node count exceeds {limits.max_nodes}")

            next_depth = depth + 1
            for child in reversed(node):
                stack.append((False, child, next_depth))


def ensure_ref_hop_budget(
    hops: int,
    *,
    source: str = "schema",
    limits: SchemaComplexityLimits = DEFAULT_SCHEMA_COMPLEXITY_LIMITS,
) -> None:
    """Fail closed when local-reference expansion exceeds its independent budget."""

    if hops > limits.max_ref_hops:
        raise _complexity_error(
            source,
            f"local reference chain exceeds {limits.max_ref_hops} hops",
        )
