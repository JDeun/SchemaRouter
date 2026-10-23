# Real local Qwen3 generated native Open-Meteo two-hop tasks (E1 public DEV)

**2026-10-18, preregistered before first actual model inference.** #1477 depends on #1346.

## Purpose and prior contrast

[PR #1521](https://github.com/JDeun/SchemaRouter/pull/1521) confirmed actual source-provider HTTP geocode → weather, 3/3 host-selected EN/KO/JA inputs on original API, six real calls. Because the host supplied the routes and both argument maps, that did NOT demonstrate autonomous agent tool use. This follow-up keeps the **same original live provider / SchemaRouter router** but now requires the *pinned local Qwen3-0.6B* to actually generate:
1. first route and precise input `name`, `language`, `country_code`;
2. second route and **exact source-observed** first-output `latitude`, `longitude`; and
3. a correct final JSON `{"temperature_2m":number,"unit":"°C","observed_at":string}` copied from observed second-stage actual weather result.

Host enforces registered sequence and exact first-observation grounding, **never repairs a model proposal**. These checks are evaluation acceptance and cannot authorize actions. **First negative integration result:** The original `execute_scoped_host_call`
used only automatically planner-selected output fields. The real geocoding
operation returned HTTP 200, but its model-visible projection contained
**neither latitude nor longitude** (`lat0_lon0` presence diagnostic);
therefore the first API step could not feed the second. Ignoring that
failure or copying unprojected provider data into model context would
invalidate the security boundary. We instead extended the *existing*
research-only scoped host invocation API with an optional
`host_required_output_fields: tuple[str,...]` contract. It accepts only
unique original source field names positively present in the CURRENT
principal-scoped capture, keeps the planner's original fields, and
requires the host's additional listed fields before invoking the SAME
native `router.execute` + post-execution scoped projector. The model
cannot add fields, and any hidden, nonregistered, duplicate or invalid
host-output contract fails closed. Host requires
`(latitude, longitude)` at geocoding and
`(time, temperature_2m, temperature_unit)` at forecast. No returned
coordinates are inserted into the model answer by the host. The earlier
no-model negative E0 tests are still negative outcomes, not omitted cases.

The two routes are registered read-only via `SchemaRouter.add_bound_tool`, never supplied as a fake outcome. Native original provider I/O only happens after `execute_scoped_host_call` revalidates a fresh principal-scoped source view, original route identity, schema, permission, tool fingerprints and Model-visible output projection, then executes using the existing registered bound invoker. API request URLs are fixed trusted Open-Meteo domains with no user/model hostname injection, no mutation, no credential, no redirect. No new agent executor, routing core, or library dependency is added.

**Use exactly the existing parser** from `scripts/research_real_qwen_bound_two_step_e0.py::parse_one_model_action` to disallow partial/multiple tool calls, duplicate JSON keys, unsafe complex/nonfinite args. Use the existing `append_authorized_nous_user_history_e0` to transmit only previously validated public observations as upstream-aligned Qwen Nous assistant/tool-response history. Generator: existing `LocalQwenAgent` from `scripts/agent_utility_v7_dev_agent.py`, `Qwen/Qwen3-0.6B` @ `c1899de289a04d12100db370d81485cdf75e47ca`, float32 Linux CPU greedy, up to four turns, max 256 output tokens per turn. Neither hidden gold, native executor callable nor private credentials are model inputs.

## Fixed and exposed cohort

Three **researcher-authored, exposed DEV** requests:
- EN Seoul, source-indexed `Seoul`, `language=en`, `country_code=KR`;
- KO 서울특별시, source-indexed `서울특별시`, `language=ko`, `country_code=KR`;
- JA 東京都, source-indexed `東京都`, `language=ja`, `country_code=JP`.

The user prompt explicitly provides city and country/language tags so this does **not** measure geographic extraction or language detection. Zero independence, tiny disclosed cohort. No hidden E2. The tool catalog has only two read-only endpoints; this experiment doesn't measure 500-route candidate recall/no-fit calibration/irrelevant cases.

## Fixed metrics and handling failures

Per language, preserve number of attempted model calls, real successful first provider calls, real successful second provider calls, prematurely finalized/wrong-call/wrong-field or host-denied reason, exact source-final value equality, and strictly full task completed. **Full task pass = two real validated calls + correct final schema/value/time/unit**. Any premature final, forged coordinates, substituted city, invented operation, wrong order, missing arguments, malicious/duplicate JSON or weather mismatch FAILS, even if an unrelated host-operated script would have succeeded. No silent refill, retry or hard-coded factual answer.

No-model regression tests use `httpx.MockTransport` and a scripted generator to verify successful wiring and adverse paths. Those test results are E0 engineering only, not actual model competence. The separate GitHub Actions actual pinned model job calls the real public endpoints, without substituting fake responses.

## Evidence limitation

If the live API is temporarily unreachable or a Qwen model call is rejected by the host, do not replace its outcome with a positive or inject true coordinates into another attempt. Report exactly where it stopped. A successful run is **E1 EXPOSED MODEL+ORIGINAL_PROVIDER DEV**, not an independently authored/publisher-gold E2 sample, not a production benchmark or proof of multilingual generalization. No independent author, third-party approval, hidden case source, model baseline noninferiority, full candidate selection with 500 tools, authenticated data policy or side-effect approval assessment. Qwen short-context and small model can fail the strict terminal even if source APIs succeed. Save only privacy-safe counters and category labels (not original coordinates, time, temperatures, assistant text, inner arguments or prompts) in Actions artifacts.

No changes to core default routing or library public API. #1346 independent E2 **0/19**, A02/R05 NOT_VERIFIED, default/model promotion and v0.18 #1356 **HARD HOLD**.

## 2026-10-23 source-native G5 paired successor

The first actual frozen-Qwen FULL / lexical K5 / G5 paired run and its
source-transport-confounded negative findings are preserved in
[G5 paired E1 research receipt](g5-source-native-qwen-open-meteo-paired-e1-2026-10-23.md).
The original Actions artifact remains immutable. The successor comparison
explicitly separates provider HTTP availability failure from genuine
model continuation/final-grounding failure and records actual token counts
without altering this original single-arm E1 output contract.
