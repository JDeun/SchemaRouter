# #1452 — Read-only trusted host-field scan lower-bound DEV

## Objective and prohibited interpretations

Current host-owned exact-field diagnostic runs full `SchemaRouter.retrieve_authorized(k=entire catalog)` and then matches the host's independently trusted structured requirements. #1448's source-pinned 100/250/500 typed but **same-author synthetic** DEV report measured 500-route public selector p95 **3930.83ms** and full retrieval p95 **3836.20ms** ([Actions 38874869933](https://github.com/JDeun/SchemaRouter/actions/runs/38874869933)). This motivates a **purely research-only**, explicitly non-public lower-bound comparison that directly traverses authorized typed metadata.

**Not a drop-in API**: the merged product's security contract explicitly uses the public principal-scoped retrieval path. This comparator neither issues executable capability receipts nor proves that public retrieval may be bypassed. No production shortcut is authorized by a speedup.

## Frozen DEV controls

- Use only `benchmarks/current_adapter_scaled_authorized_dev_v1.py` and current parsed OpenAPI/MCP plus native database/vector/graph `ToolSpec` fixtures, sizes 100/250/500; Viewer has 5 denied mutations and `audit_tag` is hidden. Entire fixture is synthetic and known to the authors.
- Fixed 6 author-written cases: unique invoice, unique vector, denied payment, absent field, hidden audit, intentionally ambiguous common payload. English/Korean/Japanese query labels per case; the exact structured field contracts are **host supplied in advance**, not inferred from natural language.
- For each case: actual public `retrieve_authorized(k=size)`, actual `select_authorized_field_contract(k=size)`, and distinct read-only `direct_scan`, **two repeats**. 3 sizes × 6 × 3 languages × 2 = **108 paired cases**.
- Private direct scan checks authorization first, local availability, current data-scope projection, exact read-only and output/enum field conjunction, with fail-on-registry/policy/availability identity change. It does not depend on embedding/score, choose a Top-K route, call planning, execute a tool or inspect gold to manufacture a winner.
- Fail the whole experiment if any public/direct reason, selected route or ambiguous identity set differs, if returned public candidate count differs from internally observed visible candidate count, if expected negatives become selections, or any timing/output is malformed. This parity is necessary **but not sufficient** for replacing the public API.
- Record all 108 raw rows, honest p50/p95/p99 for three measured paths at each size, CPU, peak RSS, source SHA256, exact checkout Git SHA. Do not re-score frozen 0.14 or make agent task success claims.

## Reproducible CPU run

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23" "PyYAML>=6,<7"
python -m pytest -q tests/test_research_host_exact_field_scan_lower_bound_dev.py
python -m scripts.research_host_exact_field_scan_lower_bound_dev \
  --repeats 2 --output artifacts/host-exact-field-dev/report.json
```

The [dedicated workflow](../../.github/workflows/research-host-exact-field-lower-bound-dev.yml) uses Ubuntu 24.04, Python 3.12, 20-minute job cap, source-pinned dependency installer actions, read-only permissions and artifact retention. No network API, GPU, agent, model execution, deployment, production policy/write keys or release.

## Adversarial input and runtime-state boundary (follow-up #1452)

The previous 108 paired measurements exercised **only prevalidated, source-authored host principals and field contracts**. Passing those comparisons does not establish that the experimental `direct_scan` validates caller-owned authentication claims or forged Pydantic instances. The separately hardened public `select_authorized_field_contract` explicitly revalidates both `PrincipalContext` and `HostFieldContract` under strict parsing. The DEV scan does not.

A negative-control test intentionally constructs (1) a `PrincipalContext.model_copy(update=...)` whose role tuple contains a non-string and (2) a `HostFieldContract.model_copy(update=...)` with duplicate required fields. A raw metadata scan can still select a route because it does **not** validate these envelopes; the public product API must reject both with `PolicyViolationError`. This is a **counterexample to product security parity**, not a bugfix or a disclosure of any real identity. No same-author 108-case performance result can waive this safety blocker.

A positive-control test additionally covers an active exact-contract executor cooldown: both the raw experimental scan and current public selector should expose an empty available catalog. A policy object swap during scan must cause an error instead of yielding a stale research selection. These tests remain in a separate research-only PR; no public API or production logic changes, and no complete concurrency or authenticated host evidence is claimed.

## Promotion blockers regardless of results

Prospective production-grade design would require a separately reviewed explicitly opt-in API boundary, authenticated host scope, policy version and effect-aware no-leak attestation, resolver cooldown/access parity, principal/role alternation, source and schema mutation/TOCTOU defenses, alias and enum tests, race controls, robust negative coverage, independent real-provider holdout, agent utility study and meaningful CPU improvement on the exact checked-in current source. The current comparator intentionally does **not** meet these requirements. #1450 and #1431 stay open; independent #1339/#1346 and held v0.18 #1356 unchanged.
