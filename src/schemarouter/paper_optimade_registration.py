"""Opt-in host-reviewed OPTIMADE discovery → registered native paper tool.

Unlike ``add_url``, this path requires a separately pinned discovery schema
fingerprint *before* registering the tool. No model or remote source may
attest its own semantics, source license, or execution authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .adapters import AdapterContext, OPTIMADESourceAdapter, review_optimade_paper_tool
from .adapters.optimade import OPTIMADERemoteInvoker
from .errors import SchemaSourceError
from .models import ToolSpec, UnitNormalizationSpec
from .network_policy import NetworkPolicy

if TYPE_CHECKING:
    from .runtime import SchemaRouter


async def discover_optimade_paper_source(
    *, url: str, name: str, http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
) -> tuple[ToolSpec, OPTIMADERemoteInvoker]:
    """Discover a source, without review/registration; keep the native invoker.

    Intended for a trusted host's *separate* fingerprint inspection phase.
    The returned invoker is opaque and has no authorization on its own.
    """
    policy = network_policy or NetworkPolicy.public_only()
    source = await OPTIMADESourceAdapter().load(AdapterContext(
        url=url, name=name, http_client=http_client, network_policy=policy,
    ))
    if source is None or not isinstance(source.invoker, OPTIMADERemoteInvoker):
        raise SchemaSourceError("OPTIMADE source was not discoverable or invokable")
    return source.tool, source.invoker


async def register_reviewed_optimade_paper_source(
    router: SchemaRouter,
    *,
    url: str,
    name: str,
    expected_fingerprint: str,
    expected_versioned_base_url: str,
    license: str,
    field_semantic_ids: dict[str, str],
    identifier_semantic_id: str,
    http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
    reviewed_unit_normalizations: dict[str, UnitNormalizationSpec] | None = None,
    expected_source_units: dict[str, str] | None = None,
    reviewed_nonnull_string_fields: tuple[str, ...] = (),
) -> ToolSpec:
    """Publish the reviewed contract bound to its *original* discovery invoker.

    ``expected_fingerprint`` must be a previously reviewed **unreviewed**
    discovery fingerprint, not a value silently learned in this same call.
    Existing registrations cannot be replaced via this entrypoint.
    """
    if not expected_fingerprint or not isinstance(expected_fingerprint, str):
        raise SchemaSourceError("host-reviewed source fingerprint is required")
    tool, invoker = await discover_optimade_paper_source(
        url=url, name=name, http_client=http_client, network_policy=network_policy,
    )
    if tool.fingerprint != expected_fingerprint:
        raise SchemaSourceError("OPTIMADE source discovery fingerprint changed")
    # Identity, endpoint and source-field contracts are checked by the
    # existing original host-reviewer; the transport remains the discovered
    # invoker and is not substituted or supplied by the model.
    reviewed = review_optimade_paper_tool(
        tool,
        expected_fingerprint=expected_fingerprint,
        expected_versioned_base_url=expected_versioned_base_url,
        entry_type="structures",
        license=license,
        field_semantic_ids=field_semantic_ids,
        reviewed_unit_normalizations=reviewed_unit_normalizations,
        expected_source_units=expected_source_units,
        identifier_semantic_id=identifier_semantic_id,
        reviewed_nonnull_string_fields=reviewed_nonnull_string_fields,
    )
    router.add_bound_tool(reviewed, invoker, replace=False)
    return reviewed
