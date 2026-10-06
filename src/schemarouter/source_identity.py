from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from ._url_safety import safe_provenance_url
from .adapters.base import RefreshProfile
from .canonical_json import canonical_json_sha256
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
    qualifiers: tuple[tuple[str, str], ...] = ()


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


def _canonical_identity_value(value: Any) -> str:
    # This qualifier preserves the historical default=str coercion because
    # refresh identity metadata may contain host objects. Persisted source
    # identity digests below use the strict canonical JSON contract.
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _profile_identity_qualifiers(
    tool: ToolSpec,
    refresh: RefreshProfile,
) -> tuple[tuple[str, str], ...]:
    items: list[tuple[str, str]] = []
    for key in refresh.identity_metadata_keys:
        if key in tool.metadata:
            items.append(
                (
                    f"metadata.{key}",
                    _canonical_identity_value(tool.metadata[key]),
                )
            )
    for key in refresh.identity_execution_keys:
        if key in tool.execution_metadata:
            items.append(
                (
                    f"execution_metadata.{key}",
                    _canonical_identity_value(tool.execution_metadata[key]),
                )
            )
    return tuple(sorted(items))


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def structured_source_identity_digest(
    identity: StructuredSourceIdentity,
) -> str:
    """Return an opaque stable digest suitable for persisted validator ownership."""

    return canonical_json_sha256(asdict(identity))


def structured_source_identity(
    tool: ToolSpec,
    refresh: RefreshProfile | None = None,
) -> StructuredSourceIdentity | None:
    """Derive a stable source identity without inspecting credential-bearing state."""

    adapter = _string_value(tool, "adapter")
    if adapter is None:
        return None
    adapter = adapter.strip().lower()
    if not adapter:
        return None

    if refresh is not None:
        source_url = _safe_url(refresh.source_url(tool))
        qualifiers = _profile_identity_qualifiers(tool, refresh)
        transport = _string_value(tool, "transport")
        transport_fingerprint = _string_value(tool, "transport_fingerprint")
        return StructuredSourceIdentity(
            adapter=adapter,
            source_url=source_url,
            transport=transport,
            transport_fingerprint=transport_fingerprint,
            qualifiers=qualifiers,
        )

    # Compatibility fallback for callers that do not yet have an AdapterRegistry.
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

def structured_source_identity_digest_for(
    tool: ToolSpec,
    refresh: RefreshProfile | None = None,
) -> str | None:
    identity = structured_source_identity(tool, refresh)
    if identity is None:
        return None
    return structured_source_identity_digest(identity)
