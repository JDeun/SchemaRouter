"""Provider-neutral capability contracts for experiment #338.

This module deliberately knows nothing about the canonical routing benchmark.  It compiles
ordinary ToolSpec / EndpointSpec metadata into a compact semantic contract that can be used
for both existing and newly registered tools.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")

# Generic operation ontology.  These are product-independent semantic primitives, not
# benchmark route names.  More specific primitives must appear before generic retrieval.
ACTION_FAMILIES: dict[str, tuple[str, ...]] = {
    "forecast": (
        "forecast",
        "predict",
        "prediction",
        "estimate future",
        "project future",
    ),
    "delete": (
        "delete",
        "remove",
        "erase",
        "purge",
        "destroy",
        "drop",
    ),
    "update": (
        "update",
        "edit",
        "change",
        "modify",
        "patch",
        "set",
        "replace",
    ),
    "create": (
        "create",
        "add",
        "register",
        "open",
        "schedule",
        "insert",
        "new",
    ),
    "send": (
        "send",
        "dispatch",
        "deliver",
        "publish",
        "post message",
    ),
    "cancel": (
        "cancel",
        "revoke",
        "unschedule",
        "abort",
    ),
    "export": (
        "export",
        "download",
        "dump",
        "extract",
        "save as",
    ),
    "translate": (
        "translate",
        "translation",
        "convert language",
    ),
    "summarize": (
        "summarize",
        "summary",
        "condense",
        "recap",
    ),
    "compare": (
        "compare",
        "difference",
        "diff",
        "contrast",
    ),
    "list": (
        "list",
        "enumerate",
        "show all",
        "browse",
    ),
    "search": (
        "search",
        "find",
        "lookup",
        "look up",
        "query",
        "discover",
    ),
    "retrieve": (
        "get",
        "retrieve",
        "read",
        "fetch",
        "show",
        "inspect",
        "view",
    ),
    "execute": (
        "execute",
        "run",
        "invoke",
        "trigger",
        "perform",
    ),
}

ACTION_PROTOTYPES: dict[str, str] = {
    "forecast": "predict or forecast a future state",
    "delete": "delete remove erase or destroy a resource",
    "update": "update edit modify or change an existing resource",
    "create": "create add register schedule or open a new resource",
    "send": "send dispatch deliver or publish a message or resource",
    "cancel": "cancel revoke abort or unschedule an operation",
    "export": "export download extract or save data",
    "translate": "translate content from one language to another",
    "summarize": "summarize condense or recap content",
    "compare": "compare contrast or compute differences",
    "list": "list enumerate or browse multiple resources",
    "search": "search find look up query or discover a resource",
    "retrieve": "get retrieve read fetch inspect or view a resource",
    "execute": "execute run invoke trigger or perform an operation",
}

TEMPORAL_FAMILIES: dict[str, tuple[str, ...]] = {
    "current": (
        "current",
        "latest",
        "now",
        "live",
        "present",
        "today",
        "real time",
        "real-time",
    ),
    "future": (
        "future",
        "forecast",
        "upcoming",
        "next",
        "later",
        "prediction",
        "predicted",
    ),
    "historical": (
        "historical",
        "history",
        "past",
        "previous",
        "earlier",
        "archive",
        "archived",
    ),
}

TEMPORAL_PROTOTYPES: dict[str, str] = {
    "current": "current latest live present state right now",
    "future": "future upcoming forecast predicted later state",
    "historical": "historical past previous archived earlier state",
}

_METHOD_ACTION = {
    "DELETE": "delete",
    "PATCH": "update",
    "PUT": "update",
    "GET": "retrieve",
    "HEAD": "retrieve",
    "OPTIONS": "retrieve",
}

_WRITE_ACTIONS = {"create", "update", "delete", "send", "cancel", "execute"}
_DESTRUCTIVE_ACTIONS = {"delete"}


@dataclass(frozen=True)
class DataFieldContract:
    name: str
    semantic_id: str | None
    role: str
    data_type: str
    required: bool
    identifier: bool
    source_unit: str | None
    canonical_unit: str | None
    dimension: str | None
    qualifiers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CapabilityContract:
    route_id: str
    tool_key: str
    endpoint_name: str
    adapter: str | None
    operation_text: str
    object_text: str
    data_contract_text: str
    contract_text: str
    input_fields: tuple[DataFieldContract, ...]
    output_fields: tuple[DataFieldContract, ...]
    declared_action: str | None
    temporal_scope: str | None
    read_only: bool | None
    destructive: bool | None
    method: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _split_identifier(value: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(value.replace("_", " ").replace("-", " ").split())


def _normalized_text(*parts: object) -> str:
    values: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, str):
            value = part.strip()
            if value:
                values.append(value)
            continue
        if isinstance(part, Iterable):
            for item in part:
                value = str(item).strip()
                if value:
                    values.append(value)
            continue
        value = str(part).strip()
        if value:
            values.append(value)
    return "\n".join(dict.fromkeys(values))


def _tokens(text: str) -> set[str]:
    normalized = _split_identifier(text).casefold()
    return {match.group(0) for match in _WORD_RE.finditer(normalized)}


def _phrase_present(text: str, phrase: str) -> bool:
    normalized = " ".join(_split_identifier(text).casefold().split())
    phrase_norm = " ".join(phrase.casefold().split())
    if " " in phrase_norm:
        return phrase_norm in normalized
    return phrase_norm in _tokens(normalized)


def infer_declared_action(endpoint: Any) -> str | None:
    """Infer one generic action primitive from registered endpoint metadata.

    Structural HTTP semantics are authoritative when they are unambiguous.  For POST and
    schema-only tools, descriptive metadata is consulted.  Unknown remains unknown rather
    than fabricating an execution capability.
    """

    method = str(endpoint.method).upper() if endpoint.method else None
    text = _normalized_text(
        _split_identifier(str(endpoint.name)),
        endpoint.operation_aliases,
        endpoint.description,
    )

    # Explicit destructive metadata must dominate descriptive ambiguity.
    if endpoint.destructive is True or method == "DELETE":
        return "delete"

    # Prefer specific semantic verbs over generic get/read words.
    for family, aliases in ACTION_FAMILIES.items():
        if family == "retrieve":
            continue
        if any(_phrase_present(text, alias) for alias in aliases):
            return family

    if method in _METHOD_ACTION:
        return _METHOD_ACTION[method]

    if method == "POST":
        # POST is intentionally not equated with create: RPC-style APIs use it for arbitrary
        # operations.  Without a descriptive verb this endpoint stays unknown.
        return None

    if any(_phrase_present(text, alias) for alias in ACTION_FAMILIES["retrieve"]):
        return "retrieve"

    if endpoint.read_only is True:
        return "retrieve"

    return None


def infer_temporal_scope(endpoint: Any) -> str | None:
    text = _normalized_text(
        _split_identifier(str(endpoint.name)),
        endpoint.operation_aliases,
        endpoint.description,
        endpoint.path,
    )
    matches = [
        family
        for family, aliases in TEMPORAL_FAMILIES.items()
        if any(_phrase_present(text, alias) for alias in aliases)
    ]
    return matches[0] if len(matches) == 1 else None


def _adapter(tool: Any) -> str | None:
    metadata = getattr(tool, "execution_metadata", None)
    if isinstance(metadata, dict):
        value = metadata.get("adapter")
        if isinstance(value, str) and value:
            return value
    metadata = getattr(tool, "metadata", None)
    if isinstance(metadata, dict):
        value = metadata.get("adapter")
        if isinstance(value, str) and value:
            return value
    return None


def _schema_type_label(schema: Any) -> str:
    if not isinstance(schema, dict) or not schema:
        return "unknown"
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        types = [str(value) for value in raw_type if isinstance(value, str)]
        non_null = [value for value in types if value != "null"]
        nullable = len(non_null) != len(types)
        if len(non_null) == 1:
            base = non_null[0]
        elif non_null:
            base = "|".join(sorted(dict.fromkeys(non_null)))
        else:
            base = "null"
        if nullable and base != "null":
            base += "|null"
    elif isinstance(raw_type, str):
        base = raw_type
    elif isinstance(schema.get("oneOf"), list):
        base = "oneOf"
    elif isinstance(schema.get("anyOf"), list):
        base = "anyOf"
    elif isinstance(schema.get("properties"), dict):
        base = "object"
    else:
        base = "unknown"

    if base == "array" and isinstance(schema.get("items"), dict):
        base = f"array<{_schema_type_label(schema['items'])}>"
    raw_format = schema.get("format")
    if isinstance(raw_format, str) and raw_format.strip():
        base += f"[{raw_format.strip()}]"
    return base


def _parameter_contract(parameter: Any) -> DataFieldContract:
    return DataFieldContract(
        name=str(parameter.name),
        semantic_id=None,
        role="input",
        data_type=_schema_type_label(parameter.json_schema),
        required=bool(parameter.required),
        identifier=False,
        source_unit=None,
        canonical_unit=None,
        dimension=None,
        qualifiers=(),
    )


def _output_contract(field: Any) -> DataFieldContract:
    normalization = getattr(field, "unit_normalization", None)
    canonical_unit = (
        str(normalization.canonical_unit)
        if normalization is not None
        else (str(field.unit) if getattr(field, "unit", None) else None)
    )
    dimension = (
        str(normalization.dimension)
        if normalization is not None
        else None
    )
    qualifiers = tuple(
        sorted((str(key), str(value)) for key, value in field.qualifiers.items())
    )
    return DataFieldContract(
        name=str(field.name),
        semantic_id=(
            str(field.semantic_id)
            if getattr(field, "semantic_id", None)
            else None
        ),
        role="output",
        data_type=_schema_type_label(field.json_schema),
        required=False,
        identifier=bool(field.identifier),
        source_unit=(str(field.unit) if getattr(field, "unit", None) else None),
        canonical_unit=canonical_unit,
        dimension=dimension,
        qualifiers=qualifiers,
    )


def _data_field_text(field: DataFieldContract) -> str:
    parts = [
        f"{field.role} {field.semantic_id or field.name}",
        f"type {field.data_type}",
    ]
    if field.required:
        parts.append("required")
    if field.identifier:
        parts.append("identifier")
    if field.source_unit is not None:
        parts.append(f"source unit {field.source_unit}")
    if field.canonical_unit is not None:
        parts.append(f"canonical unit {field.canonical_unit}")
    if field.dimension is not None:
        parts.append(f"dimension {field.dimension}")
    if field.qualifiers:
        parts.append(
            "qualifiers "
            + ", ".join(f"{key}={value}" for key, value in field.qualifiers)
        )
    return "; ".join(parts)


def _data_contract_text(
    input_fields: tuple[DataFieldContract, ...],
    output_fields: tuple[DataFieldContract, ...],
) -> str:
    rows = [_data_field_text(field) for field in (*input_fields, *output_fields)]
    return _normalized_text(rows)


def _field_text(endpoint: Any) -> str:
    parts: list[str] = []
    for parameter in endpoint.parameters:
        parts.extend(
            [
                _split_identifier(str(parameter.name)),
                str(parameter.description or ""),
            ]
        )
        aliases = getattr(parameter, "aliases", None)
        if aliases:
            parts.extend(str(value) for value in aliases)
    for field in endpoint.output_fields:
        parts.extend(
            [
                _split_identifier(str(field.semantic_id or field.name)),
                str(field.description or ""),
            ]
        )
        aliases = getattr(field, "aliases", None)
        if aliases:
            parts.extend(str(value) for value in aliases)
        if getattr(field, "unit", None):
            parts.append(str(field.unit))
        normalization = getattr(field, "unit_normalization", None)
        if normalization is not None:
            parts.extend(
                [
                    str(normalization.dimension),
                    str(normalization.canonical_unit),
                ]
            )
        if getattr(field, "json_schema", None):
            parts.append(_schema_type_label(field.json_schema))
        if getattr(field, "qualifiers", None):
            parts.extend(
                f"{key} {value}"
                for key, value in sorted(field.qualifiers.items())
            )
    return _normalized_text(parts)


def compile_endpoint(tool: Any, endpoint: Any) -> CapabilityContract:
    route_id = f"{tool.key}.{endpoint.name}"
    operation_name = _split_identifier(str(endpoint.name))
    method = str(endpoint.method).upper() if endpoint.method else None
    declared_action = infer_declared_action(endpoint)
    temporal_scope = infer_temporal_scope(endpoint)

    structural: list[str] = []
    if method:
        structural.append(f"HTTP method {method}")
    if endpoint.read_only is True:
        structural.append("read only")
    elif endpoint.read_only is False:
        structural.append("write capable")
    if endpoint.destructive is True:
        structural.append("destructive")
    elif endpoint.destructive is False:
        structural.append("non destructive")
    if declared_action is not None:
        structural.append(f"operation primitive {declared_action}")
    if temporal_scope is not None:
        structural.append(f"temporal scope {temporal_scope}")

    operation_text = _normalized_text(
        operation_name,
        endpoint.operation_aliases,
        endpoint.description,
        structural,
    )

    input_fields = tuple(_parameter_contract(item) for item in endpoint.parameters)
    output_fields = tuple(_output_contract(item) for item in endpoint.output_fields)
    data_contract_text = _data_contract_text(input_fields, output_fields)

    path_text = _split_identifier(str(endpoint.path or "").strip("/").replace("/", " "))
    object_text = _normalized_text(
        _split_identifier(str(tool.name)),
        tool.description,
        path_text,
        _field_text(endpoint),
        data_contract_text,
    )

    contract_text = _normalized_text(
        "Registered tool capability.",
        f"Operation: {operation_text}",
        f"Resource and schema: {object_text}",
        f"Data contract: {data_contract_text}",
    )

    return CapabilityContract(
        route_id=route_id,
        tool_key=str(tool.key),
        endpoint_name=str(endpoint.name),
        adapter=_adapter(tool),
        operation_text=operation_text,
        object_text=object_text,
        data_contract_text=data_contract_text,
        contract_text=contract_text,
        input_fields=input_fields,
        output_fields=output_fields,
        declared_action=declared_action,
        temporal_scope=temporal_scope,
        read_only=endpoint.read_only,
        destructive=endpoint.destructive,
        method=method,
    )


def compile_registry(registry: Any) -> tuple[CapabilityContract, ...]:
    contracts = [
        compile_endpoint(tool, endpoint)
        for tool in registry.tools()
        for endpoint in tool.endpoints
    ]
    route_ids = [contract.route_id for contract in contracts]
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("registry produced duplicate route IDs")
    return tuple(sorted(contracts, key=lambda item: item.route_id))


def counterfactual_action_texts(
    contract: CapabilityContract,
) -> dict[str, str]:
    """Return generic same-resource operation counterfactuals for one route."""

    result: dict[str, str] = {}
    for family, prototype in ACTION_PROTOTYPES.items():
        if family == contract.declared_action:
            continue
        result[family] = _normalized_text(
            f"Operation: {prototype}",
            f"Resource and schema: {contract.object_text}",
        )
    return result


def structural_action_compatible(
    contract: CapabilityContract,
    query_action: str | None,
) -> bool | None:
    """Return deterministic structural compatibility when metadata is conclusive."""

    if query_action is None:
        return None
    if contract.destructive is True:
        return query_action in _DESTRUCTIVE_ACTIONS
    if contract.read_only is True and query_action in _WRITE_ACTIONS:
        return False
    if contract.declared_action is not None:
        return query_action == contract.declared_action
    return None
