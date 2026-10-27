"""Opt-in source-revision-pinned DeepWiki MCP for original-paper P2/A5 E1.

Real tools/list output is untrusted. Only a separate exact-fingerprint host
review can narrow and publish one known read operation with existing fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .adapters.mcp import (
    MCPClientFactory,
    MCPRemoteInvoker,
    inspect_mcp_url,
)
from .errors import NonRetryableInvocationError, SchemaSourceError
from .models import ToolSpec
from .network_policy import NetworkPolicy
from .semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter

DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"
DEEPWIKI_SOURCE_TYPE = "mcp_deepwiki"
DEEPWIKI_RESEARCH_LICENSE = "source-license-unverified-research-only"
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,99}/[A-Za-z0-9._-]{1,100}\Z")
_PAGE = re.compile(r"\s*-\s+\d+(?:\.\d+)*\s+\S.*\Z")
_MAX_OUTLINE_BYTES = 131072


def _reviewed_repo_parameter_schema(schema: Any) -> bool:
    """Only drop nonvalidation descriptions; never weaken source constraints."""
    if type(schema) is not dict or schema.get("type") != "string":
        return False
    if not set(schema) <= {"type", "description"}:
        return False
    description = schema.get("description")
    return description is None or (
        type(description) is str and len(description.encode("utf-8")) <= 1024
    )


def validate_host_deepwiki_repo(value: object) -> str:
    """Accept one bounded host-chosen `owner/repository`, never a model hint."""
    if (
        type(value) is not str or len(value) > 201
        or _REPO.fullmatch(value) is None
        or any(ord(char) < 33 or ord(char) == 127 for char in value)
    ):
        raise SchemaSourceError("bounded host-reviewed DeepWiki repository required")
    return value


def validate_deepwiki_outline(repo: str, payload: Any) -> str:
    """Check already-received structured MCP result and its host-selected identity."""
    if type(payload) is not dict or set(payload) != {"result"}:
        raise NonRetryableInvocationError("DeepWiki outline projection is invalid")
    outline = payload["result"]
    if (
        type(outline) is not str
        or not 20 <= len(outline.encode("utf-8")) <= _MAX_OUTLINE_BYTES
    ):
        raise NonRetryableInvocationError("DeepWiki outline content is invalid")
    lines = outline.splitlines()
    if (
        not lines or lines[0].strip() != f"Available pages for {repo}:"
        or sum(bool(_PAGE.fullmatch(line)) for line in lines[1:]) < 2
    ):
        raise NonRetryableInvocationError("DeepWiki outline source identity is invalid")
    return outline


@dataclass(frozen=True, slots=True)
class DeepWikiPaperSourceProbe:
    """Read-only unapproved live MCP schema snapshot; no operation executed."""

    source_fingerprint: str
    url: str
    available_endpoints: tuple[str, ...]
    output_fields: tuple[str, ...]


async def _discover(
    *,
    client_factory: MCPClientFactory | None,
    network_policy: NetworkPolicy,
) -> ToolSpec:
    return await inspect_mcp_url(
        DEEPWIKI_MCP_URL, server_name="deepwiki",
        client_factory=client_factory, network_policy=network_policy,
        timeout=20.0,
    )


def _source_snapshot_fingerprint(discovered: ToolSpec) -> str:
    """Pin adapter-visible MCP metadata *and* schemas, not ToolSpec.fingerprint alone.

    The generic ToolSpec fingerprint intentionally excludes endpoint metadata,
    including untrusted MCP annotations. A DeepWiki-specific review is more
    conservative: any inspected adapter-visible annotation drift invalidates
    the separate host receipt, without treating annotations as authority.
    """
    manifest = json.dumps(
        discovered.model_dump(mode="json"),
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(manifest).hexdigest()


async def inspect_deepwiki_paper_source(
    *,
    client_factory: MCPClientFactory | None = None,
    network_policy: NetworkPolicy | None = None,
) -> DeepWikiPaperSourceProbe:
    """Live schema discovery only; the caller must review its fingerprint."""
    discovered = await _discover(
        client_factory=client_factory,
        network_policy=network_policy or NetworkPolicy.public_only(),
    )
    selected = next(
        (ep for ep in discovered.endpoints if ep.name == "read_wiki_structure"),
        None,
    )
    return DeepWikiPaperSourceProbe(
        source_fingerprint=_source_snapshot_fingerprint(discovered),
        url=DEEPWIKI_MCP_URL,
        available_endpoints=tuple(ep.name for ep in discovered.endpoints),
        output_fields=tuple(field.name for field in selected.output_fields)
        if selected is not None else (),
    )


class DeepWikiPaperNativeInvoker:
    """Identity guard around the unchanged source-owned native MCP invoker."""

    def __init__(self, native_invoker: MCPRemoteInvoker) -> None:
        self._native_invoker = native_invoker

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        if endpoint != "read_wiki_structure" or set(arguments) != {"repoName"}:
            raise NonRetryableInvocationError("DeepWiki reviewed operation is invalid")
        repo = validate_host_deepwiki_repo(arguments["repoName"])
        source = await self._native_invoker(endpoint, arguments)
        validate_deepwiki_outline(repo, source)
        return source


async def register_reviewed_deepwiki_paper_source(
    router: SchemaRouter,
    *,
    expected_source_fingerprint: str,
    expected_url: str,
    license: str,
    reviewed_by: str,
    client_factory: MCPClientFactory | None = None,
) -> ToolSpec:
    """Narrow an EXACT host-approved remote discovery to one native operation.

    `reviewed_by` is provenance supplied by the caller, not a signature.
    The host must examine `probe` separately before this call. A source's
    readOnlyHint/description do not authorize anything by themselves.
    """
    if expected_url != DEEPWIKI_MCP_URL:
        raise SchemaSourceError("DeepWiki host-reviewed source URL mismatch")
    if license != DEEPWIKI_RESEARCH_LICENSE:
        raise SchemaSourceError("DeepWiki unverified research license label required")
    if type(reviewed_by) is not str or not 1 <= len(reviewed_by) <= 160:
        raise SchemaSourceError("DeepWiki host reviewer provenance required")
    discovered = await _discover(
        client_factory=client_factory,
        network_policy=router.loader.network_policy,
    )
    if (
        type(expected_source_fingerprint) is not str
        or _source_snapshot_fingerprint(discovered) != expected_source_fingerprint
    ):
        raise SchemaSourceError("DeepWiki source fingerprint differs from host approval")
    endpoint = next(
        (ep for ep in discovered.endpoints if ep.name == "read_wiki_structure"),
        None,
    )
    if (
        endpoint is None or len(endpoint.parameters) != 1
        or endpoint.parameters[0].name != "repoName"
        or endpoint.parameters[0].required is not True
        or endpoint.parameters[0].location != "argument"
        or not _reviewed_repo_parameter_schema(endpoint.parameters[0].json_schema)
        or not set(endpoint.input_schema) <= {
            "type", "properties", "required", "additionalProperties",
        }
        or endpoint.input_schema.get("type") != "object"
        or endpoint.input_schema.get("properties")
        != {"repoName": endpoint.parameters[0].json_schema}
        or endpoint.input_schema.get("required") != ["repoName"]
        or endpoint.input_schema.get("additionalProperties", False) is not False
        or len(endpoint.output_fields) != 1
        or endpoint.output_fields[0].name != "result"
        or endpoint.output_fields[0].json_schema != {"type": "string"}
        or endpoint.output_fields[0].identifier is not False
        or not set(endpoint.output_schema) <= {
            "type", "properties", "required", "x-fastmcp-wrap-result",
        }
        or endpoint.output_schema.get("x-fastmcp-wrap-result", True) is not True
        or endpoint.output_schema.get("type") != "object"
        or endpoint.output_schema.get("properties")
        != {"result": {"type": "string"}}
        or endpoint.output_schema.get("required") != ["result"]
        or endpoint.metadata.get("remote_name") != "read_wiki_structure"
    ):
        raise SchemaSourceError("DeepWiki source typed contract is not approvable")

    reviewed = discovered.model_copy(deep=True)
    reviewed.endpoints = [endpoint.model_copy(deep=True)]
    reviewed.source_type = DEEPWIKI_SOURCE_TYPE
    reviewed.license = license
    reviewed_endpoint = reviewed.endpoint("read_wiki_structure")
    # The actual MCP provider attaches a human description to the scalar
    # repoName input. A host may remove that nonvalidation annotation after
    # pinning the full source fingerprint, but never weaken pattern/enum/
    # minLength/format or any other provider-owned validation constraint.
    reviewed_endpoint.parameters[0].json_schema = {"type": "string"}
    reviewed_endpoint.input_schema = {
        "type": "object", "properties": {"repoName": {"type": "string"}},
        "required": ["repoName"], "additionalProperties": False,
    }
    reviewed_endpoint.read_only = True
    reviewed_endpoint.destructive = False
    reviewed.metadata["paper_mcp_review"] = {
        "source_tool_fingerprint": discovered.fingerprint,
        "source_snapshot_fingerprint": expected_source_fingerprint,
        "source_url": DEEPWIKI_MCP_URL,
        "source_endpoint_fingerprint": endpoint.fingerprint,
        "reviewed_by": reviewed_by,
    }
    attestation = HostSemanticAttestation(
        expected_tool_key=reviewed.key,
        expected_tool_fingerprint=reviewed.fingerprint,
        source_type=DEEPWIKI_SOURCE_TYPE,
        license=license,
        reviewed_by=reviewed_by,
        mappings=(
            HostSemanticMapping(
                endpoint_name="read_wiki_structure",
                expected_endpoint_fingerprint=reviewed_endpoint.fingerprint,
                member_kind="output_field", member_name="result",
                semantic_id="wiki.outline",
            ),
            HostSemanticMapping(
                endpoint_name="read_wiki_structure",
                expected_endpoint_fingerprint=reviewed_endpoint.fingerprint,
                member_kind="input_parameter", member_name="repoName",
                semantic_id="wiki.repository_id",
            ),
        ),
    )
    approved = apply_host_semantic_attestation(reviewed, attestation=attestation)
    remote = MCPRemoteInvoker(
        DEEPWIKI_MCP_URL, client_factory=client_factory,
        network_policy=router.loader.network_policy,
        timeout=20.0,
    )
    router.add_bound_tool(approved, DeepWikiPaperNativeInvoker(remote), replace=False)
    return approved
