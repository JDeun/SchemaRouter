"""Opt-in, reviewed Europe PMC original-paper native HTTP/JSON DOI source.

The source schema is a curated *local* declaration, not a remotely signed
schema. Independent review of its exact fingerprint, origin, field meanings
and license label is required before a host registers an executable route.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .adapters.http_json import build_http_json_invoker, prepare_http_json_tool
from .errors import NonRetryableInvocationError, SchemaSourceError
from .models import ToolCall, ToolSpec
from .paper_crossref_registration import validate_host_crossref_doi
from .provider_profiles import built_in_provider_profile_registry
from .semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter

EUROPEPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUROPEPMC_LICENSE = "source-license-unverified-research-only"
EUROPEPMC_SOURCE_TYPE = "europepmc"
# This E1 runner uses the unquoted Europe PMC search grammar. Restrict to a
# conservative literal DOI subset, rather than letting `*`, `?`, quotes,
# brackets or boolean/query operators turn a host DOI into a search expression.
_EUROPEPMC_LITERAL_DOI = re.compile(r"10\.[0-9]{4,9}/[A-Za-z0-9._/-]{1,450}\Z", re.ASCII)
EUROPEPMC_FIELD_SEMANTICS = {
    "hitCount": "paper.search_hit_count",
    "resultList.result.*.doi": "paper.doi",
    "resultList.result.*.id": "paper.europepmc_record_id",
}


@dataclass(frozen=True, slots=True)
class EuropePMCPaperSourceProbe:
    source_fingerprint: str
    base_url: str
    available_fields: tuple[str, ...]


def _curated_source() -> tuple[ToolSpec, str]:
    profile = built_in_provider_profile_registry().get("europepmc")
    candidates = [method for method in profile.methods if method.method_id == "rest"]
    if (
        len(candidates) != 1
        or candidates[0].kind != "http_json"
        or candidates[0].url != EUROPEPMC_BASE_URL
        or candidates[0].tool is None
    ):
        raise SchemaSourceError("Europe PMC curated source unavailable")
    return candidates[0].tool.model_copy(deep=True), candidates[0].url


def inspect_europepmc_paper_source() -> EuropePMCPaperSourceProbe:
    """No HTTP request and *no* implicit authorization to execute."""
    tool, base_url = _curated_source()
    return EuropePMCPaperSourceProbe(
        source_fingerprint=tool.fingerprint,
        base_url=base_url,
        available_fields=tuple(field.name for field in tool.endpoint("search_doi").output_fields),
    )


def validate_host_europepmc_query(query: object) -> str:
    """Only a host-selected DOI may become a Europe PMC `DOI:` search."""
    if type(query) is not str or not query.startswith("DOI:"):
        raise SchemaSourceError("a host-approved DOI search query is required")
    doi = validate_host_crossref_doi(query[len("DOI:"):])
    if _EUROPEPMC_LITERAL_DOI.fullmatch(doi) is None:
        raise SchemaSourceError("a literal host-approved Europe PMC DOI is required")
    return doi


class EuropePMCPaperNativeInvoker:
    """Validate the *source row identity* before ordinary projection occurs."""

    def __init__(self, invoker: Any) -> None:
        self._invoker = invoker

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        return await self.invoke_call(ToolCall(
            tool=self._invoker.tool.key,
            endpoint=endpoint,
            arguments=arguments,
            fields=[],
            schema_fingerprint=self._invoker.tool.endpoint(endpoint).fingerprint,
        ))

    async def invoke_call(self, call: ToolCall) -> Any:
        if call.endpoint != "search_doi":
            raise NonRetryableInvocationError("Europe PMC endpoint is not reviewed")
        if set(call.arguments) != {"query", "format", "pageSize"}:
            raise NonRetryableInvocationError("Europe PMC host arguments incomplete")
        try:
            doi = validate_host_europepmc_query(call.arguments["query"])
        except SchemaSourceError as exc:
            raise NonRetryableInvocationError("Europe PMC DOI query invalid") from exc
        if call.arguments["format"] != "json" or (
            type(call.arguments["pageSize"]) is not int
            or call.arguments["pageSize"] != 1
        ):
            raise NonRetryableInvocationError("Europe PMC JSON singleton query required")

        response = await self._invoker.invoke_call(call)
        if not isinstance(response, dict):
            raise NonRetryableInvocationError("Europe PMC JSON response invalid")
        count = response.get("hitCount")
        result_list = response.get("resultList")
        rows = result_list.get("result") if isinstance(result_list, dict) else None
        if type(count) is not int or count < 1 or not isinstance(rows, list) or len(rows) != 1:
            raise NonRetryableInvocationError("Europe PMC DOI result missing or malformed")
        row = rows[0]
        if not isinstance(row, dict):
            raise NonRetryableInvocationError("Europe PMC DOI result must be an object")
        source_doi, source_id = row.get("doi"), row.get("id")
        if (
            type(source_doi) is not str
            or source_doi.casefold() != doi.casefold()
            or type(source_id) is not str
            or not source_id.strip()
            or len(source_id) > 160
            or any(ord(char) < 32 or ord(char) == 127 for char in source_id)
        ):
            raise NonRetryableInvocationError("Europe PMC source DOI identity mismatch")
        return response


def register_reviewed_europepmc_paper_source(
    router: SchemaRouter,
    *,
    expected_source_fingerprint: str,
    expected_base_url: str,
    license: str,
    reviewed_by: str,
) -> ToolSpec:
    """Register one attested local source contract, without executor permission."""
    tool, base_url = _curated_source()
    if (
        type(expected_source_fingerprint) is not str
        or expected_source_fingerprint != tool.fingerprint
    ):
        raise SchemaSourceError("Europe PMC source fingerprint differs from approval")
    if type(expected_base_url) is not str or expected_base_url != base_url:
        raise SchemaSourceError("Europe PMC source origin differs from approval")

    endpoint = tool.endpoint("search_doi")
    fields = {field.name: field for field in endpoint.output_fields}
    expected_params = {
        "query": {"type": "string"},
        "format": {"type": "string"},
        "pageSize": {"type": "integer"},
    }
    result_schema = (
        endpoint.output_schema.get("properties", {})
        .get("resultList", {}).get("properties", {})
        .get("result", {})
    )
    if (
        tool.key != "europepmc"
        or len(tool.endpoints) != 1
        or endpoint.method != "GET"
        or endpoint.path != "/search"
        or endpoint.read_only is not True
        or endpoint.destructive is not False
        or len(endpoint.parameters) != 3
        or {p.name: p.json_schema for p in endpoint.parameters} != expected_params
        or any(p.location != "query" or p.required is not True for p in endpoint.parameters)
        or endpoint.input_schema != {
            "type": "object", "properties": expected_params,
            "required": ["query", "format", "pageSize"],
            "additionalProperties": False,
        }
        or set(fields) != set(EUROPEPMC_FIELD_SEMANTICS)
        or any(fields[name].identifier for name in fields)
        or fields["hitCount"].json_schema != {"type": "integer"}
        or fields["hitCount"].projection_path != ("hitCount",)
        or endpoint.output_schema.get("properties", {}).get("hitCount") != {"type": "integer"}
        or result_schema.get("type") != "array"
        or result_schema.get("items", {}).get("properties", {}) != {
            "doi": {"type": "string"}, "id": {"type": "string"},
        }
        or any(
            fields[name].json_schema != {"type": "string"}
            or fields[name].projection_path != tuple(name.split("."))
            or fields[name].result_projection_path != tuple(name.split("."))
            for name in ("resultList.result.*.doi", "resultList.result.*.id")
        )
    ):
        raise SchemaSourceError("Europe PMC source typed contract is not approvable")

    reviewed = tool.model_copy(deep=True)
    reviewed.source_type = EUROPEPMC_SOURCE_TYPE
    reviewed.license = license
    prepared = prepare_http_json_tool(
        reviewed, base_url=base_url, provider=EUROPEPMC_SOURCE_TYPE,
    )
    p_endpoint = prepared.endpoint("search_doi")
    attestation = HostSemanticAttestation(
        expected_tool_key=prepared.key,
        expected_tool_fingerprint=prepared.fingerprint,
        source_type=EUROPEPMC_SOURCE_TYPE,
        license=license,
        reviewed_by=reviewed_by,
        mappings=tuple(
            HostSemanticMapping(
                endpoint_name="search_doi",
                expected_endpoint_fingerprint=p_endpoint.fingerprint,
                member_kind="output_field",
                member_name=name,
                semantic_id=semantic,
            )
            for name, semantic in EUROPEPMC_FIELD_SEMANTICS.items()
        ),
    )
    approved = apply_host_semantic_attestation(prepared, attestation=attestation)
    invoker = build_http_json_invoker(
        approved,
        base_url=base_url,
        http_client=router.loader.http_client,
        network_policy=router.loader.network_policy,
    )
    router.add_bound_tool(approved, EuropePMCPaperNativeInvoker(invoker), replace=False)
    return approved
