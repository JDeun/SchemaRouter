# SchemaRouter qualification checklist

> AUTO-GENERATED — edit benchmarks/qualification-control-v1.json, then run python scripts/qualification_control.py --write. Do not edit this page independently.

**Reviewed:** 2026-10-17 · **published:** v0.17.0 · **v0.18.0 release:** **HOLD** · **production model/default promotion:** **HOLD**

**Independent qualification: 0/19.** This counts verified E2 only; implemented code, green CI, positive DEV and historical negative evidence are not passes.

| Evidence status | Count |
| --- | ---: |
| BLOCKED_EXTERNAL | 3 |
| DEV_ONLY | 4 |
| ENGINEERING_ONLY | 4 |
| HISTORICAL_NEGATIVE | 5 |
| NOT_VERIFIED | 3 |
| QUALIFIED | 0 |

## Qualification gates

Checking one item requires independent provenance, a frozen split, reproducible artifacts, a separate reviewer and the gate acceptance record. Closing an owner issue never auto-checks an item.

- [ ] **G01 P0** — `BLOCKED_EXTERNAL` — [owner #1346](https://github.com/JDeun/SchemaRouter/issues/1346)
  - Blocker: Publisher-native source/gold and permitted execution are not fully available.
  - Next action: Freeze approved source bytes, license and artifact identities.
  - Evidence: No qualifying independent evidence registered
- [ ] **G02 P0** — `BLOCKED_EXTERNAL` — [owner #1346](https://github.com/JDeun/SchemaRouter/issues/1346)
  - Blocker: Independently authored provider/task-disjoint EN/KO/JA confirmation split unavailable.
  - Next action: Obtain author-reviewed native cases and freeze split plus leakage audit.
  - Evidence: No qualifying independent evidence registered
- [ ] **S01 P0** — `ENGINEERING_ONLY` — [owner #1450](https://github.com/JDeun/SchemaRouter/issues/1450)
  - Blocker: Scoped regression work exists; independent hidden-field/count qualification remains open.
  - Next action: Verify multi-principal, all-hidden and field-masking on real snapshots.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/pull/1449)
- [ ] **S02 P0** — `ENGINEERING_ONLY` — [owner #1450](https://github.com/JDeun/SchemaRouter/issues/1450)
  - Blocker: Source-swap hardening exists; concurrent authority and availability drift not qualified.
  - Next action: Reproduce concurrent registry/policy revocation with no stale execution.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/pull/1472) · [evidence 2](https://github.com/JDeun/SchemaRouter/pull/1497)
- [ ] **S03 P0** — `ENGINEERING_ONLY` — [owner #1269](https://github.com/JDeun/SchemaRouter/issues/1269)
  - Blocker: Synthetic policy protections are not an independent adversarial host evaluation.
  - Next action: Review case-blind action contracts and run approved adversarial host cases.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/pull/1212)
- [ ] **R01 P1** — `HISTORICAL_NEGATIVE` — [owner #1339](https://github.com/JDeun/SchemaRouter/issues/1339)
  - Blocker: Frozen #432 KO/JA initial recall 0/160; later DEV has no independent confirmation.
  - Next action: Score new genuine EN/KO/JA provider/task-disjoint cases at fixed K.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/actions/runs/38501112190)
- [ ] **R02 P1** — `DEV_ONLY` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: Sibling-operation correctness currently has bounded DEV evidence.
  - Next action: Test read/list/update/delete correct selection and abstention in E2.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/pull/1493)
- [ ] **R03 P1** — `DEV_ONLY` — [owner #1444](https://github.com/JDeun/SchemaRouter/issues/1444)
  - Blocker: Typed required field, enum, unit, qualifier and input joint coverage unqualified.
  - Next action: Evaluate source-native input/output/enum conjunctions.
  - Evidence: No qualifying independent evidence registered
- [ ] **R04 P1** — `HISTORICAL_NEGATIVE` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: On disclosed synthetic DEV strict unsupported no-call was 0/6 in each arm.
  - Next action: Fix false calls and calibrate false acceptance without excess false refusal.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/actions/runs/39007769090) · [evidence 2](https://github.com/JDeun/SchemaRouter/pull/1496)
- [ ] **R05 P1** — `NOT_VERIFIED` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: Ambiguous/needs-input/forbidden dispositions lack independent task evidence.
  - Next action: Add missing-parameter and ambiguity cases to integrated scorer.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/pull/1496)
- [ ] **R06 P1** — `BLOCKED_EXTERNAL` — [owner #1346](https://github.com/JDeun/SchemaRouter/issues/1346)
  - Blocker: No independent split establishes safe no-fit operating thresholds.
  - Next action: Preregister supported/OOD operating point on sealed split.
  - Evidence: No qualifying independent evidence registered
- [ ] **A01 P1** — `DEV_ONLY` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: Qwen/E5 pilot measures synthetic one-step fixture completion only.
  - Next action: Qualify native typed arguments, provider execution and actual task pass.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/actions/runs/39007769090)
- [ ] **A02 P1** — `NOT_VERIFIED` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: State-dependent 2/3-step native execution not independently qualified.
  - Next action: Run multi-step E2 with state and final-result oracle.
  - Evidence: No qualifying independent evidence registered
- [ ] **A03 P1** — `HISTORICAL_NEGATIVE` — [owner #1339](https://github.com/JDeun/SchemaRouter/issues/1339)
  - Blocker: Frozen progressive exposure had only 25.09% task pass.
  - Next action: Separate late retrieval, recovery and state propagation failure on fresh cases.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/actions/runs/38501112190)
- [ ] **A04 P1** — `HISTORICAL_NEGATIVE` — [owner #1348](https://github.com/JDeun/SchemaRouter/issues/1348)
  - Blocker: Frozen factual answer evidence gate negative; synthetic operation pass is not grounding.
  - Next action: Freeze provider-grounded answer/unit/provenance oracle; rerun E2.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/issues/1345)
- [ ] **E01 P1** — `HISTORICAL_NEGATIVE` — [owner #1477](https://github.com/JDeun/SchemaRouter/issues/1477)
  - Blocker: Frozen #432 SR-5 29.19% vs FULL 49.62% failed original gate.
  - Next action: Preregister independent paired E2 without altering frozen negatives.
  - Evidence: [evidence 1](https://github.com/JDeun/SchemaRouter/actions/runs/38501112190)
- [ ] **E02 P1** — `DEV_ONLY` — [owner #1428](https://github.com/JDeun/SchemaRouter/issues/1428)
  - Blocker: CPU DEV scale does not jointly qualify task success and p95/p99/RSS.
  - Next action: Measure identical-task K5 schema tokens, CPU tail latency and RSS.
  - Evidence: No qualifying independent evidence registered
- [ ] **I01 P2** — `ENGINEERING_ONLY` — [owner #1346](https://github.com/JDeun/SchemaRouter/issues/1346)
  - Blocker: SDK integration smokes do not qualify native agent approval/execute parity.
  - Next action: Run source-pinned framework-native guarded acceptance.
  - Evidence: No qualifying independent evidence registered
- [ ] **I02 P2** — `NOT_VERIFIED` — [owner #1428](https://github.com/JDeun/SchemaRouter/issues/1428)
  - Blocker: 1000-tool stress, hot swap, invalidation and concurrent-principal coverage incomplete.
  - Next action: Test indexed parity and absence of concurrency leaks.
  - Evidence: No qualifying independent evidence registered

## Separately reviewed release and promotion decisions

- **v0.18.0 release HOLD:** [#1345](https://github.com/JDeun/SchemaRouter/issues/1345), [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), and held [PR #1356](https://github.com/JDeun/SchemaRouter/pull/1356). Qualify feasible external suites, fix real defects, then pass exact-head checks. Do not merge/tag/publish before approval.
- **Experimental/model default promotion HOLD:** [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) integrated paired agent E2; [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) language, [#1450](https://github.com/JDeun/SchemaRouter/issues/1450) authority, [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) external independence. The v0.18 release decision and model promotion are distinct.
- Preserve frozen #432/#424/#506 negative experiments. A synthetic model-agent result is not real-provider E2.

## Update procedure

1. Review current owner issue, exact case/source and permitted evidence.
2. Change the canonical JSON row only; preserve non-qualifying evidence as DEV/negative.
3. Regenerate with python scripts/qualification_control.py --write and check with --check; review GitHub Actions.
4. Scheduled/manual Actions also perform a read-only check that owners stay consistent with unresolved gates and PR #1356 release decision. API outages are failures, not passes.

See [canonical evaluation matrix](docs/research/product-north-star-and-test-matrix.md), [research tracker #200](https://github.com/JDeun/SchemaRouter/issues/200) and [release checklist](docs/release-checklist.md).
