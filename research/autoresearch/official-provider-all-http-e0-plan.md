# Original provider all-operation journal E0 — implementation plan

Spec: [official-provider-all-http-e0-design.md](official-provider-all-http-e0-design.md).
Execution: direct inline, requested continuation of approved #1560 research
scope; tests first. No new index/executor or default behavior.

## Task 1 — bounded original operation scoping

- Test `tests/test_research_official_openai_operations_e0.py` with source
  operation `POST /responses` and `DELETE /models/{model}`, comparing the
  selected raw operation and security/auth/path parameters. Ensure invalid
  query-bearing source paths and unknown methods fail closed.
- Run test RED; implement `scope_original_http_operation_source(document,
  path, method)` reusing the original component closure. Keep the original
  GET wrapper. Run GREEN plus prior GET tests.

## Task 2 — actual full-source native catalog with journal

- Test the exact 371→355 source-to-native count (seven invalid query-path
  operations and nine non-JSON body operations), 358 mixed catalog,
  read/write method preservation, authentication, mandatory inputs and
  no execution/semantic grants. Test the 358→357→358 removal/restoration,
  stale snapshots, independent route manifest and full-build parity.
- Run RED; implement opt-in
  `scripts/research_official_openai_operations_e0.py`, with source-bounded
  per-operation converter and existing registry/index/journal. No provider
  client and no extra inferred field.
- Run GREEN, related regression suites, repository Ruff, relevant Pyright.

## Task 3 — CI, evidence, closeout

- Add both code/test files to the original pinned source workflow, assert
  all receipt invariants on Python 3.12. Update canonical resume document.
- Commit locally, publish only to the existing Draft #1755 branch with
  exact tree comparison, verify new remote-head protected CI and retain
  #1346/#1477 BLOCKED_EXTERNAL and #1356 HARD HOLD.

## Review focus

- No POST/DELETE path may be downgraded to read-only or offered to a model.
- Query-bearing OpenAPI path literals must not be stripped or rewritten.
- A compromised compressed source/license cannot pass pin validation.
- Source-owned journal must reject stale or incomplete manifests even when
  the posting and graph are empty for lack of semantic approval.
- Redact all source data from telemetry, no credentials or network calls.
