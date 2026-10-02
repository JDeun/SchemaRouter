from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

_REMOTE_ADAPTERS = {"mcp", "openapi", "optimade", "html_proposal"}
_OPENAPI_ENDPOINT_RUNTIME_KEYS = {
    "request_body_discriminator",
    "request_body_mode",
    "request_body_required",
}
_OPTIMADE_ENDPOINT_RUNTIME_KEYS = {"entry_type", "field_projection", "mode"}
_PYTHON_ENDPOINT_RUNTIME_KEYS = {"callable_module", "callable_name"}
_TOOL_RUNTIME_KEYS_BY_ADAPTER = {
    "openapi": {
        "adapter",
        "approved_base_url",
        "execution_bound",
        "requires_explicit_base_url",
    },
    "mcp": {
        "adapter",
        "authenticated_transport",
        "protocol_version",
        "source_url",
    },
    "optimade": {
        "adapter",
        "api_version",
        "versioned_base_url",
    },
    "html_proposal": {
        "adapter",
        "approved_base_url",
        "executable",
    },
    "python": {"adapter"},
}


def _schema_types(schema: dict[str, Any]) -> set[str]:
    declared = schema.get("type")
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, list):
        return {
            value
            for value in declared
            if isinstance(value, str)
        }
    return set()


def _schema_supports_unit(
    schema: dict[str, Any],
    *,
    require_declared_type: bool = False,
) -> bool:
    types = _schema_types(schema)
    types.discard("null")
    if not types:
        return not require_declared_type
    if types <= {"number", "integer"}:
        return True
    if types == {"array"}:
        items = schema.get("items")
        return isinstance(items, dict) and _schema_supports_unit(
            items,
            require_declared_type=require_declared_type,
        )
    return False


