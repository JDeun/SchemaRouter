# #1444 — Conjunctive typed OpenAPI host-oracle verification (DEV, source-locked)

## What has been demonstrated before this experiment

Merged [#1443](https://github.com/JDeun/SchemaRouter/pull/1443) verified **one** host-author-specified `(parameter, enum-value)` against the **actual current authorized** Open-Meteo `CapabilityCandidate.parameters[].json_schema`, using frozen E5 Small rank lists. From 27 author-written supported EN/KO/JA questions, it selected only **9/27** (all correct), abstained on **18/27**, and selected **0/12** author-labeled unsupported modifications. This is an *oracle upper-bound exercise*, not a real query classifier or authorization study.

The original provider OpenAPI documents (source `open-meteo/open-meteo@b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4`, provider attribution CC BY 4.0) show that `hourly.wave_height` appears in multiple APIs, and `hourly.ocean_current_velocity` also appears in multiple APIs, but the conjunction is supported uniquely by the *marine* schema in the nine published GET operations. The pre-existing English/Korean/Japanese marine questions explicitly ask for wave height **and** currents. Other source questions remain bound to the prior exact single variable, including ambiguously shared `hourly.temperature_2m` and an absent contract for elevation. **This conjunction is a post-hoc hypothesis motivated by observed same-author questions**, so success is **not** independent generalization or a validated host schema-intent extractor.

## Predeclared algorithm

The new pure `select_conjunctive` accepts only a **host-supplied, bounded nonempty tuple of 1–4 exact (query parameter, enum value) pairs** with no duplicate, malformed or padded strings. It sees only the current `SchemaRouter.retrieve_authorized(..., principal=simulated_viewer, k=9)` typed candidates; no registry bypass, free-text semantic guesses, gold lookup, or optional score thresholds. Each candidate must be `read_only is True` and its exposed `ParameterSpec.json_schema.items.enum` must **contain every requested value**. The function:

- **selects** only with exactly one matching authorized route;
- **abstains** when zero/more than one route matches all pairs;
- **denies** all non-read operations, missing host requirements or untrusted rank identities; and
- **never** calls a provider, creates an execution plan, or promotes a model selection into authority.

## Immutable source comparison

The read-only Ubuntu CPU Actions fetches previous **successful** real original E5 + enum gate [run #38864540058](https://github.com/JDeun/SchemaRouter/actions/runs/38864540058) artifact `real-openapi-enum-host-dev-38864540058`, verifying:
- 39-source-case single-field `enum-verification.json` raw SHA-256 `e3945b0f8eba04370b0bec802dad36483c4ac9e249da6e57434318d829dcfbe1`
- 36-source-case actual E5 rank `report.json` raw SHA-256 `b8fc826397c0385d2b59b5968d3b7f53a2433f7327a8a3679168ecb7127ff038`
- nine original provider Git blob SHAs and unchanged old per-case outputs (rerun the original verifier before comparison).

Evaluate the exact same 27 supported + nine unsupported original cases plus three deceptive writes with valid marine wave/current enums = 39 source-bound DEV cases. Measure E5 Top-1, old strict one-field correct/abstained, new conjunction **unique correct, unique wrong, ambiguous, missing**, each language, and unsupported selected. Preserve full case results and all original source files. No new E5 inference or hosted API. Product code unchanged.

## Hard scientific constraints

Even if this recovers three marine queries, it must still abstain on common forecast/ensemble/historical `temperature_2m` without a reliably sourced domain/time requirement. Do not fit additional variables by looking at gold/held-out outcomes and then call the result generalizable. All user operation/variable pairs here are manually authored **oracle inputs**; no multilingual query intent extraction, production host authentication, actual data-field value guarantee, real remote execution or agent completion proven. Negative writes supplied as `action=write` are trivially denied on a read-only catalog; they are **not** independent no-fit classification successes.

**Acceptance:** all protected CI/CodeQL and exact-source CPU tests pass; report both *coverage and mistakes*; keep #1339/#1346 open, original frozen #432 independent KO/JA negative evidence unchanged, and v0.18 release #1356 HOLD.
