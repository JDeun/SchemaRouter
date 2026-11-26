"""Historical lexical comparison fixture; not used by native-only benchmarks."""
from __future__ import annotations

from schemarouter import AuthorizationPolicy, AuthorizationRule, SchemaRouter
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _populate_synthetic_router


def legacy_synthetic_router(noise_routes: int) -> SchemaRouter:
    router = SchemaRouter(_legacy_routing=True, authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    return _populate_synthetic_router(router, noise_routes)