def _schema_type_shape_compatible(
    required: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    """Return whether candidate values fit the declared required type shape."""

    required_types = _schema_types(required)
    candidate_types = _schema_types(candidate)
    if not required_types or not candidate_types:
        return True

    for candidate_type in candidate_types:
        if candidate_type in required_types:
            continue
        if candidate_type == "integer" and "number" in required_types:
            continue
        return False

    if "array" in candidate_types and "array" in required_types:
        required_items = required.get("items")
        candidate_items = candidate.get("items")
        if isinstance(required_items, dict):
            if not isinstance(candidate_items, dict):
                return False
            if not _schema_type_shape_compatible(required_items, candidate_items):
                return False

    return True


def _resolve_local_schema_ref(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Resolve only local JSON Schema refs against the endpoint's own schema document."""

    current = schema
    seen: set[str] = set()
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return current
        seen.add(ref)

        node: Any = document
        try:
            for raw in ref[2:].split("/"):
                part = raw.replace("~1", "/").replace("~0", "~")
                node = node[part]
        except (KeyError, TypeError):
            return current
        if not isinstance(node, dict):
            return current

        merged = dict(node)
        merged.update({key: value for key, value in current.items() if key != "$ref"})
        current = merged
    return schema


def _schema_at_projection_path(
    output_schema: dict[str, Any],
    path: tuple[str, ...],
) -> dict[str, Any]:
    document = output_schema
    schema = _resolve_local_schema_ref(document, output_schema)
    if "array" in _schema_types(schema) and isinstance(schema.get("items"), dict):
        # Root collection endpoints historically address fields relative to each record.
        schema = _resolve_local_schema_ref(document, schema["items"])

    for part in path:
        schema = _resolve_local_schema_ref(document, schema)
        if part == "*":
            if "array" not in _schema_types(schema):
                return {}
            items = schema.get("items")
            if not isinstance(items, dict):
                return {}
            schema = _resolve_local_schema_ref(document, items)
            continue

        if "object" not in _schema_types(schema):
            return {}
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return {}
        child = properties.get(part)
        if not isinstance(child, dict):
            return {}
        schema = _resolve_local_schema_ref(document, child)
    return schema


def _validate_execution_metadata(value: dict[str, Any]) -> None:
    try:
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except ValueError as exc:
        raise ValueError(
            "execution_metadata must contain only finite JSON numbers"
        ) from exc
    except TypeError as exc:
        raise ValueError(
            "execution_metadata must contain only JSON-safe values"
        ) from exc


def _legacy_endpoint_execution_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys: set[str] = set()
    if any(key in metadata for key in _OPENAPI_ENDPOINT_RUNTIME_KEYS):
        keys.update(_OPENAPI_ENDPOINT_RUNTIME_KEYS)
    if "entry_type" in metadata or "field_projection" in metadata:
        keys.update(_OPTIMADE_ENDPOINT_RUNTIME_KEYS)
    if "callable_module" in metadata or "callable_name" in metadata:
        keys.update(_PYTHON_ENDPOINT_RUNTIME_KEYS)
    return {key: metadata[key] for key in keys if key in metadata}


def _legacy_tool_execution_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    adapter = metadata.get("adapter")
    if not isinstance(adapter, str):
        return {}
    keys = _TOOL_RUNTIME_KEYS_BY_ADAPTER.get(adapter)
    if keys is None:
        return {}
    return {key: metadata[key] for key in keys if key in metadata}



class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ParameterSpec(StrictModel):
    name: str
    wire_name: str | None = None
    description: str = ""
    required: bool = False
    location: Literal["path", "query", "header", "body", "body_root", "argument"] = "argument"
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class ServerProjectionSpec(StrictModel):
    """Trusted contract for server-side response-field selection."""

    parameter: str
    separator: str = ","
    field_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_projection(self) -> ServerProjectionSpec:
        if not self.parameter.strip():
            raise ValueError("server projection parameter must be non-empty")
        if not self.separator:
            raise ValueError("server projection separator must be non-empty")
        if any(not key or not value for key, value in self.field_map.items()):
            raise ValueError("server projection field_map requires non-empty keys and values")
        return self

    def selector_for(self, field: FieldSpec) -> str:
        return self.field_map.get(field.name, field.name)


class UnitNormalizationSpec(StrictModel):
    """Explicit affine conversion from a provider unit to one canonical unit.

    The runtime never infers conversion factors from unit strings. Adapters/applications must
    declare the conversion contract locally.

    canonical_value = source_value * scale + offset
    """

    dimension: str
    canonical_unit: str
    scale: float = 1.0
    offset: float = 0.0

    @model_validator(mode="after")
    def validate_unit_normalization(self) -> UnitNormalizationSpec:
        if not self.dimension.strip():
            raise ValueError("unit normalization dimension must be non-empty")
        if self.dimension != self.dimension.strip():
            raise ValueError("unit normalization dimension must not have surrounding whitespace")
        if not self.canonical_unit.strip():
            raise ValueError("unit normalization canonical_unit must be non-empty")
        if self.canonical_unit != self.canonical_unit.strip():
            raise ValueError(
                "unit normalization canonical_unit must not have surrounding whitespace"
            )
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("unit normalization scale must be finite and positive")
        if not math.isfinite(self.offset):
            raise ValueError("unit normalization offset must be finite")
        return self


class ResultFieldContract(StrictModel):
    """Minimal field contract carried with a projected ToolResult."""

    semantic_id: str | None = None
    json_schema: dict[str, Any] = Field(default_factory=dict)
    source_unit: str | None = None
    unit: str | None = None
    dimension: str | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)


class FieldSpec(StrictModel):
    name: str
    semantic_id: str | None = None
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    result_path: list[str] = Field(default_factory=list)
    unit: str | None = None
    unit_normalization: UnitNormalizationSpec | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)
    identifier: bool = False
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_path(self) -> FieldSpec:
        if self.semantic_id is not None and not self.semantic_id.strip():
            raise ValueError("field semantic_id must be non-empty when provided")
        if any(not isinstance(part, str) or not part for part in self.path):
            raise ValueError("field path requires non-empty string segments")
        if any(not isinstance(part, str) or not part for part in self.result_path):
            raise ValueError("field result_path requires non-empty string segments")
        source_wildcards = [
            index
            for index, part in enumerate(self.path)
            if part == "*"
        ]
        result_wildcards = [
            index
            for index, part in enumerate(self.result_path)
            if part == "*"
        ]
        if source_wildcards:
            if source_wildcards[0] == 0:
                raise ValueError("array wildcard must not begin a field path")
            if source_wildcards[-1] == len(self.path) - 1:
                raise ValueError("array wildcard must not end a field path")
            if not self.result_path:
                raise ValueError(
                    "array-item field paths require an explicit result_path"
                )
            if result_wildcards and result_wildcards[0] == 0:
                raise ValueError("array wildcard must not begin a result path")
            if result_wildcards and result_wildcards[-1] == len(self.result_path) - 1:
                raise ValueError("array wildcard must not end a result path")
            if source_wildcards != result_wildcards:
                raise ValueError(
                    "array-item source/result paths must preserve wildcard positions"
                )
        if self.unit is not None:
            if not self.unit.strip():
                raise ValueError("field unit must be non-empty when provided")
            if self.unit != self.unit.strip():
                raise ValueError("field unit must not have surrounding whitespace")
        for key, value in self.qualifiers.items():
            if not key or key != key.strip():
                raise ValueError(
                    "field qualifier keys must be non-empty and have no surrounding whitespace"
                )
            if not value or value != value.strip():
                raise ValueError(
                    "field qualifier values must be non-empty and have no surrounding whitespace"
                )
        if self.unit_normalization is not None and self.unit is None:
            raise ValueError(
                "unit_normalization requires the provider source unit in field.unit"
            )
        if (
            self.unit_normalization is not None
            and self.unit == self.unit_normalization.canonical_unit
            and (
                self.unit_normalization.scale != 1.0
                or self.unit_normalization.offset != 0.0
            )
        ):
            raise ValueError(
                "unit normalization must be identity when source and canonical units are equal"
            )
        if self.unit is not None and self.json_schema:
            if not _schema_supports_unit(
                self.json_schema,
                require_declared_type=True,
            ):
                raise ValueError(
                    "a field with unit metadata must declare a numeric scalar or numeric-array "
                    "json_schema type"
                )
        return self

    @property
    def projection_path(self) -> tuple[str, ...]:
        return tuple(self.path or [self.name])

    @property
    def result_projection_path(self) -> tuple[str, ...]:
        return tuple(self.result_path or self.projection_path)


