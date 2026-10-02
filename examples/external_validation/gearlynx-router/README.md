# Gearlynx MCP router external validation

This fixture is derived from `drhelius/Gearlynx` at commit
`58c0fa0fa2abe1b0b7da885640b32bce4ff3677f`.

The upstream maintainer accepted the cross-benchmark in Gearlynx issue #105.
SchemaRouter is evaluated only as a candidate-selection layer. Gearlynx remains
authoritative for exact input schemas, validation, emulator state, and execution.

Run:

```bash
python scripts/external_validation_gearlynx.py --json-out benchmarks/results/gearlynx-e1-summary.json
```

Phase A requires no ROM and does not start the emulator. The frozen catalog
contains derived tool metadata (name/title/description/category/parameter names,
direct/routed classification, and input-schema source size) from the pinned
upstream source.

The benchmark compares Gearlynx's native case-insensitive AND-substring search
(max 20 results) with bounded SchemaRouter retrieval (max 3 disclosed names).
Unsupported cases are included. Each case records the source bytes of the exact
selected schemas for both retrieval paths. Required-field recall is explicitly
not reported in Phase A because the pinned Gearlynx metadata does not expose
normalized output-field labels; no field labels are inferred or imputed.

Results must be reported unchanged, including negative or non-monotonic findings.

A later live smoke may verify that selected routed tools still flow through
Gearlynx `get_tool_info` and `execute_tool`; it is intentionally outside the
core retrieval benchmark.
