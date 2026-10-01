from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._url_safety import safe_provenance_url
from .models import ToolSpec


@dataclass(frozen=True)
class StructuredSourceIdentity:
    """Credential-free identity of the structured source behind one ToolSpec."""

    adapter: str
    source_url: str | None = None
    resolved_source_url: str | None = None
    transport: str | None = None
    transport_fingerprint: str | None = None
    openapi_external_refs: bool = False
    openapi_ref_max_depth: int | None = None
    openapi_ref_max_documents: int | None = None
    openapi_ref_max_bytes: int | None = None


def _string_value(
    tool: ToolSpec,
    key: str,
    *,
    execution_first: bool = True,
) -> str | None:
    sources = (
        (tool.execution_metadata, tool.metadata)
        if execution_first
        else (tool.metadata, tool.execution_metadata)
    )
    for source in sources:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _safe_url(value: str | None) -> str | None:
    if value is None:
        return None
    safe = safe_provenance_url(value)
    return safe if not safe.startswith("<redacted-") else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def structured_source_identity(tool: ToolSpec) -> StructuredSourceIdentity | None:
    """Derive a stable source identity without inspecting credential-bearing state."""

    adapter = _string_value(tool, "adapter")
    if adapter is None:
        return None
    adapter = adapter.strip().lower()
    if not adapter:
        return None

    source_url: str | None = None
    resolved_source_url: str | None = None
    transport: str | None = None
    transport_fingerprint: str | None = None
    external_refs = False
    max_depth: int | None = None
    max_documents: int | None = None
    max_bytes: int | None = None

    if adapter == "optimade":
        source_url = _safe_url(_string_value(tool, "versioned_base_url"))
    elif adapter == "openapi":
        source_url = _safe_url(
            _string_value(tool, "source_url", execution_first=False)
        )
        resolved_source_url = _safe_url(
            _string_value(tool, "resolved_schema_url", execution_first=False)
        )
        external_refs = bool(tool.metadata.get("external_refs_enabled", False))
        limits = tool.metadata.get("external_ref_limits")
        if isinstance(limits, dict):
            max_depth = _positive_int(limits.get("max_depth"))
            max_documents = _positive_int(limits.get("max_documents"))
            max_bytes = _positive_int(limits.get("max_bytes"))
    else:
        source_url = _safe_url(_string_value(tool, "source_url"))

    if adapter == "mcp":
        transport = _string_value(tool, "transport")
        transport_fingerprint = _string_value(tool, "transport_fingerprint")

    return StructuredSourceIdentity(
        adapter=adapter,
        source_url=source_url,
        resolved_source_url=resolved_source_url,
        transport=transport,
        transport_fingerprint=transport_fingerprint,
        openapi_external_refs=external_refs,
        openapi_ref_max_depth=max_depth,
        openapi_ref_max_documents=max_documents,
        openapi_ref_max_bytes=max_bytes,
    )