AuthKind = Literal["api_key", "http", "oauth2", "openid_connect", "unsupported"]
AuthLocation = Literal["header", "query", "cookie"]


class AuthSchemeRequirement(StrictModel):
    """Secret-free identity of one credential requirement."""

    name: str
    kind: AuthKind
    location: AuthLocation | None = None
    parameter_name: str | None = None
    http_scheme: str | None = None
    scopes: list[str] = Field(default_factory=list)
    declared_type: str | None = None

    @model_validator(mode="after")
    def validate_auth_scheme(self) -> AuthSchemeRequirement:
        if not self.name or self.name != self.name.strip():
            raise ValueError("auth scheme name must be non-empty and trimmed")
        if self.declared_type is not None and (
            not self.declared_type or self.declared_type != self.declared_type.strip()
        ):
            raise ValueError("declared auth scheme type must be non-empty and trimmed")
        if len(self.scopes) != len(set(self.scopes)):
            raise ValueError("auth requirement scopes must be unique")
        if any(not scope or scope != scope.strip() for scope in self.scopes):
            raise ValueError("auth requirement scopes must be non-empty and trimmed")

        if self.kind == "api_key":
            if self.location is None or not self.parameter_name:
                raise ValueError(
                    "api_key auth requires a declared header/query/cookie name"
                )
        elif self.kind == "http":
            if not self.http_scheme:
                raise ValueError("http auth requires a declared HTTP auth scheme")
        return self


class AuthRequirementSet(StrictModel):
    """One OpenAPI security alternative; schemes inside the set are conjunctive."""

    schemes: list[AuthSchemeRequirement] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_auth_schemes(self) -> AuthRequirementSet:
        names = [scheme.name for scheme in self.schemes]
        if len(names) != len(set(names)):
            raise ValueError("auth requirement set contains duplicate scheme names")
        return self


