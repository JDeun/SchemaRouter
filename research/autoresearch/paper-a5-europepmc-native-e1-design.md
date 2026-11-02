# Europe PMC native original-paper P2/A5 E1 — design and implementation plan (2026-10-27)

Issue: #1769; stack onto Draft #1768. Research-only, no release authority.

## Gap and source contract

`research_public_heterogeneous_live_e1.py` calls Europe PMC by hand, outside
SchemaRouter's registration, original `Understand(q)`/P2, authorization and A5.
The published Europe PMC REST search GET endpoint accepts a `query` parameter,
an explicit `format=json` parameter and `pageSize`. The response supplies an
integer `hitCount` and a nested `resultList.result` array with per-record `doi`
and `id` keys. These are provider-declared locations; there is **no** top-level
`doi` scalar in the original response. Official service documentation:
https://europepmc.org/RestfulWebService. Existing keyless heterogeneous test
fixture is an additional locally inspected source-shaped reference.

## Design

1. Add an opt-in built-in Europe PMC HTTP/JSON ToolSpec declaring only a
   readonly `GET /search`, **three required host-owned query parameters**
   (`query`, `format`, `pageSize`) and typed paths for `hitCount`,
   `resultList.result[*].doi`, `resultList.result[*].id`. Require all three
   parameters in the *local* closed schema so P2's existing G5 scalar host
   argument mechanism can pass exactly one fully reviewed source envelope.
2. Local inspection produces fingerprint, base URL and visible field list;
   separate explicit approval verifies the exact curated schema, pins origin,
   assigns bounded host-reviewed field semantics, and binds the existing native
   HTTP/JSON invoker. No silent registration or automatic schema approval.
3. The invoker wrapper accepts only `query=DOI:<host-validated DOI>`,
   `format=json`, `pageSize=1`; source `hitCount>0` is insufficient: require
   one **matching** canonical DOI and a nonempty source `id` in the nested
   result array before returning the source response for normal field
   projection. Since the Europe PMC unquoted query parser has search operators,
   reject DOI metacharacters and use a conservative `[A-Za-z0-9._/-]` suffix
   subset for this E1 pilot, rather than claiming all standards-valid DOI
   punctuation is supported. No fake identifier or graph-join edge; DOI array field is
   explicitly **not** marked `identifier=True`.
4. A scripted research-only `Understand → P2` runner uses an EN/KO/JA
   host-owned concept, a deliberately forged model argument, native scoped
   A5 execution, and checks the *projected* original nested DOI and count.
5. Add source-shaped mock regressions: normal, forged argument, stale source,
   empty/mismatched source identity, malformed nested array, wrong content
   types, query boundary, and no I/O before approval. Add manual-only public
   `probe/run` workflow and automatic mock tests.

## Boundaries and validation

- Source owner schema and license are not independently signed or licensed;
  approval label remains `source-license-unverified-research-only`.
- `hitCount` is upstream search hit count, **not** a verified DOI-match count.
  The E1 receipt proves at least one matching result in the fetched page.
- No LLM-derived DOI values, no arbitrary search query, no implicit executor
  permission and no independent model E2 claim. Less common DOIs containing
  punctuation outside the explicitly supported literal subset fail closed.
- Implement in order: **RED** source/schema and A5 test → registration/profile
  and runner **GREEN** → abuse/revocation tests → lint/types/native regression →
  independent review → publish exact-tree stacked Draft PR and check CI.
