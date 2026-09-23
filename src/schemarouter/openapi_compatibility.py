from __future__ import annotations

from collections import Counter
from typing import Any, Literal
from urllib.parse import unquote, urlparse

from pydantic import Field

from .models import StrictModel

OpenAPISupport = Literal["supported", "partial", "unsupported"]


class OpenAPICompatibilityIssue(StrictModel):
    """One explicit compatibility limitation found in an OpenAPI document."""

    location: str
    schema_construct: str = Field(alias="construct", serialization_alias="construct")
    support: Literal["partial", "unsupported"]
    message: str


class OpenAPICompatibilityReport(StrictModel):
    """Machine-readable summary of SchemaRouter's OpenAPI import fidelity."""

    openapi_version: str | None = None
    status: OpenAPISupport
    operations_total: int = Field(ge=0)
    operations_importable: int = Field(ge=0)
    issues: list[OpenAPICompatibilityIssue] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


def _pointer(parts: tuple[str, ...]) -> str:
    if not parts:
        return "#"
    encoded = [part.replace("~", "~0").replace("/", "~1") for part in parts]
    return "#/" + "/".join(encoded)


def _safe_path(path: str) -> bool:
    parsed = urlparse(path)
    if (
        not path.startswith("/")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        return False
    return all(unquote(segment).casefold() not in {".", ".."} for segment in parsed.path.split("/"))


def _walk(node: Any, parts: tuple[str, ...] = ()):
    yield parts, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*parts, str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, (*parts, str(index)))


def _local_ref_target(document: dict[str, Any], ref: str) -> Any | None:
    if not ref.startswith("#/"):
        return None
    node: Any = document
    try:
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
    except (KeyError, TypeError, IndexError):
        return None
    return node


def _resolve_local_ref(document: dict[str, Any], value: Any) -> Any:
    current = value
    seen: set[str] = set()
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            break
        target = _local_ref_target(document, ref)
        if target is None:
            break
        seen.add(ref)
        current = target
    return current


def _collect_schema_refs(node: Any) -> set[str]:
    refs: set[str] = set()
    for _, value in _walk(node):
        if isinstance(value, dict) and isinstance(value.get("$ref"), str):
            refs.add(value["$ref"])
    return refs


def _recursive_component_refs(document: dict[str, Any]) -> set[str]:
    components = document.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    if not isinstance(schemas, dict):
        return set()

    graph: dict[str, set[str]] = {}
    prefix = "#/components/schemas/"
    for name, schema in schemas.items():
        targets: set[str] = set()
        for ref in _collect_schema_refs(schema):
            if ref.startswith(prefix):
                target = ref[len(prefix) :].replace("~1", "/").replace("~0", "~")
                if target in schemas:
                    targets.add(target)
        graph[str(name)] = targets

    recursive: set[str] = set()

    def visit(name: str, path: list[str]) -> None:
        if name in path:
            start = path.index(name)
            recursive.update(path[start:])
            return
        if name not in graph:
            return
        for target in graph[name]:
            visit(target, [*path, name])

    for name in graph:
        visit(name, [])
    return recursive


