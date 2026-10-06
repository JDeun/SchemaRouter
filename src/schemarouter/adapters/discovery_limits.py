from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from ..errors import RegistrationError

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class NativeDiscoveryLimits:
    """Resource budgets for trusted native schema/catalog discovery."""

    max_sources: int = 256
    max_fields_per_source: int = 512
    max_node_types_per_source: int = 512
    max_relationship_types_per_source: int = 512
    max_properties_per_type: int = 256
    max_total_items: int = 16_384
    max_descriptor_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in (
            ("max_sources", self.max_sources),
            ("max_fields_per_source", self.max_fields_per_source),
            ("max_node_types_per_source", self.max_node_types_per_source),
            ("max_relationship_types_per_source", self.max_relationship_types_per_source),
            ("max_properties_per_type", self.max_properties_per_type),
            ("max_total_items", self.max_total_items),
            ("max_descriptor_bytes", self.max_descriptor_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


def bounded_collect(
    values: Iterable[_T],
    *,
    limit: int,
    label: str,
) -> tuple[_T, ...]:
    """Collect at most limit values, consuming only one item past the budget."""

    collected: list[_T] = []
    for index, value in enumerate(values):
        if index >= limit:
            raise RegistrationError(
                f"{label} exceeds native discovery limit of {limit}"
            )
        collected.append(value)
    return tuple(collected)


def bounded_select(
    values: Iterable[_T],
    requested: set[str],
    *,
    limit: int,
    label: str,
    name_of: Callable[[_T], str],
) -> tuple[_T, ...]:
    """Select requested descriptors without consuming unrelated tail entries."""

    if not requested:
        return ()
    selected: list[_T] = []
    found: set[str] = set()
    for index, value in enumerate(values):
        if index >= limit:
            raise RegistrationError(
                f"{label} exceeds native discovery limit of {limit}"
            )
        name = name_of(value)
        if name in requested:
            selected.append(value)
            found.add(name)
            if found == requested:
                break
    return tuple(selected)


def descriptor_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("name") or "")
    return str(getattr(value, "name", "") or "")


def require_at_most(
    count: int,
    *,
    limit: int,
    label: str,
) -> None:
    if count > limit:
        raise RegistrationError(
            f"{label} exceeds native discovery limit of {limit}"
        )


class NativeDiscoveryBudget:
    """Track cumulative descriptor work across one failure-atomic discovery pass."""

    def __init__(self, limits: NativeDiscoveryLimits | None = None) -> None:
        self.limits = limits or NativeDiscoveryLimits()
        self._sources = 0
        self._items = 0
        self._descriptor_bytes = 0

    def consume_source(
        self,
        descriptor: Any,
        *,
        nested_items: int,
    ) -> None:
        self._sources += 1
        require_at_most(
            self._sources,
            limit=self.limits.max_sources,
            label="native discovery source count",
        )

        self._items += 1 + nested_items
        require_at_most(
            self._items,
            limit=self.limits.max_total_items,
            label="native discovery descriptor item count",
        )

        dump = getattr(descriptor, "model_dump_json", None)
        if callable(dump):
            encoded_size = len(dump().encode("utf-8"))
        else:
            encoded_size = len(repr(descriptor).encode("utf-8"))
        self._descriptor_bytes += encoded_size
        require_at_most(
            self._descriptor_bytes,
            limit=self.limits.max_descriptor_bytes,
            label="native discovery descriptor bytes",
        )
