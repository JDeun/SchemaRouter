from __future__ import annotations

from .errors import BindingDriftError
from .executor import BoundEndpointInvoker, RegistryExecutor
from .models import ToolSpec
from .registry import (
    ToolRegistry,
    replace_if_current,
    unregister_if_current,
)


def publish_bound_tool(
    registry: ToolRegistry,
    executor: RegistryExecutor,
    tool: ToolSpec,
    invoker: BoundEndpointInvoker,
    *,
    replace: bool = False,
    expected_fingerprint: str | None = None,
    expected_version: int | None = None,
    offload_sync: bool = False,
) -> str:
    """Publish one registry contract and trusted binding as one logical transition.

    The registry remains the source of truth for the executable contract. If binding
    fails after a registry write, this helper restores the previous contract and binding
    when this transition still owns the current tool fingerprint. Concurrent same-key
    drift is never overwritten during rollback.

    expected_fingerprint and expected_version select compare-and-swap replacement
    semantics for callers that already reviewed a specific registry snapshot.
    """

    if (expected_fingerprint is None) != (expected_version is None):
        raise ValueError(
            "expected_fingerprint and expected_version must be provided together"
        )

    tool_key = tool.key
    captured_version = registry.version
    try:
        previous = registry.get(tool_key)
    except KeyError:
        previous = None

    previous_binding = (
        executor._bound_binding_for_contract(tool_key, previous.fingerprint)
        if previous is not None
        else None
    )

    if expected_fingerprint is not None:
        if previous is None:
            raise KeyError(tool_key)
        key = replace_if_current(
            registry,
            tool,
            expected_fingerprint=expected_fingerprint,
            expected_version=expected_version,
        )
    elif replace and previous is not None:
        key = replace_if_current(
            registry,
            tool,
            expected_fingerprint=previous.fingerprint,
            expected_version=captured_version,
        )
    else:
        key = registry.register(tool)

    try:
        executor.bind(
            key,
            invoker,
            expected_fingerprint=tool.fingerprint,
            offload_sync=offload_sync,
        )
        return key
    except Exception as bind_exc:
        try:
            rollback_version = registry.version
            current = registry.get(key)
            if current.fingerprint != tool.fingerprint:
                raise BindingDriftError(
                    f"bound publication for {key!r} failed and the registered "
                    "contract changed concurrently before rollback"
                )

            if previous is None:
                unregister_if_current(
                    registry,
                    key,
                    expected_fingerprint=tool.fingerprint,
                    expected_version=rollback_version,
                )
            else:
                replace_if_current(
                    registry,
                    previous,
                    expected_fingerprint=tool.fingerprint,
                    expected_version=rollback_version,
                )
        except Exception as rollback_exc:
            executor.unbind(key)
            raise BindingDriftError(
                f"bound publication for {key!r} failed and registry rollback "
                "could not be completed safely"
            ) from rollback_exc

        if previous_binding is None:
            executor.unbind(key)
        else:
            previous_invoker, previous_offload_sync = previous_binding
            try:
                executor.bind(
                    key,
                    previous_invoker,
                    expected_fingerprint=previous.fingerprint,
                    offload_sync=previous_offload_sync,
                )
            except Exception as restore_exc:
                executor.unbind(key)
                raise BindingDriftError(
                    f"bound publication for {key!r} restored the previous contract "
                    "but could not restore its trusted binding"
                ) from restore_exc
        raise bind_exc
