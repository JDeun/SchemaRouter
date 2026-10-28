# B1 official GitHub REST 651 GET source E0 — implementation plan

Spec: [official-github-rest-651-e0-design.md](official-github-rest-651-e0-design.md).
Continuation of directly approved #1560 B1 E0; native TDD, no new index.

## Task 1 — original bytes, native shape (RED→GREEN)

- Add `tests/test_research_official_github_get_e0.py` failing against
  `parse_pinned_github_rest_source` and
  `compile_official_github_get_bundle_e0`. Check exact upstream original
  file/license blob and SHA, 823 paths, 651 GET methods, original operation
  ID uniqueness, one 651-endpoint bundle and mandatory path inputs.
- Add tamper tests for original gzip/container/license changes and
  unsupported local `$ref` closure. Run RED then GREEN.

## Task 2 — actual source journal (RED→GREEN)

- Test `audit_official_github_get_churn_e0` against a literal
  654→3→654 manifest, stale index rejection on both updates,
  source-owned journal = full native rebuild, no semantic edges/postings,
  zero provider calls and no policy authority. Verify forged no-op
  refresh fails closed.
- Implement opt-in script using only `NativeSchemaPostingIndex`,
  `NativeSchemaGraphIndex`, `SchemaRouter`, and atomic current-fingerprint
  unregister. Include no external clients or execution transport.

## Task 3 — verification/publication

- Add original immutable file/license fixtures, design/plan, canonical
  resumption checkpoint and dedicated provider-source Python 3.12 CI.
- Run focused/source/index regressions, Ruff, relevant Pyright, attempted
  whole suite. Review diff; commit, publish to existing Draft #1755 with
  original-source tree parity; verify exact new-head CI. No merge/release.

## Review focus

- Large operation bundle still lacks approved semantics/permission. All
  metadata and source strings stay untrusted; negative lookup returns no-hit.
- Source-owned journal must invalidate all 651 routes atomically.
- Never reuse or invent required path input values or auth credentials.
- Any timestamp/date-like strings in upstream JSON remain exact strings.
- Cache, policy, graph, default router and existing E0 GET source behavior
  must remain unchanged outside this opt-in research audit.
