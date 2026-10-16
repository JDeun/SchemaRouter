# #1346 — Actual published OpenAPI enum capability verifier with *host-oracle* request contracts

## Exact evidence and motivation

The merged [#1441](https://github.com/JDeun/SchemaRouter/pull/1441) evaluated actual local multilingual E5-small on nine original Open-Meteo OpenAPI 3.1 documents and achieved Top-1 **23/27**, Top-5 **26/27** on author-written EN/KO/JA development queries, under default-deny simulated Viewer. Merged [#1442](https://github.com/JDeun/SchemaRouter/pull/1442) compared extra publisher parameter and output text: both increased Top-5 to **27/27**, yet worsened Top-1 **23→20**, proving more text is not sufficient for choosing an executable route.

Actual source-based provider contract inspection finds discriminative **query parameter enum values**: marine `hourly.wave_height`, flood `daily.river_discharge`, air-quality `hourly.pm2_5`. Other values such as `hourly.temperature_2m` occur in multiple distinct forecast/ensemble/historical contracts, and should **not** be treated as sufficient proof of which tool fits.

## Precise diagnostic contract

This PR computes a fail-closed **read-only capability verifier**, over *only* current `SchemaRouter.retrieve_authorized(...,simulated Viewer,k=9)` results. It uses the nine original published Open-Meteo YAML files (publisher `open-meteo/open-meteo@b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4`; Git blob SHAs checked), and the **already measured unchanged real E5-ranked candidates** archived at [Actions #38863136350](https://github.com/JDeun/SchemaRouter/actions/runs/38863136350) [artifact #12029847264](https://github.com/JDeun/SchemaRouter/actions/runs/38863136350/artifacts/12029847264), original exact `report.json` SHA-256 `b8fc826397c0385d2b59b5968d3b7f53a2433f7327a8a3679168ecb7127ff038`. No new model inference, model training, remote provider execution, or mutable inputs.

**Host-oracle assumption:** for each *already authored* case, we explicitly supply an expected action (`read` vs unsupported mutation) and desired `(query_parameter,enum_value)` pair. This is researcher-authored and sometimes more precise than the source query. **No query-to-variable classifier is built, validated or assumed accurate.** The verifier does not use gold route identity, question text, user labels or route names for matching. It only checks whether a currently authorized, read-only `CapabilityCandidate.parameters[].json_schema` has the requested exact OpenAPI enum value.

Selection policy: **select only if exactly one authorized endpoint matches.** No matches means abstain. Multiple matches (common weather variables) means **abstain**, even when original E5's first-ranked endpoint matches. Absent request variables (elevation) mean abstain. A requested mutation rejects all read-only endpoints **even if the exact variable exists**. This tests one narrow trust boundary without inventing confidence scores, operation fit or user-host authorization. The policy is intentionally conservative; coverage may be low.

- 27 real-E5-ranked supported author-written cases, 9 unsupported cases, plus 3 **deceptive negatives** requesting mutation of a valid `hourly.temperature_2m` variable → **39 total**, all EN/KO/JA.
- For every row verify exact authorization-bound route identities from the current public API, E5 original rank permutation and source report SHA, provider Git blob identity, schema enum types and operation (read-only flag).
- Record correct unique selections vs wrong; ambiguous and missing abstentions separately, negatives incorrectly selected, complete route shortlist, source SHA provenance. **Do not sum ambiguous abstention with false routing.**
- All model output is **fixed historical developer data**, not independent queries or a calibrated no-fit test; host requests are an *oracle* not inferred in production.
- No actual provider tool called, no real principal authentication, no agent task completion, no product code changes, no default switching and no v0.18 release.

## Acceptance of experiment, not promotion

1. Source-locked read-only Ubuntu Actions workflow, 15-minute cap, 39 original rows exactly, nine authentic source hashes and frozen original E5 report hash checked.
2. Fail-closed tests for valid unique variables, shared-enum ambiguity, absent contracts, denied mutations and unauthorized route permutations. Strict full CI/CodeQL before merging even research-only.
3. Report both the **recoverable subset** (unique declared variable) and **unresolved subset** (no or shared variable). Even 100% precision within a small selected subset would **not** justify product adoption without measuring coverage and a genuine real-user host-intent parser. No threshold fitted or no-fit FPR claimed.
4. Next separate prospective evaluation needs provider-disjoint independently annotated user intent/domain/field needs and fixed-agent denied/no-call tests with genuine host principal and permissions. #1339/#1346 OPEN; frozen #432 independent KO/JA negative and v0.18.0 #1356 HOLD.

Open-Meteo original documents attributed to Open-Meteo, CC BY 4.0; no claim of affiliation.
