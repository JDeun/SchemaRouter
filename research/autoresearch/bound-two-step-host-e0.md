# A02 — two-step real Router.execute host-bound synthetic provider E0

**Owner:** #1477, qualification A02, with S02 #1450. This is implementation-level engineering proof **only**.

The original `FrozenCorpusExecutor` tests verify a stateful fixture, not actual `SchemaRouter.execute`. This additive E0 study now routes two read-only operations through **real package authorization, planner, RegistryExecutor binding and output projection**, using deterministic **in-process synthetic host functions**, not a live third-party provider.

1. Authorized read `marine.read` requires `place` (host-verified input). The host invoker returns a **public** `record_id` and a secret canary.
2. A fresh principal-scoped source view is captured; a new trusted field preflight ensures `papers.read` has its required `record_id` from the **projected public first-step result**, not the private raw provider response. The second real host binding returns a typed boolean verification result.

The EN/KO/JA original user prompts use the **same** deterministic two-step route contract. Language variants test view and call safety, **not** independent multilingual comprehension. Tests assert exact two host-bound executions and second-step argument state handoff, zero hidden canary disclosure, missing/wrong first argument blocks before physical invocation, and no second host invocation after **same-policy-object RBAC mutation**, policy replacement, principal role revocation, or a private host error.

## Stop conditions

- Each call must be freshly authorized; no earlier model-view snapshot itself grants execution.
- All model/provider observations are scalar public projections; no raw private response is provided to the second stage or final report.
- An attempted mutation or missing/hidden route must not silently become a new authorized route.
- A one-step success is never a two-step completed task. Both host-bound executions and the final typed host oracle must succeed.
- `actual_model_inference_measured=false`, `actual_model_final_answer_correctness_measured=false`, `real_external_native_provider_execution=false`, `independent_e2_qualified=false`.

This does **not** include actual model-generated tool selection, a user-facing answer correctness oracle, external original provider invocation, a 3-step task, an independent case author, stress-tested concurrent revocation or calibrated false refusal. Therefore **A02 NOT_VERIFIED, S02 ENGINEERING_ONLY, E2 0/19**, v0.18 #1356 and default promotion **HOLD**.

Run: `python -m pytest -q tests/test_research_bound_two_step_host_e0.py` on Ubuntu Linux CPU.
