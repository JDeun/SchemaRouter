# Capability provenance and fallback lineage

Capability lineage records why a route was selected and, when fallback occurs, which route was actually used.

```python
from schemarouter import CapabilityLineageHop, build_capability_lineage

selected = CapabilityLineageHop(
    provider="materials-project",
    access_method="rest",
    route_id="mp.summary",
    capability_id="material.summary",
    schema_fingerprint="...",
    semantic_ids=("band_gap",),
)
lineage = build_capability_lineage(selected=selected)
```

Each lineage document receives a deterministic SHA-256 ID over its canonical machine-readable representation. A hop may contain provider, access method, route/capability ID, schema revision/fingerprint, relevant semantic IDs, and a structured health/fallback reason.

The model intentionally has no payload, argument-value, credential, or header fields. Hosts must also avoid constructing lineage for capabilities that were hidden by authorization or visibility policy. `inspect_capability_lineage()` returns a detached safe copy for logging, dashboards, or adapter-specific observability.

Lineage is not distributed tracing and does not execute or authorize anything. The host remains responsible for execution, policy, redaction, and trace correlation.
