# Source-aligned Nous user-role two-step E0: opt-in model/host replay

**2026-10-18.** Owner #1510 → #1477, A02/R05. This is a preregistered experimental **transport-only** successor to the exposed 3-task bound-host model DEV, **not** a new model or prompt search.

## Why this experiment, and what is held fixed

The [source-pinned upstream Qwen-Agent Nous E0 conformance](qwen-agent-nous-upstream-protocol-e0.md) invokes actual `NousFnCallPrompt` at `31a4d36d123688581a9e9744427272b33ce940e0`. It establishes a concrete non-equivalence: after an authorized function call, Qwen-Agent replays the function result as **`role=user`** with `<tool_response>…</tool_response>`, whereas the original SchemaRouter Qwen E0 pilot replayed it as **`role=tool`** and preserved raw assistant EOS text. #1508 already compared strip-EOS and structured tool-role transports, both 0/3; those were **not** source-aligned Nous USER history.

This new strictly opt-in `--transcript-mode nous-user` changes only **after** a successful `execute_scoped_host_call`:
- The assistant message reconstitutes `<tool_call>…</tool_call>` from the **already host-validated and actually executed** route+arguments, not untrusted free text/EOS.
- The next message has `role=user` and `<tool_response>…</tool_response>` from the **actual source-projected observation**. Do not use arbitrary provider text as instructions, route hints or policy changes.
- Source and route ID authorization remains principal-scoped; no visibility expansion, native executor override, provider substitution, retry budget change or permission grant. Hidden/source forbidden metadata must not reach model messages.
- Input task prompts, fixed two registered read-only operations, model/tokenizer weights (`Qwen/Qwen3-0.6B` at existing pinned revision), decoder settings, EN/KO/JA revealed synthetic cases, original strict final oracle, CPU constraints and host reauthorization are retained.
- Default `raw` mode remains unchanged, including its original history and E0 reports. Alternative is **not** the product default.

The [dedicated GitHub Actions job](../../.github/workflows/research-qwen-nous-user-bound-e0.yml) first runs source-only simulated EN/KO/JA regressions proving two real `Router.execute` host calls with dependent ID, correct strict final, fail-closed on revoked authority, bad route/argument, hidden response and EOS injection. It then runs **real pinned Qwen CPU inference**, reports all three original E0 task outcomes, and retains negatives instead of replacing or pooling older 0/3 results.

## Measurement and stop rules

Primary E0: per-language full-task correct, two actual bound calls, premature final/invalid proposal classification, strict final answer vs actual host oracle, unauthorized call attempt, no unauthorized physical execution. Same 3 public tasks are **exposed** and have published outcomes, so these are diagnostic **paired transport results only**. A source-aligned history is not evidence of generality, calibrated unsupported refusal or independent E2. Do not tune prompt/model/threshold from observed outcomes.

If fail: retain negative result; investigate protocol readiness only through upstream-native source tests. If pass: retain as E0 transport compatibility only, do **not** promote models or authorize v0.18. The next gate is publisher/task-independent EN/KO/JA native tool/no-fit/clarification and full-task E2 with locked gold/permissions.

**Standing:** A02/R05 NOT_VERIFIED, independent E2 **0/19**, held v0.18 #1356 and default model promotion HOLD.


## Actual pinned CPU outcome — 2026-10-18 (negative E0 evidence)

At [GitHub Actions run #39044874054](https://github.com/JDeun/SchemaRouter/actions/runs/39044874054), exact source commit `cee5344ed0aca1683cf1978634f97ab073e2f3ff`, the `no-model-source-host-contract` job passed and the `real-pinned-qwen-nous-user` job completed **SUCCESS** as an engineering workflow. Its *strict scored task outcome* is **0/3 full tasks**, not a model success:

| Original published E0 request | Actual host-bound calls | Two steps complete | Strict final correct | Stop reason |
| --- | ---: | --- | --- | --- |
| English | 1 | false | false | `premature_final` |
| Korean | 1 | false | false | `premature_final` |
| Japanese | 1 | false | false | `premature_final` |

This reproduces the frozen original `raw` 0.6B E0 symptom even after correcting the upstream Nous **result role** and stripping raw EOS from reconstructed assistant history. No unauthorized tool execution was observed in these three rows, and there was no completed dependent tool or final-answer oracle success. It is falsifying evidence **against role mismatch alone as the sufficient fix**, not a universal causal attribution or a negative benchmark against all models.

Do not retune these now-exposed cases, raise K, or repeat the same prompt with learned gold. Next gate remains original-publisher/task-independent EN/KO/JA multi-step/clarification/no-fit qualification and hypothesis testing on a locked split. Prior #1507/#1508 0/3 and #1509 1.7B 2/3 published observations remain separate. R05/A02 NOT_VERIFIED, E2 0/19, v0.18 and default model HOLD.
