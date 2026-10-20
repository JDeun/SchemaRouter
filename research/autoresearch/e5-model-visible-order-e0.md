# E0 registered A/B — model-visible E5 K5 order (2026-10-20)

## Narrow testable hypothesis

Merged #1615 only added an opt-in ordering seam to the existing agent evaluator, and did **not** demonstrate utility. Before seeing real A/B results, test whether preserving already verified E5 candidate relevance order changes the external agent's tool-operation completion or unsafe non-fit behavior relative to the default alphabetically sorted presentation. **No scoring threshold or no-fit policy will be fitted** to the observed examples.

## Fixed source and controls

- Previously disclosed `benchmarks/multilingual-embedding-cpu-dev-20261015.json`, exact SHA-256 `dc8b0a7c9325c8767d9b323b24040e0dfe94f3fd170b829b6f977c0e629b2110`; fixed 12 original cases, two supported and two unsupported per EN/KO/JA, 13 native read-only operations.
- Pinned locally executed `intfloat/multilingual-e5-small@fd1525a9fd15316a2d503bf26ab031a61d056e98` and `Qwen/Qwen3-0.6B@c1899de289a04d12100db370d81485cdf75e47ca`, CPU Ubuntu GitHub Actions. Shared `run_generated_episode` and `FrozenCorpusExecutor`, no second agent loop.
- Fix exact K5, source registry and authority, task prompts, arguments, model system prompt, deterministic decoding. **The five candidate identities AND ranking are matched across A/B**; only the order of model-visible JSON tool definitions differs.
- Counterbalanced within task `A,B,B,A`, with A = alphabetically sorted existing behavior, B = E5 relevance order; 48 actual model episodes from 12 exposed tasks. This is not blinded, randomized or independent.
- **Score on completed original executor receipts only**, never pass fixture `required_routes`, expected operation, model generation, task status, gold or secret into the selector. No auto refills or dynamic K and no invented source aliases.
- Post-hoc model-visible order witness must exactly match the exposure arm on each turn; all candidates must be current authorization-visible native routes. Fail closed if source/policy/candidate list changes or model order drifts between turns.

## Metrics and go/no-go before unblinding

Primary descriptive metrics are positive synthetic one-step fixture completion and unsupported *strict* no-call+exact refusal, separately per language with denominators. Report unsupported tool *attempts* separately from unsupported successfully executed operations. Report number of original source cases whose E5 order differs from alphabetical and number of nonidentical outcome pairs over 24 A/B pairs. Unauthorized destructive executions must remain zero. Any failure of source exactness, model-ID attestation, fixed K5, view isolation, optional scope or immutable corpus aborts as INVALID.

No production promotion regardless of DEV results. The minimum signal to justify a **new prospectively independent external** test is nontrivial supported positive improvements **without increased unsupported tool attempts, false acceptance, privacy leakage or unbounded CPU latency**. If no rank-order difference or a regression occurs, retain existing alphabetical model presentation by default. No causal effect-size claim from this tiny disclosed cohort or sequential runs.

## Limitations and release gate

The tasks are deliberately seen/synthetic; tool observations are deterministic and **not original provider HTTPS execution**. Neither independent #1346 publisher labels, multi-step source grounding, correct factual final-answer validation, strong no-fit calibration nor #1477 E2 has been established. Same frozen #432 negative remains immutable, and #1356 v0.18 release remains HARD HOLD. Research output must contain aggregate counters and sanitized model/hardware/source IDs only, never full prompts, task texts, raw generations, source gold or private fields.
