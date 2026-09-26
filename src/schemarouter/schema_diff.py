from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

from .models import EndpointSpec, StrictModel, ToolSpec

SchemaChangeSeverity = Literal["info", "compatible", "breaking", "security"]
SchemaCompatibility = Literal["identical", "compatible", "breaking", "security_review"]


class SchemaChange(StrictModel):
    """One semantic difference between two trusted schema snapshots."""

    path: str
    kind: str
    severity: SchemaChangeSeverity
    old: Any = None
    new: Any = None
    message: str = ""


class SchemaDiffReport(StrictModel):
    """Machine-readable explanation for a schema fingerprint change.

    Compatibility is intentionally conservative. A report may explain why two fingerprints differ,
    but it never authorizes an old plan or binding to execute against a new schema.
    """

    compatibility: SchemaCompatibility
    old_fingerprint: str
    new_fingerprint: str
    changes: list[SchemaChange] = Field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def _compatibility(changes: list[SchemaChange]) -> SchemaCompatibility:
    if not changes:
        return "identical"
    if any(change.severity == "security" for change in changes):
        return "security_review"
    if any(change.severity == "breaking" for change in changes):
        return "breaking"
    return "compatible"


def _change(
    changes: list[SchemaChange],
    *,
    path: str,
    kind: str,
    severity: SchemaChangeSeverity,
    old: Any = None,
    new: Any = None,
    message: str = "",
) -> None:
    changes.append(
        SchemaChange(
            path=path,
            kind=kind,
            severity=severity,
            old=old,
            new=new,
            message=message,
        )
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _schema_change_severity(old: dict[str, Any], new: dict[str, Any]) -> SchemaChangeSeverity:
    """Return compatible only for a few schema widenings that are safe to prove locally."""

    if old == new:
        return "info"

    old_type = old.get("type")
    new_type = new.get("type")
    if old_type != new_type:
        if old_type == "integer" and new_type == "number":
            widened = dict(old)
            widened["type"] = "number"
            if widened == new:
                return "compatible"
        return "breaking"

    old_enum = old.get("enum")
    new_enum = new.get("enum")
    if old_enum != new_enum:
        if isinstance(old_enum, list) and isinstance(new_enum, list):
            old_values = {_canonical_json(value) for value in old_enum}
            new_values = {_canonical_json(value) for value in new_enum}
            if old_values <= new_values:
                widened = dict(old)
                widened["enum"] = new_enum
                if widened == new:
                    return "compatible"
        return "breaking"

    old_required_raw = old.get("required")
    new_required_raw = new.get("required")
    old_required = set(old_required_raw) if isinstance(old_required_raw, list) else set()
    new_required = set(new_required_raw) if isinstance(new_required_raw, list) else set()
    if old_required != new_required:
        if new_required <= old_required:
            widened = dict(old)
            if isinstance(new_required_raw, list):
                widened["required"] = new_required_raw
            else:
                widened.pop("required", None)
            if widened == new:
                return "compatible"
        return "breaking"

    for keyword in ("minimum", "exclusiveMinimum", "minLength", "minItems"):
        old_value = old.get(keyword)
        new_value = new.get(keyword)
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            if new_value > old_value:
                return "breaking"
    for keyword in ("maximum", "exclusiveMaximum", "maxLength", "maxItems"):
        old_value = old.get(keyword)
        new_value = new.get(keyword)
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            if new_value < old_value:
                return "breaking"

    # JSON Schema is expressive enough that proving arbitrary compatibility is difficult.
    # Unknown changes are deliberately treated as breaking rather than guessed safe.
    return "breaking"


def _compare_parameter(
    changes: list[SchemaChange],
    *,
    prefix: str,
    old: Any,
    new: Any,
) -> None:
    if old.required != new.required:
        _change(
            changes,
            path=f"{prefix}.required",
            kind="required_changed",
            severity="breaking" if new.required else "compatible",
            old=old.required,
            new=new.required,
        )

    for attribute in ("wire_name", "location", "style", "explode", "allow_reserved"):
        old_value = getattr(old, attribute)
        new_value = getattr(new, attribute)
        if old_value != new_value:
            _change(
                changes,
                path=f"{prefix}.{attribute}",
                kind=f"{attribute}_changed",
                severity="breaking",
                old=old_value,
                new=new_value,
            )

    if old.json_schema != new.json_schema:
        _change(
            changes,
            path=f"{prefix}.json_schema",
            kind="json_schema_changed",
            severity=_schema_change_severity(old.json_schema, new.json_schema),
            old=old.json_schema,
            new=new.json_schema,
        )

    if old.aliases != new.aliases:
        _change(
            changes,
            path=f"{prefix}.aliases",
            kind="aliases_changed",
            severity="compatible",
            old=old.aliases,
            new=new.aliases,
        )
    if old.description != new.description:
        _change(
            changes,
            path=f"{prefix}.description",
            kind="description_changed",
            severity="info",
            old=old.description,
            new=new.description,
        )


def _compare_field(
    changes: list[SchemaChange],
    *,
    prefix: str,
    old: Any,
    new: Any,
) -> None:
    if old.path != new.path:
        _change(
            changes,
            path=f"{prefix}.path",
            kind="projection_path_changed",
            severity="breaking",
            old=old.path,
            new=new.path,
        )
    if old.result_path != new.result_path:
        _change(
            changes,
            path=f"{prefix}.result_path",
            kind="result_projection_path_changed",
            severity="breaking",
            old=old.result_path,
            new=new.result_path,
        )
    if old.semantic_id != new.semantic_id:
        _change(
            changes,
            path=f"{prefix}.semantic_id",
            kind="semantic_id_changed",
            severity="breaking",
            old=old.semantic_id,
            new=new.semantic_id,
        )
    if old.unit_normalization != new.unit_normalization:
        _change(
            changes,
            path=f"{prefix}.unit_normalization",
            kind="unit_normalization_changed",
            severity="breaking",
            old=(
                old.unit_normalization.model_dump(mode="json")
                if old.unit_normalization is not None
                else None
            ),
            new=(
                new.unit_normalization.model_dump(mode="json")
                if new.unit_normalization is not None
                else None
            ),
        )
    if old.qualifiers != new.qualifiers:
        _change(
            changes,
            path=f"{prefix}.qualifiers",
            kind="qualifiers_changed",
            severity="breaking",
            old=old.qualifiers,
            new=new.qualifiers,
        )
    if old.identifier != new.identifier:
        _change(
            changes,
            path=f"{prefix}.identifier",
            kind="identifier_changed",
            severity="breaking",
            old=old.identifier,
            new=new.identifier,
        )
    for attribute in ("unit", "source_type", "license"):
        old_value = getattr(old, attribute)
        new_value = getattr(new, attribute)
        if old_value != new_value:
            _change(
                changes,
                path=f"{prefix}.{attribute}",
                kind=f"{attribute}_changed",
                severity="breaking",
                old=old_value,
                new=new_value,
            )
    if old.json_schema != new.json_schema:
        _change(
            changes,
            path=f"{prefix}.json_schema",
            kind="json_schema_changed",
            severity=_schema_change_severity(old.json_schema, new.json_schema),
            old=old.json_schema,
            new=new.json_schema,
        )
    if old.aliases != new.aliases:
        _change(
            changes,
            path=f"{prefix}.aliases",
            kind="aliases_changed",
            severity="compatible",
            old=old.aliases,
            new=new.aliases,
        )
    if old.description != new.description:
        _change(
            changes,
            path=f"{prefix}.description",
            kind="description_changed",
            severity="info",
            old=old.description,
            new=new.description,
        )


def compare_endpoint_specs(old: EndpointSpec, new: EndpointSpec) -> SchemaDiffReport:
    """Explain semantic differences between endpoint snapshots.

    This function is diagnostic only. The executor still requires an exact current fingerprint.
    """

    changes: list[SchemaChange] = []

    if old.name != new.name:
        _change(
            changes,
            path="name",
            kind="endpoint_name_changed",
            severity="breaking",
            old=old.name,
            new=new.name,
        )
    if old.description != new.description:
        _change(
            changes,
            path="description",
            kind="description_changed",
            severity="info",
            old=old.description,
            new=new.description,
        )
    if old.operation_aliases != new.operation_aliases:
        _change(
            changes,
            path="operation_aliases",
            kind="operation_aliases_changed",
            severity="compatible",
            old=old.operation_aliases,
            new=new.operation_aliases,
            message=(
                "Trusted planning aliases changed; exact fingerprints still require "
                "replanning."
            ),
        )
    if old.method != new.method:
        old_method = old.method.upper() if isinstance(old.method, str) else None
        new_method = new.method.upper() if isinstance(new.method, str) else None
        mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}
        severity: SchemaChangeSeverity = (
            "security"
            if new_method in mutating_methods and old_method != new_method
            else "breaking"
        )
        _change(
            changes,
            path="method",
            kind="method_changed",
            severity=severity,
            old=old.method,
            new=new.method,
            message=(
                "HTTP method changed to a mutating method and requires local policy review."
                if severity == "security"
                else ""
            ),
        )

    if old.path != new.path:
        _change(
            changes,
            path="path",
            kind="path_changed",
            severity="breaking",
            old=old.path,
            new=new.path,
        )

    if old.read_only != new.read_only:
        if old.read_only is True and new.read_only is not True:
            severity: SchemaChangeSeverity = "security"
        elif new.read_only is False and old.read_only is not False:
            severity = "security"
        else:
            severity = "breaking"
        _change(
            changes,
            path="read_only",
            kind="execution_semantics_changed",
            severity=severity,
            old=old.read_only,
            new=new.read_only,
            message="Side-effect classification changed and requires local policy review.",
        )

    if old.destructive != new.destructive:
        severity = "security" if new.destructive is True else "breaking"
        _change(
            changes,
            path="destructive",
            kind="destructive_semantics_changed",
            severity=severity,
            old=old.destructive,
            new=new.destructive,
            message="Destructive classification changed and requires local policy review.",
        )

    if old.execution_metadata != new.execution_metadata:
        _change(
            changes,
            path="execution_metadata",
            kind="execution_metadata_changed",
            severity="security",
            old=old.execution_metadata,
            new=new.execution_metadata,
            message=(
                "Runtime adapter semantics changed and require execution review; "
                "replan and rebind before execution."
            ),
        )

    old_parameters = {parameter.name: parameter for parameter in old.parameters}
    new_parameters = {parameter.name: parameter for parameter in new.parameters}
    for name in old_parameters.keys() - new_parameters.keys():
        _change(
            changes,
            path=f"parameters.{name}",
            kind="parameter_removed",
            severity="breaking",
            old=old_parameters[name].model_dump(mode="json"),
        )
    for name in new_parameters.keys() - old_parameters.keys():
        parameter = new_parameters[name]
        _change(
            changes,
            path=f"parameters.{name}",
            kind="parameter_added",
            severity="breaking" if parameter.required else "compatible",
            new=parameter.model_dump(mode="json"),
        )
    for name in old_parameters.keys() & new_parameters.keys():
        _compare_parameter(
            changes,
            prefix=f"parameters.{name}",
            old=old_parameters[name],
            new=new_parameters[name],
        )
    old_parameter_order = [parameter.name for parameter in old.parameters]
    new_parameter_order = [parameter.name for parameter in new.parameters]
    if (
        set(old_parameter_order) == set(new_parameter_order)
        and old_parameter_order != new_parameter_order
    ):
        _change(
            changes,
            path="parameters",
            kind="parameter_order_changed",
            severity="compatible",
            old=old_parameter_order,
            new=new_parameter_order,
        )

    old_fields = {field.name: field for field in old.output_fields}
    new_fields = {field.name: field for field in new.output_fields}
    for name in old_fields.keys() - new_fields.keys():
        _change(
            changes,
            path=f"output_fields.{name}",
            kind="output_field_removed",
            severity="breaking",
            old=old_fields[name].model_dump(mode="json"),
        )
    for name in new_fields.keys() - old_fields.keys():
        field = new_fields[name]
        _change(
            changes,
            path=f"output_fields.{name}",
            kind="output_field_added",
            severity="compatible" if not field.json_schema else "breaking",
            new=field.model_dump(mode="json"),
            message=(
                "Untyped optional output field is additive."
                if not field.json_schema
                else (
                    "Typed output field adds raw-response validation for that key and is "
                    "conservatively treated as breaking."
                )
            ),
        )
    for name in old_fields.keys() & new_fields.keys():
        _compare_field(
            changes,
            prefix=f"output_fields.{name}",
            old=old_fields[name],
            new=new_fields[name],
        )
    old_field_order = [field.name for field in old.output_fields]
    new_field_order = [field.name for field in new.output_fields]
    if set(old_field_order) == set(new_field_order) and old_field_order != new_field_order:
        _change(
            changes,
            path="output_fields",
            kind="output_field_order_changed",
            severity="compatible",
            old=old_field_order,
            new=new_field_order,
        )

    for attribute in ("input_schema", "output_schema"):
        old_value = getattr(old, attribute)
        new_value = getattr(new, attribute)
        if old_value != new_value:
            _change(
                changes,
                path=attribute,
                kind=f"{attribute}_changed",
                severity=_schema_change_severity(old_value, new_value),
                old=old_value,
                new=new_value,
            )

    return SchemaDiffReport(
        compatibility=_compatibility(changes),
        old_fingerprint=old.fingerprint,
        new_fingerprint=new.fingerprint,
        changes=changes,
    )