class EndpointSpec(StrictModel):
    name: str
    description: str = ""
    operation_aliases: list[str] = Field(default_factory=list)
    parameters: list[ParameterSpec] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_fields: list[FieldSpec] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    method: str | None = None
    path: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    server_projection: ServerProjectionSpec | None = None
    auth_requirements: list[AuthRequirementSet] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_execution_metadata(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "execution_metadata" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        execution_metadata = _legacy_endpoint_execution_metadata(metadata)
        if not execution_metadata:
            return value
        migrated = dict(value)
        migrated["execution_metadata"] = execution_metadata
        return migrated

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_auth_requirements(cls, value: Any) -> Any:
        """Fail closed for legacy endpoint documents that only stored raw security metadata."""

        if not isinstance(value, dict) or "auth_requirements" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        security = metadata.get("security")
        if not isinstance(security, list) or not security:
            return value

        alternatives: list[dict[str, Any]] = []
        for alternative in security:
            if not isinstance(alternative, dict):
                alternatives.append(
                    {
                        "schemes": [
                            {
                                "name": "__legacy_invalid_security__",
                                "kind": "unsupported",
                                "declared_type": "legacy_invalid",
                            }
                        ]
                    }
                )
                continue
            schemes: list[dict[str, Any]] = []
            for name, raw_scopes in sorted(alternative.items()):
                if not isinstance(name, str) or not name.strip():
                    continue
                scopes = (
                    sorted({scope for scope in raw_scopes if isinstance(scope, str)})
                    if isinstance(raw_scopes, list)
                    else []
                )
                schemes.append(
                    {
                        "name": name,
                        "kind": "unsupported",
                        "scopes": scopes,
                        "declared_type": "legacy_unknown",
                    }
                )
            alternatives.append({"schemes": schemes})

        migrated = dict(value)
        migrated["auth_requirements"] = alternatives
        return migrated

    @model_validator(mode="after")
    def validate_unique_names(self) -> EndpointSpec:
        _validate_execution_metadata(self.execution_metadata)
        normalized_operation_aliases: set[str] = set()
        for alias in self.operation_aliases:
            if not alias or alias != alias.strip():
                raise ValueError(
                    "endpoint operation_aliases must be non-empty and have no "
                    "surrounding whitespace"
                )
            normalized = " ".join(alias.casefold().split())
            if normalized in normalized_operation_aliases:
                raise ValueError(
                    f"duplicate operation alias in endpoint {self.name!r}: {alias!r}; "
                    "operation_aliases must be unique"
                )
            normalized_operation_aliases.add(normalized)
        pnames = [p.name for p in self.parameters]
        fnames = [f.name for f in self.output_fields]
        if len(pnames) != len(set(pnames)):
            raise ValueError(f"duplicate parameter name in endpoint {self.name!r}")
        if len(fnames) != len(set(fnames)):
            raise ValueError(f"duplicate output field name in endpoint {self.name!r}")

        for field in self.output_fields:
            raw_field_schema = (
                _schema_at_projection_path(
                    self.output_schema,
                    field.projection_path,
                )
                if self.output_schema
                else {}
            )

            if field.json_schema and raw_field_schema:
                if not _schema_type_shape_compatible(
                    field.json_schema,
                    raw_field_schema,
                ):
                    raise ValueError(
                        "field json_schema is incompatible with the raw output schema in endpoint "
                        f"{self.name!r}: {field.name!r}"
                    )

            if field.unit is None:
                continue

            declared_quantity_schema = field.json_schema or raw_field_schema
            if field.unit_normalization is not None and not declared_quantity_schema:
                raise ValueError(
                    "unit normalization requires a declared numeric field schema in endpoint "
                    f"{self.name!r}: {field.name!r}"
                )
            if declared_quantity_schema and not _schema_supports_unit(
                declared_quantity_schema,
                require_declared_type=True,
            ):
                raise ValueError(
                    "a field with unit metadata must resolve to a numeric scalar or "
                    f"numeric-array schema in endpoint {self.name!r}: {field.name!r}"
                )

        if self.server_projection is not None:
            remapped_source_fields = [
                field.name
                for field in self.output_fields
                if field.projection_path != (field.name,)
            ]
            if remapped_source_fields and not self.output_schema:
                raise ValueError(
                    "server projection with provider-specific field paths requires an explicit "
                    "output_schema in endpoint "
                    f"{self.name!r}: " + ", ".join(sorted(remapped_source_fields))
                )

            unknown_projection_fields = sorted(
                set(self.server_projection.field_map) - set(fnames)
            )
            if unknown_projection_fields:
                raise ValueError(
                    "server projection field_map contains undeclared output fields in endpoint "
                    f"{self.name!r}: " + ", ".join(unknown_projection_fields)
                )

            projection_parameter = self.server_projection.parameter
            conflicting_parameters = [
                parameter
                for parameter in self.parameters
                if (parameter.wire_name or parameter.name) == projection_parameter
                and parameter.location != "query"
            ]
            if conflicting_parameters:
                raise ValueError(
                    "server projection parameter conflicts with a non-query parameter in endpoint "
                    f"{self.name!r}: {projection_parameter!r}"
                )

        paths = [(field.name, field.projection_path) for field in self.output_fields]
        if len({path for _, path in paths}) != len(paths):
            raise ValueError(f"duplicate output field path in endpoint {self.name!r}")

        # Source paths may overlap (for example "data" and "data.band_gap") as long as their
        # projected result paths do not. This lets adapters expose nested declared fields while
        # preserving the existing parent field. Result-path collision checks below remain the
        # fail-closed boundary for ambiguous projection output.
        # Preserve the historical validation error when overlapping source paths would also
        # collide in the projected result. Source-path overlap is allowed only when adapters
        # explicitly remap the result paths to disjoint keys.
        projection_entries = [
            (field.name, field.projection_path, field.result_projection_path)
            for field in self.output_fields
        ]
        for index, (left_name, left_path, left_result) in enumerate(projection_entries):
            for right_name, right_path, right_result in projection_entries[index + 1 :]:
                source_shorter, source_longer = (
                    (left_path, right_path)
                    if len(left_path) <= len(right_path)
                    else (right_path, left_path)
                )
                result_shorter, result_longer = (
                    (left_result, right_result)
                    if len(left_result) <= len(right_result)
                    else (right_result, left_result)
                )
                source_overlaps = (
                    source_longer[: len(source_shorter)] == source_shorter
                )
                result_overlaps = (
                    result_longer[: len(result_shorter)] == result_shorter
                )
                wildcard_mergeable = (
                    "*" in source_longer
                    and "*" in result_longer
                )
                if source_overlaps and result_overlaps and not wildcard_mergeable:
                    raise ValueError(
                        "overlapping output field paths in endpoint "
                        f"{self.name!r}: {left_name!r} and {right_name!r}"
                    )

        result_paths = [
            (field.name, field.result_projection_path)
            for field in self.output_fields
        ]
        if len({path for _, path in result_paths}) != len(result_paths):
            raise ValueError(f"duplicate output result path in endpoint {self.name!r}")
        for index, (left_name, left_path) in enumerate(result_paths):
            for right_name, right_path in result_paths[index + 1 :]:
                shorter, longer = (
                    (left_path, right_path)
                    if len(left_path) <= len(right_path)
                    else (right_path, left_path)
                )
                if (
                    longer[: len(shorter)] == shorter
                    and "*" not in longer
                ):
                    raise ValueError(
                        "overlapping output result paths in endpoint "
                        f"{self.name!r}: {left_name!r} and {right_name!r}"
                    )
        return self

    @model_serializer(mode="wrap")
    def serialize_endpoint(self, handler: Any) -> dict[str, Any]:
        """Omit the empty auth default so legacy public contracts serialize identically."""

        data = handler(self)
        if not self.auth_requirements:
            data.pop("auth_requirements", None)
        return data

    @property
    def auth_required(self) -> bool:
        """Whether every declared auth alternative requires at least one credential."""

        return bool(self.auth_requirements) and all(
            bool(requirement.schemes) for requirement in self.auth_requirements
        )

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"metadata"})
        if not self.auth_requirements:
            # Preserve pre-auth-contract fingerprints for public endpoints.
            payload.pop("auth_requirements", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ToolSpec(StrictModel):
    name: str
    namespace: str | None = None
    description: str = ""
    endpoints: list[EndpointSpec]
    source_type: str | None = None
    license: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    remote: bool = False
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_execution_metadata(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "execution_metadata" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        execution_metadata = _legacy_tool_execution_metadata(metadata)
        if not execution_metadata:
            return value
        migrated = dict(value)
        migrated["execution_metadata"] = execution_metadata
        return migrated

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_remote_classification(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "remote" in value:
            return value
        metadata = value.get("metadata")
        if not isinstance(metadata, dict):
            return value
        adapter = metadata.get("adapter")
        if not (bool(metadata.get("remote")) or adapter in _REMOTE_ADAPTERS):
            return value
        migrated = dict(value)
        migrated["remote"] = True
        return migrated

    @model_validator(mode="after")
    def validate_endpoints(self) -> ToolSpec:
        _validate_execution_metadata(self.execution_metadata)
        if self.provider is not None and not self.provider.strip():
            raise ValueError("tool provider must be non-empty when provided")
        if self.access_mode is not None and not self.access_mode.strip():
            raise ValueError("tool access_mode must be non-empty when provided")
        names = [e.name for e in self.endpoints]
        if not names:
            raise ValueError("tool must define at least one endpoint")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate endpoint name in tool {self.name!r}")
        return self

    @property
    def key(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={"metadata", "endpoints"},
        )
        endpoint_payloads: list[dict[str, Any]] = []
        for endpoint in self.endpoints:
            endpoint_payload = endpoint.model_dump(mode="json", exclude={"metadata"})
            if not endpoint.auth_requirements:
                # Keep existing public-tool fingerprints stable across this migration.
                endpoint_payload.pop("auth_requirements", None)
            endpoint_payloads.append(endpoint_payload)
        payload["endpoints"] = endpoint_payloads
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def endpoint(self, name: str) -> EndpointSpec:
        for endpoint in self.endpoints:
            if endpoint.name == name:
                return endpoint
        raise KeyError(name)


class EvidenceRequirements(StrictModel):
    provenance: bool = False
    license: bool = False
    units: bool = False
    source_type: str | None = None


class QueryIntent(StrictModel):
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    preferred_endpoints: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    field_evidence: dict[str, EvidenceRequirements] = Field(default_factory=dict)


FallbackScope = Literal["disabled", "same_provider", "cross_provider"]
RetrievalMode = Literal["coverage", "corroborate"]


class PlanRequest(StrictModel):
    query: str
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    field_evidence: dict[str, EvidenceRequirements] = Field(default_factory=dict)
    max_calls: int = Field(default=1, ge=1, le=32)
    retrieval_mode: RetrievalMode = "coverage"
    fallback_scope: FallbackScope = "disabled"
    max_fallbacks: int = Field(default=2, ge=0, le=8)

    @model_validator(mode="after")
    def validate_field_evidence(self) -> PlanRequest:
        normalized: dict[str, str] = {}
        for semantic_id, requirement in self.field_evidence.items():
            if not semantic_id.strip():
                raise ValueError("field_evidence semantic IDs must be non-empty")
            if semantic_id != semantic_id.strip():
                raise ValueError(
                    "field_evidence semantic IDs must not have surrounding whitespace"
                )
            key = "".join(
                char.lower()
                for char in semantic_id
                if char.isalnum()
            )
            if not key:
                raise ValueError(
                    "field_evidence semantic IDs must contain letters or numbers"
                )
            previous = normalized.get(key)
            if previous is not None and previous != semantic_id:
                raise ValueError(
                    "field_evidence contains ambiguous normalized semantic IDs: "
                    f"{previous!r}, {semantic_id!r}"
                )
            normalized[key] = semantic_id
            if (
                self.evidence.source_type is not None
                and requirement.source_type is not None
                and self.evidence.source_type != requirement.source_type
            ):
                raise ValueError(
                    "field_evidence source_type conflicts with global evidence "
                    f"for {semantic_id!r}"
                )
        return self


class ScoreComponent(StrictModel):
    """One deterministic contribution to candidate ranking."""

    kind: str
    value: float
    matched: str | None = None


FieldSelectionReason = Literal[
    "identifier",
    "field_exact",
    "field_lexical",
    "field_substring",
    "recall_fallback",
    "decision_backend",
]
CandidateSelectionSource = Literal[
    "deterministic",
    "semantic_recall",
    "endpoint_disambiguation",
    "decision_backend",
    "decision_recall",
]


class CapabilityRouteCandidate(StrictModel):
    """One lightweight ranked route reference returned without schema materialization."""

    rank: int = Field(ge=1)
    route_id: str
    tool: str
    endpoint: str
    score: float
    matched_fields: list[str] = Field(default_factory=list)
    score_components: list[ScoreComponent] = Field(default_factory=list)
    selection_source: CandidateSelectionSource = "deterministic"
    read_only: bool | None = None
    destructive: bool | None = None
    provider: str | None = None
    access_mode: str | None = None
    tool_fingerprint: str
    endpoint_fingerprint: str


class CapabilityRouteRetrieval(StrictModel):
    """Ordered Top-K lightweight route references for downstream preselection."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    executable_only: bool = False
    candidates: list[CapabilityRouteCandidate] = Field(default_factory=list)


class CapabilityCandidate(StrictModel):
    """One ranked registered capability returned without execution."""

    rank: int = Field(ge=1)
    route_id: str
    tool: str
    endpoint: str
    tool_description: str = ""
    endpoint_description: str = ""
    score: float
    matched_fields: list[str] = Field(default_factory=list)
    score_components: list[ScoreComponent] = Field(default_factory=list)
    selection_source: CandidateSelectionSource = "deterministic"
    parameters: list[ParameterSpec] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_fields: list[FieldSpec] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    read_only: bool | None = None
    destructive: bool | None = None
    source_type: str | None = None
    license: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    tool_fingerprint: str
    endpoint_fingerprint: str


class CapabilityRetrieval(StrictModel):
    """Ordered Top-K capability retrieval result for downstream selection."""

    query: str
    registry_version: int
    requested_k: int = Field(ge=1)
    total_ranked: int = Field(ge=0)
    executable_only: bool = False
    candidates: list[CapabilityCandidate] = Field(default_factory=list)


class FieldSelectionExplanation(StrictModel):
    """Machine-readable reason a declared output field is retained."""

    field: str
    reason: FieldSelectionReason


class PlanExplanation(StrictModel):
    """Auditable structural explanation for one planned call.

    This records locally observable routing signals, not model chain-of-thought.
    """

    candidate_selection: CandidateSelectionSource = "deterministic"
    score_components: list[ScoreComponent] = Field(default_factory=list)
    field_selection: list[FieldSelectionExplanation] = Field(default_factory=list)
    ignored_arguments: list[str] = Field(default_factory=list)


class ToolCall(StrictModel):
    tool: str
    endpoint: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list)
    # Evidence declared as available by the selected trusted route surface.
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    # Global evidence explicitly required by the caller for this compiled call.
    required_evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    # Per-local-field evidence explicitly required by the caller.
    field_evidence: dict[str, EvidenceRequirements] = Field(default_factory=dict)
    schema_fingerprint: str
    tool_fingerprint: str | None = None
    missing_required_arguments: list[str] = Field(default_factory=list)
    score: float = 0.0
    explanation: PlanExplanation | None = None

    @property
    def executable(self) -> bool:
        return not self.missing_required_arguments


class FallbackRoute(StrictModel):
    """Precompiled alternatives for one primary call in an ExecutionPlan."""

    primary_call_index: int = Field(ge=0)
    alternatives: list[ToolCall] = Field(default_factory=list)


class SemanticFieldRequirement(StrictModel):
    """One query-matched semantic field requirement used for plan coverage."""

    semantic_id: str
    qualifiers: list[str] = Field(default_factory=list)


class PlanCoverage(StrictModel):
    """Structured semantic-field coverage for one execution plan."""

    required: list[SemanticFieldRequirement] = Field(default_factory=list)
    covered: list[SemanticFieldRequirement] = Field(default_factory=list)
    uncovered: list[SemanticFieldRequirement] = Field(default_factory=list)
    complete: bool = False


class ExecutionPlan(StrictModel):
    query: str
    registry_version: int
    calls: list[ToolCall] = Field(default_factory=list)
    fallback_routes: list[FallbackRoute] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    coverage: PlanCoverage | None = None

    @model_validator(mode="after")
    def validate_fallback_routes(self) -> ExecutionPlan:
        seen: set[int] = set()
        for route in self.fallback_routes:
            if route.primary_call_index >= len(self.calls):
                raise ValueError("fallback route primary_call_index is outside plan.calls")
            if route.primary_call_index in seen:
                raise ValueError("duplicate fallback route for primary call index")
            seen.add(route.primary_call_index)
        return self

    @property
    def executable(self) -> bool:
        return bool(self.calls) and all(call.executable for call in self.calls)

    def fallback_route(self, primary_call_index: int) -> FallbackRoute | None:
        return next(
            (
                route
                for route in self.fallback_routes
                if route.primary_call_index == primary_call_index
            ),
            None,
        )


class ToolResult(StrictModel):
    tool: str
    endpoint: str
    data: Any
    projected_fields: list[str] = Field(default_factory=list)
    field_contracts: dict[str, ResultFieldContract] = Field(default_factory=dict)
