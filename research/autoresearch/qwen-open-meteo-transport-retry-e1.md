# Real native Open-Meteo GET transport reliability — E1 scoped

Issue [#1574](https://github.com/JDeun/SchemaRouter/issues/1574)
stacked after state-ready model E1 PR [#1573](https://github.com/JDeun/SchemaRouter/pull/1573).

On actual pinned Qwen3+Open-Meteo paired source run
[39176697976](https://github.com/JDeun/SchemaRouter/actions/runs/39176697976),
both EN cases stopped after a valid original geocode with
`premature_final` (not fixed here); both KO cases failed original
`geocode_http_transport_failure`; Japanese state-ready reached verified
live first+second provider calls and exact factual JSON final while
all-visible prematurely finalized.

One engineering hypothesis independent of task gold: Open-Meteo's
fixed HTTPS GET is idempotent, so retry **once** only on original
`httpx.RequestError` before any source observation is validated.
`OpenMeteoBoundInvoker` default remains ZERO retries; new
`transport_retry_budget=1` is opt-in E1. Same exact URL, original
country, arguments and host. No HTTP redirect, provider response cache,
unverified value or automatic model call. HTTP errors with responses,
malformed JSON, invalid country/schema and host permission changes are
NOT retried. Real HTTP attempts and actually validated source responses
are counted separately. All source/invoker failures remain failures.

Compare the same two existing Qwen3 and real provider E1 exposure arms
(`all_visible`, `state_ready`) with identical one-retry setting in
the SAME CPU model run, alternating arm order. Replay of previously
disclosed three EN/KO/JA requests, not independent E2, is a source
stability diagnostic. Weather and geocoding may still fail; strict
source-typed model arguments, principal and factual final are unchanged.
A first successful retry is not credited as model quality improvement.

Mock transport tests include first connection fail/second GET source
success, two genuine failed GETs, default no retry, country/payload
rejection (never retry), wrong future route and no fake completion.
No production default model, SchemaRouter invoker, source auth grants,
frozen #432 or held #1356 release changes. Publisher-authored
permission/gold/private split #1346 and actual E2 #1477 remain required.
