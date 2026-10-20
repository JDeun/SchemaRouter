# E1 bounded health-gated model turn — request deadline and late-result quarantine

## Actual gap

The merged #1623 default-off host strict availability preflight correctly returns an application-owned exact refusal when there are no healthy native operations and drops stale proposals. But for a healthy catalog it calls `asyncio.to_thread(agent.generate)` with **no host-side deadline or same-agent in-flight guard**. A stuck or unexpectedly slow local Qwen can hold a request indefinitely; merely observing the background watchdog does not stop the model thread.

## Narrow isolated adapter

`BoundedHealthModelTurnE1` composes the **existing** `run_strict_health_gated_model_turn` rather than modifying retrieval/scoring/security contracts:

- One explicitly retained controller owns ONE model, ONE router, an event-loop affinity and a positive finite deadline (0.01–60 seconds). One active request is admitted; concurrent callers of the same controller immediately return `model_busy` with no additional model invocation.
- With no viable authorized, input-ready, recently healthy tool, the parent host preflight returns exact `REQUEST_MORE_TOOLS` and `temporary_unavailable` with NO model execution. The controller preserves those results unchanged.
- For a healthy eligible menu, one model generation begins on the existing executor worker. The caller waits only until its host deadline. On timeout, return sanitized `generation_timeout`, exact host literal and explicit `semantic_no_fit_established=false`; no model text, tool args, credentials or provider data. A `threading.Event` distinguishes whether the actual model call began before timeout.
- **Important limitation:** `asyncio.wait_for(asyncio.shield(task))` is a **request deadline, NOT a hard CPU/process kill**. The actual `to_thread` generation may continue after the caller returns; its task stays referenced/quarantined and blocks another generation through this controller until it actually completes. On a client cancellation, the inner worker also remains quarantined. Its late result or exception is consumed silently and **NEVER** sent to a caller or executed.
- If the model raises, return a sanitized `generation_error` rather than expose raw stack details or pretending a provider outage. Closed controllers reject new work. No process-global mutex is claimed; an application sharing one Qwen model across sessions must use the SAME retained controller or provide equivalent cross-session admission control.
- A future true hard-deadline/cancellation SLO requires supervised killable **subprocess isolation** (not available from thread-only in-process transformer inference). The current implementation must not report `generation_timeout` as evidence that CPU resources are reclaimed, and should monitor long-running tasks separately.

## Evidence and validation

Ubuntu Python 3.12 deterministic no-network tests use an agent blocked on real `threading.Event`: timeout -> actual thread remains active -> second host call is rejected without a new generation -> eventual completion is discarded -> new request can execute; client cancellation -> same quarantine; two simultaneous host calls -> exactly one generation; no-probe unavailable -> zero generation; malicious/raw model exception -> only sanitized error; invalid timeout -> fail closed. Existing 41+ parent health and scoped routes tests run alongside.

All proposed tools are classified only; zero provider HTTP and zero model-selected tool execution. This is a default-off E1 request admission control, not independent E2, real Open-Meteo uptime, production latency p95 or model semantic no-fit improvement. Independent provider probes, original frozen #432, and v0.18 #1356 HARD HOLD remain unchanged.

## Additional actual pinned Qwen CPU model deadline check

After the deterministic no-network proof, the dedicated workflow has a second job using the **existing pinned** `Qwen/Qwen3-0.6B@c1899de289a04d12100db370d81485cdf75e47ca` and its previously published EN source prompt. An injected read-only host probe reports healthy and an HTTPX MockTransport raises on every provider GET (zero real provider traffic). A **0.5s host request deadline** is compared to one *actual* Qwen CPU generation; the job checks that the request returns `generation_timeout` promptly, that the Qwen generation **remains actively quarantined**, and that a second turn is rejected with `model_busy` until the actual model thread terminates. The workflow prints only an attested aggregate status and request elapsed time, never the model generation, prompts or tool arguments.

This CPU experiment validates the *request deadline and admission behavior*, not an operating-system hard kill, saved compute cost, model fit, provider uptime or general latency distribution. It is a single publicly disclosed model task; do not report a production p95. Hardware can change and cause a run to fail; any such failure must be analyzed, not silently removed.
