# #1228 — Native ServiceNow readonly E5 vs lexical K3/K5 (visible DEV only)

## Motivation

Current pinned publisher Xerrion native readonly 12-tool development comparison has **20
supported and 4 unsupported** previously visible, same-author English queries. Current
SchemaRouter K5 obtains 17/20 original required tools (85% supported macro recall),
and returns a **nonempty shortlist for all four negatives**. This is an observed
developer-only limitation, not an independent user or agent test. The interleaved
true local request-p95 instrumentation is separately archived in PR #1460; it is
not valid to substitute that preselection-only p95 for an agent SLA.

Source locks remain unchanged:
- Upstream original MCP publisher commit:
  `5bcb83b29ab5b30aee07cabaa8df974881c47126`
- Actual source-native readonly tool canonical SHA-256:
  `006045422791939ff603420080e2f759de38a19329eeb0c1b80e264ab4897940`
- Original 24 cases from
  `benchmarks/external-validation-servicenow-platform-mcp-dev-v1`.
- Real CPU multilingual E5-small checkpoint:
  `fd1525a9fd15316a2d503bf26ab031a61d056e98`.

## Strictly limited prospective treatment (preregistered before measurement)

The direct local source package and per-case original required tool/parameter
labels are **not changed**. First obtain complete source-native `SchemaRouter.retrieve
(k=12)` candidates; require every original native tool ID exactly once. The
pinned E5 embedder sees only candidate tool name and published descriptions,
plus the query; it does not see required tool labels, task IDs, expected
parameter names or hidden scorer outcomes. It may **only permute the same 12
native tools**, returning lexical and E5 candidate shortlists at K3 and K5.

Report five conditions: whole 12-tool static readonly, lexical K3, lexical K5,
real E5 K3 and real E5 K5. For each, retain raw original case ID, actual query,
full candidate rank, selected native IDs and canonical publisher schema bytes.
For **supported cases only**, report macro and micro required-tool recall,
and micro availability of originally declared required native input
parameters. Report *all four unsupported cases* with whether their shortlist
is nonempty — **this is not calibrated no-fit acceptance or actual unsafe
execution**. Preserve any regression and failed sample without relabeling.

Record local full-retrieval and E5 reranking elapsed ms per request, not an
end-to-end speed comparison to static tools, because **no LLM, host network,
ServiceNow tenant, downstream tool invocation, execution policy or agent
response exists in this experiment**. Record current source SHA, native digest,
manifest/case bytes, model revision, CPU and package versions; offline source
control tests must fail on foreign/duplicate/missing route, changed model
revision and malformed metric denominators.

The model is local CPU only, no API keys, paid provider or GPU. User input
language in these original 24 tasks is **English only**. Despite E5's
multilingual model architecture, this particular result **does not measure
Korean/Japanese ServiceNow requests** or multilingual transfer. Do not copy
translations into the previous task set and label them independent.

## Decision rule and release boundary

Use this as a **diagnostic** on previously disclosed DEV cases. No winner
promotion, model default switch, threshold tuning or fabricated confidence
intervals from these source/label-exposed results. If E5 improves K5 required
route/field recall, it creates only a prospective hypothesis for publisher-
reviewed, genuinely disjoint source-native tasks, original primary K and
runtime input constraints, and separate agent/host no-call evaluation. If it
fails, preserve negative evidence.

**#1228 and #1346 remain OPEN; v0.18.0 release candidate #1356 remains HOLD.**
Previously frozen #432/#424 outcomes must never be rewritten.
