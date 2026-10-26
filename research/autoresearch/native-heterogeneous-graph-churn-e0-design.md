# B1 E0 — nonempty mixed-source graph churn and exact source witnesses

**Scope: engineering evidence, not original publisher gold.** Canonical #1560,
Draft #1755, B1 500/5000 source benchmark. The 2026-10-26 direct mixed-source
journal audit checked a 500/5000 registered ToolSpec inventory but had **no
G5 source graph edges**. Its graph/full-build equality was therefore vacuous
for typed producer→consumer churn. This design closes that bounded E0 gap.

## Original-source fixtures and preregistered transitions

- Reuse the existing 500/5000 mixed OpenAPI/MCP/OPTIMADE/custom *ToolSpec*
  fixture. Replace exactly four `unrelated_0000{0,1,2,3}` source tools in the
  registered inventory without adding routes or changing the original
  500/5000 counts.
- Host-authored source-native typed fields form `root (openapi) → middle (mcp)
  → target (optimade)`, plus `root (openapi) → direct (custom)`.
- The expected graph edge sets, defined **independently of either indexed
  engine**, have counts `3→2→3→1→3`: initial, middle typed output changed,
  middle restored, root typed output changed, root restored. The only two
  changed source tools pass through the built-in in-memory atomic change-key
  journal, and every stale original graph lookup must reject.
- A second intentionally simple oracle looks at the actual four registered
  source ToolSpec inputs/outputs and their closed, required scalar contracts;
  it never calls graph builder, edge updater or retrieval result. Source-only
  oracle edges must exactly equal the preregistered stage and canonical
  incremental AND full-rebuild graph edges.
- Full posting-index and graph source snapshot equality includes source
  fingerprints, route postings/locations, graph edges, all root/consumer
  counts and source-derived contracts. The source check catches a shared
  graph bug that delta-vs-rebuild equality alone would miss.

## Principal, privacy, liveness and 1-/2-hop path oracle

For each of the five original registry versions: six host-defined scopes
(`visible`, `hidden_root`, `hidden_middle`, `denied_middle`, `denied_direct`,
`unavailable_root`), both allowed-reader and no-role principal, and EN/KO/JA
alias pairs. Direct source-typed one-hop and chained 2-hop results must match
both the independently enumerated expected path and full-rebuild lookup;
both argument bindings are pinned (`contact_id` and `case_id`). This gives
**180 one-hop and 180 two-hop checks** per catalog size. The source/permission
oracle has fixed expectations, so an indexed failure shared with rebuilt
lookups is not automatically accepted.

On the initial snapshot, mutate a live blocked-source set behind exactly the
same availability predicate callable. Root-down and intermediary-down
transitions must instantly suppress affected paths and recover without any
registry version bump (four checks). None of these checks invokes tools or
allows unscoped executor calls.

## Production bug reproduced under real nonempty churn

`NativeSchemaGraphIndex._refresh_changed_contracts` previously recomputed
`native_root_count` for unchanged contracts with `bool(contract.produces)`.
That counted an intermediary that **both requires and produces** a typed
identifier as a source root. It surfaced only when root-source churn caused
that intermediary to remain in the old-contract set. Correct count is
`produces and not requires`, matching `_source_native_graph_contracts` and
full-build semantics. The new five-snapshot test fails before the fix and
passes after it; the graph's actual edges were already correct.

## Guardrails and evidence tier

- All 500/5000 ToolSpec tools are developer authored (native-like source
  descriptions, not actual independent provider imports).
- The finite expected edge/path oracle is host authored. It does **not**
  establish publisher-authored gold #1346, independently reviewed 1/2-hop E2
  #1477, calibrated no-fit, real provider behavior or schema-byte savings.
- Only the existing canonical `NativeSchemaGraphIndex` / posting index,
  production live scoped lookup and built-in source journal are used.
  No new ranking engine, model calls, executor or default route changes.
- CI runs both 500 and 5000 acceptance suites and CLI aggregate-only
  `E0_SYNTHETIC_MIXED_SOURCE_NONEMPTY_G5_JOURNAL_CHURN_NOT_E2` artifacts;
  `#1356` remains HARD HOLD, #1560 remains open and Draft #1755 unmerged
  until independent owner E2 gold arrives.
