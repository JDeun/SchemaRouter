# Host preflight fail-safe for zero visible healthy tools — E1 (2026-10-20)

## Cause and independently labeled observation

Already merged #1619/#1620/#1621 provide explicit healthy model-visible tool schema and long-lived one-router state. The first actual pinned Qwen CPU E1 baseline in [#1622 original run](https://github.com/JDeun/SchemaRouter/actions/runs/39385240475) showed EN/KO/JA each propose **no tool** when no definitions were visible. However the separately added (explicitly post-hoc) strict refusal diagnostic found **0/3 exactly canonical `REQUEST_MORE_TOOLS`** after the one-allowlisted-ChatML-terminator parser. A no-tool final is not exact safe refusal, and one CPU generation on this small Qwen fixture took roughly 7.6–9 seconds. This E1 artifact is a **success/failure diagnosis**, not evidence of independently sampled E2 or overall agent correctness.

## Correct host behavior and implementation contract

If the application has already established no current eligible principal-visible native tools from **trusted explicit health probes + input readiness + existing typed cooldown**, the correct output is an **application-owned status**, not a model-generated guess. This is implemented only as a separate **opt-in research host turn function** `run_strict_health_gated_model_turn` and does not alter the original first pinned Qwen experiment.

- `temporary_unavailable`: host sees authorized input-ready provider path that is down or unknown. Do not call an LLM. Return exact bounded host terminal literal `REQUEST_MORE_TOOLS`, with distinct `status=temporary_unavailable` and `semantic_no_fit_established=false`.
- `inputs_missing`: do not call LLM; return the same bounded public terminal literal but different safe source-readiness reason. Cannot infer denied/field-scoped route from this disposition.
- `ready`: recheck exact source/policy/contract and latest fresh probe, call the injected agent for **one model proposal** on a worker (background watchdog remains active); recheck immediately on return. If source or health changed, **discard all proposed output** and return only a host-owned `needs_revalidation` label and safe terminal. Never perform a provider call or treat the model proposal as execution authority. The existing trusted executor is the only allowed future execution path after a separate validation.
- Parse the model proposal with the original existing strict Qwen tool parser. A model asking for a route not explicitly in the currently offered menu is never executed. Record coarse category only. Do not leak prompts, source-projected private data, model generation/raw body, coordinates, task gold or HTTP payload.
- No health probes are inferred from arbitrary business GETs, model tokens or Open-Meteo model-update status. Unknown stays unknown without registered host-owned approved read-only probes.

## Strict E1 verification

The fixed no-network `httpx.MockTransport` suite uses real original bound router/health, principal-scoped model menu and fake agent that would respond incorrectly if invoked: no healthy routes -> exact host refusal without **any model calls** or **any provider HTTP calls**; unknown probe -> same; missing native inputs -> separate cause; normal route gets one authorized definition and a proposal only; hidden route is quarantined; mid-generation cooldown invalidates the model receipt and discards its output; sequential health toggles cause consistent skip/re-entry. No synthetic claim of actual remote provider success.

The original Qwen run is immutable and remains a negative exact-no-fit terminal finding. This is a follow-up host policy **after** observing it, thus not independent confirmation, not a change to original models or benchmarks, and not an E2 factual agent pass. v0.18 #1356 HARD HOLD remains.

Latency guidance: no LLM call is made in the zero-healthy-route branch (hence zero model *generations* there). Do not claim saved p95 or remote end-to-end SLO without separate measurements.
