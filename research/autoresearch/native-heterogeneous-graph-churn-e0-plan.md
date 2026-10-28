# B1 nonempty mixed-source G5 churn — implementation plan

**Goal:** Close the nonempty 1-/2-hop versioned graph churn E0 test gap in
one issue-sized change, reuse existing indexes, and qualify the exact remote
Draft PR head without claiming independent E2.

**Design:** [native-heterogeneous-graph-churn-e0-design.md](native-heterogeneous-graph-churn-e0-design.md).

1. [x] Write failing acceptance test for 500/5000 five-state graph edge
   oracle, 1/2-hop scopes, bindings, freshness, health, evidence flags and
   bounded input; `pytest` RED on missing script.
2. [x] Implement native-like mixed ToolSpec four-source typed graph fixture,
   explicit independent source-only witness, five source-owned journal
   stages, full-build equality, six scopes × two principals × three aliases.
3. [x] Reproduce nonempty production root-count mismatch during root-source
   delta, narrow it to intermediates being counted as roots, correct the
   canonical root predicate once, rerun focused TDD.
4. [x] Extend existing dedicated 500/5000 E0 CI matrix with scoped tests,
   executable audit, artifact, exact edge/count/E0 gate and job summary.
5. [x] Verify **375 related native graph/journal/source tests passed in
   190.70s**; post-review strengthened focused 9-test set **9 passed in
   10.96s** and 5000-route CLI returned exact gated JSON. Repository Ruff
   green, changed modules Pyright 0 errors, YAML parsed and diff clean.
6. [ ] Publish exactly scoped blobs as fast-forward to Draft #1755, post
   evidence references to #1755/#1560, verify pinned remote exact-head CI.

**Not within this E0 scope:** independent publisher schemas/permissions/gold,
original paper E2 model/provider runs, merging Draft #1755 or removing release
hard-hold #1356.
