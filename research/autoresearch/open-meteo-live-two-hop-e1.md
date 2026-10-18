# Open-Meteo LIVE original provider two-hop via SchemaRouter (research E1)

**2026-10-18; #1477 / #1346.** This is a targeted executable **live original provider** bridge for an observably successful two-step API workflow, rather than a simulated `FrozenCorpusExecutor` result. This is **NOT** a model/tool-choice accuracy experiment, language understanding measure, independent provider-native E2 or reason to release v0.18.

## Source ownership and execution contract

Official provider descriptions: [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api) and [forecast API](https://open-meteo.com/en/docs). The requested fixed GET endpoints, under sole host-trusted control:
- `https://geocoding-api.open-meteo.com/v1/search` with `name`, explicit `countryCode`, `language`, `count=10`, `format=json`.
- `https://api.open-meteo.com/v1/forecast` with exactly the first-hop **source-validated latitude/longitude**, `current=temperature_2m`, `timezone=auto`.

No credentials, approval bypass, request-supplied URLs, downloads, mutations, redirects or dynamic paths. Two separately registered `ToolSpec` contracts are bound to trusted fixed-host HTTP invokers. All HTTP and typed result validation is done inside this source-specific adapter; `SchemaRouter.execute` validates each explicitly created `ExecutionPlan` against original registry+endpoint fingerprint, input and output schemas and default local read-only policy. It projects only required public output fields.

## Exact development task/success criteria

Three *host-authored* inputs: EN-labeled city `Seoul/KR`, KO-labeled `서울특별시/KR`, JA-labeled `東京都/JP`. This is a **source API localization** check; the city strings, country and sequential tool operations are **supplied by the trusted host**. The text language label is not a model-inferred operation. These original native-script FULL city names are deliberately host-supplied because two-character abbreviations may not be indexed; these cases do not establish abbreviated city resolution. The host verifies country identity on a bounded returned list rather than assuming the first search candidate belongs to the requested country. For each case two real HTTP 200 responses must be structurally verified, geocoding original ID and WGS84 lat/lon checked and then passed through observed projected SchemaRouter results into the second typed plan, weather time/finite Celsius number verified. One failed/missing provider response fails the run and earns no task success. Exactly six invoker observations are expected.

The output contains **only aggregate call counts, coarse pass markers, language labels, source host names, and latency**. No raw provider messages, user-provided content, coordinates, temperatures or source secrets are published. No synthetic HTTP responses are used in the actual external job.

An independent **offline** suite with `httpx.MockTransport` tests the same router/executor against source-shaped responses, missing input, wrong country, malformed numeric values, and two-step source-state carry. It is expressly no-model E0 engineering regression, **not** real-provider evidence.

## Interpretation

A successful workflow attests to actual API-to-API source-validated **2-hop transport/field/state interoperability** in GitHub Actions Linux CPU without a fake fixture, which was previously missing in the agent evaluation workstream. It **does not** attest model-selected tool IDs, decoded input arguments, agent final answer, independent authored ground truth, native third-party agent integration, EN/KO/JA free-text routing, host-principal hidden fields or supported vs unsupported classifiers. If provider is unavailable or usage terms change, the live run can fail and must not be silently replaced by a fixture; official APIs are not a pinned dataset. It does **not** change installed product dependency, policy or runtime API. This E1 live-source smoke does not satisfy A02 independent E2 or count among the #1346 **0/19** accepted cases.

Next genuine step remains a prospective independent original provider/task-author-reviewed user request and exact factual answer with actual agent-generated two-step plan/arguments/observations, EN/KO/JA, protected policy and hidden E2 test. v0.18 #1356 and default promotion remain HOLD.