def analyze_openapi_compatibility(document: dict[str, Any]) -> OpenAPICompatibilityReport:
    """Report constructs SchemaRouter preserves, partially interprets, or cannot import safely."""

    issues: list[OpenAPICompatibilityIssue] = []
    issue_keys: set[tuple[str, str, str]] = set()

    def add(
        location: str,
        construct: str,
        support: Literal["partial", "unsupported"],
        message: str,
    ) -> None:
        key = (location, construct, support)
        if key in issue_keys:
            return
        issue_keys.add(key)
        issues.append(
            OpenAPICompatibilityIssue(
                location=location,
                construct=construct,
                support=support,
                message=message,
            )
        )

    version = document.get("openapi")
    version_text = str(version) if isinstance(version, str) else None

    for parts, node in _walk(document):
        if not isinstance(node, dict):
            continue
        location = _pointer(parts)
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#/"):
            add(
                location,
                "external_ref",
                "unsupported",
                (
                    "Cross-document $ref targets remain unresolved unless bounded external-ref "
                    "resolution is explicitly enabled during URL ingestion. URI refs that resolve "
                    "back to the loaded document are normalized automatically."
                ),
            )
        for construct in ("allOf", "oneOf", "anyOf"):
            if construct not in node:
                continue
            if construct == "allOf":
                message = (
                    "allOf is preserved for runtime validation and object properties/required "
                    "fields are flattened for planning when safely derivable; more general "
                    "composition semantics remain partial."
                )
            else:
                message = (
                    f"{construct} is preserved for runtime validation. Object properties from "
                    "response variants are exposed as conditional planner-visible output fields. "
                    "Composed request bodies are preserved as one typed root body parameter when "
                    "they cannot be safely flattened."
                )
            add(
                location,
                construct,
                "partial",
                message,
            )
        if "discriminator" in node:
            add(
                location,
                "discriminator",
                "partial",
                (
                    "Discriminator metadata is not trusted as execution authority. A oneOf JSON "
                    "request body is exposed as one typed root parameter only when every branch "
                    "requires the discriminator and proves a unique const/single-enum tag."
                ),
            )

    for name in sorted(_recursive_component_refs(document)):
        add(
            f"#/components/schemas/{name}",
            "recursive_ref",
            "partial",
            (
                "Recursive local references remain available to runtime validation but are "
                "not recursively flattened."
            ),
        )

    operations_total = 0
    operations_importable = 0
    paths = document.get("paths")
    if isinstance(paths, dict):
        for path, path_item in paths.items():
            if not isinstance(path, str) or not isinstance(path_item, dict):
                continue
            path_item = _resolve_local_ref(document, path_item)
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                method_lower = str(method).lower()
                if method_lower not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                    "trace",
                }:
                    continue
                operations_total += 1
                escaped_path = path.replace("~", "~0").replace("/", "~1")
                op_location = f"#/paths/{escaped_path}/{method_lower}"
                if not isinstance(operation, dict):
                    add(
                        op_location,
                        "operation_shape",
                        "unsupported",
                        "Operation must be an object.",
                    )
                    continue
                if not _safe_path(path):
                    add(
                        op_location,
                        "unsafe_path",
                        "unsupported",
                        "Unsafe or non-relative operation paths are skipped.",
                    )
                    continue
                operations_importable += 1

                parameters = [
                    *(
                        path_item.get("parameters", [])
                        if isinstance(path_item.get("parameters"), list)
                        else []
                    ),
                    *(
                        operation.get("parameters", [])
                        if isinstance(operation.get("parameters"), list)
                        else []
                    ),
                ]
                for index, parameter in enumerate(parameters):
                    resolved = _resolve_local_ref(document, parameter)
                    if not isinstance(resolved, dict):
                        continue

                    parameter_location = resolved.get("in")
                    parameter_pointer = f"{op_location}/parameters/{index}"
                    if parameter_location == "cookie":
                        add(
                            parameter_pointer,
                            "cookie_parameter",
                            "unsupported",
                            (
                                "Cookie parameters are not model-selectable or emitted by the "
                                "OpenAPI invoker."
                            ),
                        )
                        continue

                    default_styles = {
                        "path": "simple",
                        "query": "form",
                        "header": "simple",
                    }
                    supported_style = default_styles.get(str(parameter_location))
                    if supported_style is not None:
                        raw_style = resolved.get("style")
                        style = raw_style if isinstance(raw_style, str) else supported_style
                        if style != supported_style:
                            add(
                                parameter_pointer,
                                "parameter_style",
                                "unsupported",
                                (
                                    f"{parameter_location} parameter style {style!r} is not "
                                    f"currently serialized; supported style is "
                                    f"{supported_style!r}."
                                ),
                            )

                    if parameter_location == "query" and resolved.get("allowReserved") is True:
                        add(
                            parameter_pointer,
                            "allow_reserved",
                            "unsupported",
                            (
                                "allowReserved=true is not emitted because the HTTP client would "
                                "otherwise silently change reserved-character semantics."
                            ),
                        )

                request_body = _resolve_local_ref(document, operation.get("requestBody"))
                if isinstance(request_body, dict):
                    content = request_body.get("content")
                    if isinstance(content, dict) and content:
                        media_types = list(content)
                        if len(media_types) > 1:
                            add(
                                f"{op_location}/requestBody/content",
                                "multiple_request_content_types",
                                "partial",
                                "Only application/json is compiled into body parameters.",
                            )
                        if "application/json" not in content:
                            add(
                                f"{op_location}/requestBody/content",
                                "non_json_request_body",
                                "unsupported",
                                (
                                    "Request bodies without application/json are not compiled "
                                    "for execution."
                                ),
                            )
                        else:
                            media = content.get("application/json")
                            schema = media.get("schema") if isinstance(media, dict) else None
                            schema = _resolve_local_ref(document, schema)
                            if not isinstance(schema, dict) or not schema:
                                add(
                                    f"{op_location}/requestBody/content/application~1json/schema",
                                    "schema_less_request_body",
                                    "unsupported",
                                    (
                                        "JSON request bodies without an explicit schema cannot be "
                                        "safely represented as named planner parameters."
                                    ),
                                )

                responses = operation.get("responses")
                if isinstance(responses, dict):
                    for code, response in responses.items():
                        code_text = str(code).upper()
                        if not (
                            len(code_text) == 3
                            and code_text.startswith("2")
                            and (code_text[1:].isdigit() or code_text == "2XX")
                        ):
                            continue
                        resolved_response = _resolve_local_ref(document, response)
                        content = (
                            resolved_response.get("content")
                            if isinstance(resolved_response, dict)
                            else None
                        )
                        if isinstance(content, dict) and content:
                            if len(content) > 1:
                                add(
                                    f"{op_location}/responses/{code}/content",
                                    "multiple_response_content_types",
                                    "partial",
                                    (
                                        "SchemaRouter validates supported JSON media types; "
                                        "other success media types remain partial."
                                    ),
                                )
                            if not any(
                                media in content
                                for media in ("application/json", "application/problem+json")
                            ):
                                add(
                                    f"{op_location}/responses/{code}/content",
                                    "non_json_response",
                                    "unsupported",
                                    (
                                        "Non-JSON response schemas are not imported for output "
                                        "validation."
                                    ),
                                )

                if operation.get("callbacks"):
                    add(
                        f"{op_location}/callbacks",
                        "callbacks",
                        "unsupported",
                        "OpenAPI callbacks are not registered as executable endpoints.",
                    )
                if "security" in operation:
                    add(
                        f"{op_location}/security",
                        "security_requirements",
                        "partial",
                        (
                            "Security requirements are preserved as metadata; credentials must "
                            "be bound locally."
                        ),
                    )

    if document.get("webhooks"):
        add(
            "#/webhooks",
            "webhooks",
            "unsupported",
            "OpenAPI webhooks are not registered as executable endpoints.",
        )

    servers = document.get("servers")
    if isinstance(servers, list):
        for index, server in enumerate(servers):
            if isinstance(server, dict) and server.get("variables"):
                add(
                    f"#/servers/{index}/variables",
                    "server_variables",
                    "partial",
                    "Server variables are not expanded automatically; bind an explicit base URL.",
                )

    counts = Counter(issue.support for issue in issues)
    if not issues:
        status: OpenAPISupport = "supported"
    elif operations_importable == 0 and operations_total > 0:
        status = "unsupported"
    else:
        status = "partial"

    return OpenAPICompatibilityReport(
        openapi_version=version_text,
        status=status,
        operations_total=operations_total,
        operations_importable=operations_importable,
        issues=issues,
        counts={key: counts.get(key, 0) for key in ("partial", "unsupported")},
    )
