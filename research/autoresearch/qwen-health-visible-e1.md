# E1 pinned Qwen actual tool disclosure under simulated host availability (2026-10-20)

## Motivating issue and exact scientific boundary

The source-safe E1 adapter merged as #1619 and the same-router host E1 proof merged as #1620; neither asked a real pinned Qwen model to generate while the source menu changed. An E1 strict model receipt also exposed a spurious false denial: a normal periodic positive probe updated the timestamp during a model turn, invalidating the otherwise unchanged healthy route. Parent [#1621](https://github.com/JDeun/SchemaRouter/pull/1621) fixes that narrow host controller issue with no-model tests and is the source dependency of this study.

## Registered, fully disclosed experiment (not independently authored)

- Frozen public E1 `SYSTEM`, `USER_REQUESTS`, `CASES` and `PrincipalContext` imported verbatim from existing real Qwen/Open-Meteo harness. Three source languages EN/KO/JA, one exposed weather task each.
- Pinned real local `Qwen/Qwen3-0.6B@c1899de289a04d12100db370d81485cdf75e47ca`, CPU GitHub Actions 24.04; same model instance, deterministic decoding and one single live `SchemaRouter` across all 9 observations.
- Three host-controlled phases per language in order `healthy → unavailable → recovered`. **Both** actual native routes remain source-registered and original; no new operation or source read. At first turn, current-weather route is not input-ready, so only the geocoding definition is eligible. The geocoding *host-owned callback* returns True, False, True per phase. Explicit positive/negative probe receipts and the existing registry/authorization/cooldown gate yield exactly **one → zero → one actual model-visible tool definitions**.
- `agent.generate` is run on a dedicated worker to leave the monitor/event loop live. An additional host-owned `check_health_once` after model inference guarantees a second recent healthy observation; a harmless Healthy refresh must not spuriously invalidate the presented tool.
- Exact existing Qwen strict `parse_one_model_action` classifies the proposed operation as visible or hidden, terminal, malformed, or context overflow. **No model-selected tool is executed**, even if Qwen hallucinates an explicitly unavailable operation. The HTTPX transport is an in-memory sentinel that raises on **any provider GET**. Report exposes only counts/class labels, token counts, CPU model generation time, fixed public language and phase; no raw generated text, prompts, weather, coordinates, provider result or private source schema.
- Fail-closed tests with injected agent output demonstrate a model-generated hidden weather attempt, a hidden geocoding attempt during outage, invalid model formats and safe non-execution. Only actual pinned `LocalQwenAgent` may label the final CPU artifact `REAL_LOCAL_QWEN...`; injection tests label explicitly `INJECTED_AGENT_NO_REAL_QWEN_E1`.

## Metrics and limitations

For each of 9 (3 language × 3 phase) **non-independent** model episodes report selected tool count (1/0/1), proposed action class, total token overhead and generation CPU latency. Zero business-provider requests and zero executed model-selected operations are **mandatory**. This evaluates **availability disclosure** and model attempted behavior, not business task completion, final weather factual answer, true remote provider liveness, pricing/failure budget, calibration, generalization or independent E2. Host probe outcomes are **simulated**, not Open-Meteo official status; do not describe this as verified live API performance.

The strict E1 mode remains explicitly opt-in; product defaults, original frozen #432 and v0.18 #1356 HARD HOLD unchanged. Independent #1346/#1477 and real provider-qualified session are still open.


## First actual pinned Qwen run and secondary diagnostic

The first pinned CPU report ran successfully at branch head `ff245bc73fd7e305ba0c2a3f3f501383c1982151`, [GitHub Actions #39385240475](https://github.com/JDeun/SchemaRouter/actions/runs/39385240475) (artifact 12246943184). Actual real model proposals for EN/KO/JA were **attempt_visible_tool → terminal_no_tool → attempt_visible_tool** for host simulation Healthy/Unavailable/Recovered respectively, and the actual model was shown 1/0/1 definitions. The experimental host executed exactly zero model-proposed calls and zero network provider requests. Latency was ~8.7–9.8 seconds per pinned CPU generation, not API/transport latency or benchmark p95. This is one exposed prompt per language and MUST NOT be characterized as generalized fit/no-fit accuracy.

**Post-hoc extension after seeing the original labels:** Because `terminal_no_tool` cannot establish a compliant refusal, a new boolean `exact_host_refusal_after_allowlisted_eot` is attached to each model proposal. It is True only when the original strict `parse_one_model_action` returns a `final` payload **exactly** `REQUEST_MORE_TOOLS` (after removing at most one already allowlisted ChatML end marker). Arbitrary "cannot do it" text, malformed format or hidden tool attempt must remain False. A no-tool final can be terminal-format-wrong; do not count it as a safe no-fit success. This additional diagnostic changes NO prompts, model tool lists, authorization, parser, generation method or execution; it is a repeated descriptive E1 and not independent confirmation. Never infer model compliance from previously uploaded `terminal_no_tool` alone.

Parent #1621's benign healthy-heartbeat receipt fix is now merged in main at `3bc9232e4d8e2d41b167372baa080a5570192bf0`. The new head is rebased in meaning (exact four new research-only files) onto that `main`; no duplicates, defaults or core changes.
