from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..errors import PolicyViolationError, StaleExportedToolError
from ..models import EndpointSpec, ToolSpec
from ..runs import RunConfig

if TYPE_CHECKING:
    from ..runtime import SchemaRouter


@dataclass(frozen=True)
class _ExportedEndpointContract:
    tool_fingerprint: str
    endpoint_fingerprint: str
    visible_endpoint_fingerprint: str


def _coerce_export_run_config(
    config: RunConfig | dict[str, Any] | None,
) -> RunConfig:
    if config is None:
        run_config = RunConfig()
    elif isinstance(config, RunConfig):
        run_config = config
    else:
        run_config = RunConfig.model_validate(config)
    if run_config.run_id is not None:
        return run_config
    return run_config.model_copy(update={"run_id": uuid4().hex})


def _authorized_endpoint_view(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    run_config: RunConfig,
    *,
    audit_export: bool = True,
) -> tuple[ToolSpec, EndpointSpec, EndpointSpec]:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(endpoint_name)
    policy = router.authorization_policy
    if policy is None:
        return tool, endpoint, endpoint

    principal = run_config.principal
    if principal is None:
        if audit_export:
            router._audit_export_authorization(
                None,
                tool,
                endpoint,
                run_id=run_config.run_id,
                principal_audit_id=run_config.principal_audit_id,
            )
        raise PolicyViolationError(
            "principal context is required when authorization_policy is configured"
        )

    authorized = (
        router._audit_export_authorization(
            principal,
            tool,
            endpoint,
            run_id=run_config.run_id,
            principal_audit_id=run_config.principal_audit_id,
        )
        if audit_export
        else policy.visible(principal, tool, endpoint)
    )
    if not authorized:
        raise PolicyViolationError("authorization denied for requested capability")
    projected = router._data_scope_endpoint_view(principal, tool, endpoint)
    if projected is None:
        raise PolicyViolationError("authorization denied for requested data scope")
    return tool, endpoint, projected


def _capture_exported_endpoint_contract(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    visible_endpoint: EndpointSpec,
) -> _ExportedEndpointContract:
    return _ExportedEndpointContract(
        tool_fingerprint=tool.fingerprint,
        endpoint_fingerprint=endpoint.fingerprint,
        visible_endpoint_fingerprint=visible_endpoint.fingerprint,
    )


def _resolve_live_exported_endpoint(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    run_config: RunConfig,
    expected: _ExportedEndpointContract,
) -> tuple[ToolSpec, EndpointSpec, EndpointSpec]:
    try:
        tool, endpoint, visible_endpoint = _authorized_endpoint_view(
            router,
            tool_key,
            endpoint_name,
            run_config,
        )
    except KeyError as exc:
        raise StaleExportedToolError(
            f"exported framework tool {tool_key}.{endpoint_name} is stale because "
            "the live endpoint no longer exists; re-export the framework tool"
        ) from exc
    except PolicyViolationError as exc:
        raise StaleExportedToolError(
            f"exported framework tool {tool_key}.{endpoint_name} is stale because "
            "the live authorization view no longer permits the exported contract; "
            "re-export the framework tool"
        ) from exc

    current = _capture_exported_endpoint_contract(
        tool,
        endpoint,
        visible_endpoint,
    )
    if current != expected:
        raise StaleExportedToolError(
            f"exported framework tool {tool_key}.{endpoint_name} is stale because "
            "its live authorized contract changed; re-export the framework tool"
        )
    return tool, endpoint, visible_endpoint
