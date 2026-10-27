"""Opt-in Crossref typed A5 source review over the native HTTP/JSON adapter.

This pins a *curated local manifest*, not a remotely discovered schema: the
provider's runtime contents and its license are not independently attested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .adapters.http_json import build_http_json_invoker, prepare_http_json_tool
from .errors import NonRetryableInvocationError, SchemaSourceError
from .models import ToolCall, ToolSpec
from .provider_profiles import built_in_provider_profile_registry
from .semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter

CROSSREF_BASE_URL = "https://api.crossref.org/v1"
CROSSREF_SOURCE_TYPE = "crossref"
_DOI = re.compile(r"10\.[0-9]{4,9}/[^\s]{1,450}\Z", flags=re.ASCII)


def validate_host_crossref_doi(doi: object) -> str:
    """Bound a trusted host's DOI before any outbound request; never infer it."""
    if (
        type(doi) is not str
        or not 7 <= len(doi) <= 512
        or doi != doi.strip()
        or not doi.isascii()
        or _DOI.fullmatch(doi) is None
        or any(ord(char) < 33 or ord(char) == 127 for char in doi)
    ):
        raise SchemaSourceError("a valid, bounded host-reviewed Crossref DOI is required")
    return doi


@dataclass(frozen=True, slots=True)
class CrossrefPaperSourceProbe:
    """Unreviewed local source declaration for a *separate* host approval."""

    source_fingerprint: str
    base_url: str
    available_fields: tuple[str, ...]


def _curated_crossref_source() -> tuple[ToolSpec, str]:
    profile = built_in_provider_profile_registry().get("crossref")
    candidates = [method for method in profile.methods if method.method_id == "rest"]
    if (
        len(candidates) != 1
        or candidates[0].url != CROSSREF_BASE_URL
        or candidates[0].kind != "http_json"
        or candidates[0].tool is None
    ):
        raise SchemaSourceError("Crossref curated provider source is unavailable")
    return candidates[0].tool.model_copy(deep=True), candidates[0].url


def inspect_crossref_paper_source() -> CrossrefPaperSourceProbe:
    """Inspect the built-in manifest without contacting Crossref or approving it."""
    tool, base_url = _curated_crossref_source()
    return CrossrefPaperSourceProbe(
        source_fingerprint=tool.fingerprint,
        base_url=base_url,
        available_fields=tuple(field.name for field in tool.endpoint("get_work").output_fields),
    )


class CrossrefPaperNativeInvoker:
    """Source-specific identity boundary around the existing native invoker."""

    def __init__(self, invoker: Any) -> None:
        self._invoker = invoker

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        return await self.invoke_call(ToolCall(
            tool=self._invoker.tool.key, endpoint=endpoint,
            arguments=arguments, fields=[],
            schema_fingerprint=self._invoker.tool.endpoint(endpoint).fingerprint,
        ))

    async def invoke_call(self, call: ToolCall) -> Any:
        if call.endpoint == "get_work":
            doi = validate_host_crossref_doi(call.arguments.get("doi"))
        else:
            doi = None
        response = await self._invoker.invoke_call(call)
        if doi is None:
            return response
        if not isinstance(response, dict) or response.get("status") != "ok":
            raise NonRetryableInvocationError("Crossref source status is not ok")
        if response.get("message-type") != "work":
            raise NonRetryableInvocationError(
                "Crossref source message-type is not a singleton work"
            )
        message = response.get("message")
        if not isinstance(message, dict):
            raise NonRetryableInvocationError("Crossref source message must be an object")
        source_doi = message.get("DOI")
        if (
            type(source_doi) is not str
            or source_doi.casefold() != doi.casefold()
        ):
            raise NonRetryableInvocationError("Crossref source DOI identity mismatch")
        publisher = message.get("publisher")
        if (
            type(publisher) is not str
            or not 1 <= len(publisher.strip()) <= 300
            or any(ord(char) < 32 or ord(char) == 127 for char in publisher)
        ):
            raise NonRetryableInvocationError("Crossref source publisher missing or invalid")
        return response


