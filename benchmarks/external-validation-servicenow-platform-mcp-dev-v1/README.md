# SchemaRouter × ServiceNow Platform MCP — development fixture v1

This package is the **development/protocol-review** implementation for the collaboration discussed in [Xerrion/servicenow-platform-mcp#192](https://github.com/Xerrion/servicenow-platform-mcp/issues/192).

It is **not held-out evidence**. The visible cases exist so both maintainers can review the task-to-tool mapping, required input fields, unsupported cases, serialization boundary, and timing procedure before a freeze.

## Fair primary comparison

Both conditions begin from the same upstream ServiceNow `readonly` package:

1. **static_readonly** — make every upstream `readonly` MCP tool contract model-visible;
2. **readonly_plus_schemarouter_preselection** — give SchemaRouter only that same captured `readonly` tool set and make the selected subset model-visible.

SchemaRouter must not add any tool that the upstream package did not expose. ServiceNow authorization, runtime policy, and execution behavior are outside the selection benchmark and remain unchanged.

## Upstream contract capture

The benchmark does not hand-author a substitute ServiceNow catalog. The capture script imports the pinned upstream checkout, creates its MCP server with safe dummy connection metadata, and records the result of `await mcp.list_tools()`. No ServiceNow credential, network request, or tool execution is needed to enumerate the registered schemas.

Pinned development reference:

- ServiceNow Platform MCP: `5bcb83b29ab5b30aee07cabaa8df974881c47126` (2.1.2)
- SchemaRouter: `da33d5a95f32984fee12692930d31fe0f4ee850a`
- Python: 3.12
- `MCP_TOOL_PACKAGE=readonly`
- `SERVICENOW_ENV=prod`

At this upstream revision, `readonly` contains 11 tool groups plus the always-registered `list_tool_packages`, for an expected 12 public MCP tools.

## Field metric

The native MCP contracts are authoritative. The development scorer therefore measures **required top-level input-parameter recall** for each gold tool. It does not invent domain-level output fields when the upstream MCP schema does not expose them.

This distinction matters: a result may show useful tool-surface reduction without demonstrating per-domain-output-field projection. Any final report must preserve that limitation.

## Visible development cases

`cases.json` contains 20 supported cases across query, describe, record-read, choice, analysis, audit, investigation, code-search, Flow Designer, CMDB, and attachment surfaces, plus four unsupported/OOD cases. These are review fixtures, not hidden test data.

Unsupported cases are diagnostic. A system that always returns candidates must be reported as such; the harness does not synthesize an abstention threshold after seeing results.

## Exposure accounting

For both conditions, schema exposure is measured from the **same captured upstream MCP tool objects**, encoded as canonical JSON:

- UTF-8
- `ensure_ascii=false`
- sorted object keys
- compact separators

This avoids comparing SchemaRouter's internal candidate representation against a different static serialization. The primary variable is which native contracts become model-visible.

## Planned commands

After installing the pinned upstream checkout:

```bash
python scripts/capture_servicenow_platform_mcp_tools.py \
  --out benchmarks/external-validation-servicenow-platform-mcp-dev-v1/servicenow-readonly-tools.json

python scripts/external_validation_servicenow_platform_mcp.py validate \
  --package-dir benchmarks/external-validation-servicenow-platform-mcp-dev-v1 \
  --snapshot benchmarks/external-validation-servicenow-platform-mcp-dev-v1/servicenow-readonly-tools.json
```

Development smoke results may be used to fix harness defects. Held-out scoring remains disabled until the protocol is reviewed and frozen with the upstream maintainer.

## Maintainer review requested

Before freeze, confirm:

- `readonly` is the correct primary package;
- the visible task → tool / required-input-field labels are semantically correct;
- `mcp.list_tools()` is the canonical package schema boundary;
- the negative cases do not misrepresent intended `readonly` behavior;
- the selection/timing and schema-byte boundaries are acceptable.

Negative or non-monotonic results remain publishable unchanged.


## Pinned source provenance and maintainer review worksheet

At upstream commit `5bcb83b29ab5b30aee07cabaa8df974881c47126`,
`pyproject.toml` declares **MIT** licensing, Python 3.12 or newer, and
`servicenow-platform-mcp==2.1.2`. The upstream `LICENSE` is MIT (copyright
2026 Lasse Nielsen). The study reads only the public, native MCP
`readonly` `tools/list` contracts; it neither bypasses instance ACLs nor
measures production authorization, access, endpoint output values, billed
tokens, or true task-success/agent latency.

`scripts/external_validation_servicenow_platform_mcp.py` verifies the
actual canonical SHA-256 of captured native tool objects against
`tools_sha256` **and separately against the manifest-pinned reference**
`006045422791939ff603420080e2f759de38a19329eeb0c1b80e264ab4897940`
(reproduced across two actual pinned-source CI captures). Consequently
simultaneously altering the captured contracts and their internal hash also
fails verification. This checks a known source snapshot, not independent
policy correctness. The scorer validates upstream package/version/environment, cardinality
and every proposed gold input field; rejects duplicate gold tool/field IDs;
and makes direct `score()` users pass the same source checks. A green test
indicates **mechanical source and scoring integrity**, not that a human
maintainer approved the semantic mapping.

A complete, *unscored* reviewer worksheet is written as
`artifacts/servicenow-platform-mcp-dev-smoke/maintainer-review-visible-dev.md`
in the PR's workflow artifact, alongside exact upstream schemas and the
already-public 24 synthetic tasks. It highlights the **existing** visible
`sn-dev-006`, `sn-dev-007`, and `sn-dev-015` tool-mapping questions without
changing their gold labels, ranking settings or Top-K. The upstream
maintainer was previously asked to review the protocol in
[Xerrion #192](https://github.com/Xerrion/servicenow-platform-mcp/issues/192).
Avoid sending a duplicate proposal while that answer is pending.

The existing development diagnostic and any failures are unchanged. No new
independently authored confirmation cases, externally endorsed field labels,
or prospective held-out scores are supplied by this PR.