def _added_endpoint_severity(
    endpoint: EndpointSpec,
    *,
    tool_remote: bool,
) -> SchemaChangeSeverity:
    method = endpoint.method.upper() if isinstance(endpoint.method, str) else None
    if endpoint.destructive is True:
        return "security"
    if endpoint.read_only is False:
        return "security"
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "security"
    if tool_remote and endpoint.read_only is None:
        return "security"
    return "compatible"


def compare_tool_specs(old: ToolSpec, new: ToolSpec) -> SchemaDiffReport:
    """Explain why two tool fingerprints differ without weakening drift checks."""

    changes: list[SchemaChange] = []
    if old.key != new.key:
        _change(
            changes,
            path="key",
            kind="tool_key_changed",
            severity="breaking",
            old=old.key,
            new=new.key,
        )
    if old.description != new.description:
        _change(
            changes,
            path="description",
            kind="description_changed",
            severity="info",
            old=old.description,
            new=new.description,
        )
    if old.provider != new.provider:
        _change(
            changes,
            path="provider",
            kind="information_provider_changed",
            severity="security",
            old=old.provider,
            new=new.provider,
            message="Logical information provider changed and requires provenance review.",
        )
    if old.access_mode != new.access_mode:
        _change(
            changes,
            path="access_mode",
            kind="access_mode_changed",
            severity="security",
            old=old.access_mode,
            new=new.access_mode,
            message="Provider access mode changed and requires execution review.",
        )
    if old.remote != new.remote:
        _change(
            changes,
            path="remote",
            kind="execution_origin_changed",
            severity="security",
            old=old.remote,
            new=new.remote,
            message=(
                "Local/remote execution-origin classification changed "
                "and requires policy review."
            ),
        )
    if old.execution_metadata != new.execution_metadata:
        _change(
            changes,
            path="execution_metadata",
            kind="tool_execution_metadata_changed",
            severity="security",
            old=old.execution_metadata,
            new=new.execution_metadata,
            message="Transport or binding identity changed and requires execution review.",
        )
    for attribute in ("source_type", "license"):
        old_value = getattr(old, attribute)
        new_value = getattr(new, attribute)
        if old_value != new_value:
            _change(
                changes,
                path=attribute,
                kind=f"{attribute}_changed",
                severity="breaking",
                old=old_value,
                new=new_value,
            )

    old_endpoints = {endpoint.name: endpoint for endpoint in old.endpoints}
    new_endpoints = {endpoint.name: endpoint for endpoint in new.endpoints}
    for name in old_endpoints.keys() - new_endpoints.keys():
        _change(
            changes,
            path=f"endpoints.{name}",
            kind="endpoint_removed",
            severity="breaking",
            old=old_endpoints[name].model_dump(mode="json"),
        )
    for name in new_endpoints.keys() - old_endpoints.keys():
        endpoint = new_endpoints[name]
        severity = _added_endpoint_severity(
            endpoint,
            tool_remote=new.remote,
        )
        _change(
            changes,
            path=f"endpoints.{name}",
            kind="endpoint_added",
            severity=severity,
            new=endpoint.model_dump(mode="json"),
            message=(
                "New endpoint increases the side-effect or remote-unclassified authority surface."
                if severity == "security"
                else "New explicitly read-only endpoint is additive."
            ),
        )
    for name in old_endpoints.keys() & new_endpoints.keys():
        endpoint_report = compare_endpoint_specs(old_endpoints[name], new_endpoints[name])
        for change in endpoint_report.changes:
            changes.append(
                change.model_copy(update={"path": f"endpoints.{name}.{change.path}"})
            )

    old_order = [endpoint.name for endpoint in old.endpoints]
    new_order = [endpoint.name for endpoint in new.endpoints]
    if set(old_order) == set(new_order) and old_order != new_order:
        _change(
            changes,
            path="endpoints",
            kind="endpoint_order_changed",
            severity="compatible",
            old=old_order,
            new=new_order,
        )

    return SchemaDiffReport(
        compatibility=_compatibility(changes),
        old_fingerprint=old.fingerprint,
        new_fingerprint=new.fingerprint,
        changes=changes,
    )