def register_reviewed_crossref_paper_source(
    router: SchemaRouter,
    *,
    expected_source_fingerprint: str,
    expected_base_url: str,
    license: str,
    reviewed_by: str,
) -> ToolSpec:
    """Publish one reviewed native Crossref source without granting execution rights.

    Caller must first inspect and independently review the source fingerprint,
    URL, semantic field identities and license label. No `replace` is allowed.
    """
    tool, base_url = _curated_crossref_source()
    if (
        type(expected_source_fingerprint) is not str
        or tool.fingerprint != expected_source_fingerprint
    ):
        raise SchemaSourceError("Crossref source fingerprint differs from host approval")
    if type(expected_base_url) is not str or expected_base_url != base_url:
        raise SchemaSourceError("Crossref source base URL differs from host approval")
    endpoint = tool.endpoint("get_work")
    fields = {field.name: field for field in endpoint.output_fields}
    closed_input_schema = {
        "type": "object",
        "properties": {"doi": {"type": "string"}},
        "required": ["doi"],
        "additionalProperties": False,
    }
    output_properties = endpoint.output_schema.get("properties", {})
    message_schema = (
        output_properties.get("message")
        if isinstance(output_properties, dict)
        else None
    )
    message_properties = (
        message_schema.get("properties", {})
        if isinstance(message_schema, dict)
        else {}
    )
    if (
        endpoint.method != "GET"
        or endpoint.path != "/works/{doi}"
        or endpoint.read_only is not True
        or endpoint.destructive is not False
        or not {"message.DOI", "message.publisher"} <= fields.keys()
        or fields["message.DOI"].json_schema != {"type": "string"}
        or fields["message.DOI"].identifier is not True
        or fields["message.DOI"].projection_path != ("message", "DOI")
        or fields["message.DOI"].result_projection_path != ("message.DOI",)
        or fields["message.publisher"].json_schema != {"type": "string"}
        or fields["message.publisher"].projection_path != ("message", "publisher")
        or fields["message.publisher"].result_projection_path
        != ("message.publisher",)
        or message_properties.get("DOI") != {"type": "string"}
        or message_properties.get("publisher") != {"type": "string"}
        or endpoint.input_schema != closed_input_schema
        or len(endpoint.parameters) != 1
        or endpoint.parameters[0].name != "doi"
        or endpoint.parameters[0].location != "path"
        or endpoint.parameters[0].json_schema != {"type": "string"}
        or endpoint.parameters[0].required is not True
    ):
        raise SchemaSourceError("Crossref source typed contract is not approvable")

    reviewed = tool.model_copy(deep=True)
    reviewed.source_type = CROSSREF_SOURCE_TYPE
    reviewed.license = license
    prepared = prepare_http_json_tool(reviewed, base_url=base_url, provider="crossref")
    prepared_endpoint = prepared.endpoint("get_work")
    attestation = HostSemanticAttestation(
        expected_tool_key=prepared.key,
        expected_tool_fingerprint=prepared.fingerprint,
        source_type=CROSSREF_SOURCE_TYPE,
        license=license,
        reviewed_by=reviewed_by,
        mappings=(
            HostSemanticMapping(
                endpoint_name="get_work",
                expected_endpoint_fingerprint=prepared_endpoint.fingerprint,
                member_kind="output_field",
                member_name="message.DOI",
                semantic_id="paper.doi",
            ),
            HostSemanticMapping(
                endpoint_name="get_work",
                expected_endpoint_fingerprint=prepared_endpoint.fingerprint,
                member_kind="output_field",
                member_name="message.publisher",
                semantic_id="paper.publisher",
            ),
            HostSemanticMapping(
                endpoint_name="get_work",
                expected_endpoint_fingerprint=prepared_endpoint.fingerprint,
                member_kind="input_parameter",
                member_name="doi",
                semantic_id="paper.doi",
            ),
        ),
    )
    approved = apply_host_semantic_attestation(prepared, attestation=attestation)
    invoker = build_http_json_invoker(
        approved,
        base_url=base_url,
        http_client=router.loader.http_client,
        network_policy=router.loader.network_policy,
    )
    router.add_bound_tool(approved, CrossrefPaperNativeInvoker(invoker), replace=False)
    return approved
