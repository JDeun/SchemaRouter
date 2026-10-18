# Trusted original-provider failure-stage receipts (public Open-Meteo E1 DEV)

2026-10-18, issue #1477. This is a **diagnostic/observability patch**, not an
agent, router, model or API capability change. It follows merged #1525, which
proved a verified-response counter alone underreports failed HTTPS attempts.

## Observation / trust boundary

Only the **host-bound original Open-Meteo invokers** may set a
`last_failure_stage`. The research harness reads this only **after the
existing trusted host rejected the model-generated call**. The stage is never
included in the prompt, tool definition, visible observation, model history or
authoritative execution plan. It is not a permission receipt or inference about
the model's intent.

Source stages are fixed, bounded and require an actual invoker-level event:

| Stage | Evidence actually available | Claim not justified |
| --- | --- | --- |
| `http_transport_failure` | `httpx.RequestError` during fixed-host GET | Provider was down, model chose wrongly |
| `http_status_rejected` | HTTP non-2xx rejected by `raise_for_status` | Authorization or provider identity cause |
| `response_json_rejected` | Original HTTP response failed bounded strict JSON/envelope checks | Semantic city mismatch |
| `geocoding_payload_rejected` | Original geocode result failed registered ID/country/coordinates validation | Exact rejected original response field |
| `weather_payload_rejected` | Current-weather value/time/Celsius contract failed | Final-answer generation failure |

The evaluator adds `geocode_` or `forecast_` to these stages based on
the original fixed source only. A masked trusted-host exception with no
invoker receipt yields `host_boundary_without_new_http` if no GET was
attempted for the rejected call, `host_boundary_after_validated_source`
if an original response was validated before boundary failure, or
`unclassified_after_http_attempt` when source/host evidence is insufficient.
These are **observations**, not unique failure causes. The original
`host_or_native_source_denied` stop reason and the independent strict
final-answer oracle are unchanged.

## Privacy, correctness and experiment controls

- Never export provider exception messages, URLs, coordinates, city texts,
  response JSON, query, gold, raw arguments, user/tenant credentials or traces
  containing chain-of-thought. The stage is a fixed finite string only.
- Exact fixed Open-Meteo hosts and paths remain the only allowed network
  targets; first-hop source location/state must still bind the second call.
- Preserve legacy `calls` as validated successes, new
  `http_attempts` as attempted outbound requests; nonzero attempts do not
  imply a response was received, nor do successful invoker responses prove a
  complete model-generated task.
- Model-generated route, arguments, state handoff and strict factual final
  remain the unchanged scoring authority. Source contract failures remain
  **failed** tasks, including possible live provider outages.
- Existing exposed n=3 EN/KO/JA original inputs are **not** independent
  publisher-authored E2, privacy/authorization certification or a model-size
  comparison. Preserve historical Qwen3-0.6B 1/3 and Qwen3-1.7B 1/3
  first-real-run outcomes; later Qwen3-1.7B 2/3 is separate nonpaired exposure.
- Source-stage regression uses offline `httpx.MockTransport` for status,
  malformed JSON, no-match/mismatched-country, wrong weather unit, transport
  exception, source reset, and pre-HTTP denial. These are tests of telemetry
  correctness, **not** new routing or agent success evidence.

## Acceptance

1. Exact-head isolated offline regressions, all protected CI and CodeQL green.
2. The pinned GitHub Linux CPU actual-model jobs run on the original
   Open-Meteo public source and display only safe stop/stage/count summaries;
   keep failed cases, even if total task pass changes.
3. No product default, prompt, model selection, source authorization,
   independent E2 metric or v0.18 release-status change.

**Gate:** #1346 independent publisher-authored task/gold remains blocked,
A02/R05 NOT_VERIFIED, 0/19 E2, #1356 v0.18 HARD HOLD.
