# Independent original-provider E2: source-neutral **unscored** intake preflight

**2026-10-18 · issue #1346 → #1477 / #1510.** Existing provider-specific ClicShopping verbatim raw gate stays canonical for its upstream submission. This general-purpose tool adds *only* source-byte, cohort and obvious overlap checks needed before a prospective native EN/KO/JA heldout can enter a separate reviewer process. **There is no newly received externally authored case or verified E2 result.**

## Private file contract

Supply four **unaltered** local UTF-8 JSON files (never commit these files, original queries, provider outputs, private gold, credentials or manifests containing unreleased identifiers):

1. `manifest.json`: exact fields `schema_version=1`, `intake_kind="unscored_native_e2"`, `provider_repository="owner/repo"`, `provider_commit` (40 lowercase hex), `native_tool_inventory_sha256`, `case_bytes_sha256`, `gold_bytes_sha256`, `development_bytes_sha256` (all 64 lowercase hex), `split_id`, `case_author`, `gold_reviewer`, `license_spdx`, `source_permission_review="pending"|"attested"`, `case_language_origin="publisher_original_not_translated"`.
2. `cases.json`: object with exactly `cases` array. Every case has `id`, `language` (en/ko/ja), `query` (original publisher-authored request, not a translated duplicate), `role` (authorization principal/profile) and `expected_kind` (supported, unsupported, required_input_missing, ambiguous, opaque_unavailable).
3. `gold.json`: object with `cases` array; each record has the same `id`, `role`, `expected_kind`, `native_authority_sha256`, `gold_reference_sha256`. These **hash references are claims only**: this preflight does not fetch or validate their source, prove permission, or score correctness. Store original provider/field/argument/final-answer oracle outside the repo for independent review.
4. `development.json`: object with `cases` array of `id`, `query` for previously exposed DEV requests. The checksum binds the screened snapshot. Supplying an intentionally incomplete DEV inventory invalidates any overlap conclusion and must be caught by the independent reviewer.

For predictable local resource use, each case/gold/DEV collection is capped at **256 rows** and each request at **2,000 characters**. Oversized cohorts must be partitioned into separately frozen, independently reviewed splits, never truncated silently. These conservative bounds prevent the intentionally simple near-copy screen from becoming an unbounded quadratic workload.\n\nThe program requires source/gold/dev byte hashes to match literally; duplicate JSON keys and nonfinite constants are rejected, including numeric exponent overflow. BOM, size excess, non-UTF-8, absent/extra keys, duplicate/overlapping IDs, incomplete EN/KO/JA × 5-class strata, gold identity/role/expected-label conflicts and exact/obvious near-copied DEV requests fail closed.

Run the structural-only preflight locally, with paths outside the checkout:

```bash
python -m scripts.inspect_independent_native_e2_intake \
  --manifest /secure/e2/manifest.json \
  --cases /secure/e2/cases.json \
  --gold /secure/e2/gold.json \
  --development /secure/e2/development.json
```

The report contains **counts by language and expected kind**, and flags. It contains **no original query, individual ID, route names, role, gold, HMAC key, raw model text or provider results**. Every accepted report *still says* `scoring_authorized=false`, `independent_e2_qualified=false`, `qualification_gate=BLOCKED_EXTERNAL`. This is a *minimum structural barrier*, never a reviewer receipt.

## What this deliberately cannot certify

- Manifest strings and SHA-like references are **untrusted self-declarations**; byte-equality does not prove the publisher's true origin, ownership, case author, split timing, license permission or native source.
- This lexical duplication screen cannot detect multilingual semantic translation, paraphrases, hidden prompt tuning, task/author contamination or a withheld earlier DEV corpus.
- Matching case/gold IDs and expected labels is not validation of source-native acceptable routes, required input/output fields, side effects, actual principal scopes or independent final-answer oracle.
- `source_permission_review="attested"` is not a cryptographic signature or authority to call a third-party provider. There is no model or original provider execution and no live scoring.

Before moving beyond `BLOCKED_EXTERNAL`, obtain **original upstream exact case bytes and provenance**, publisher consent/eligible license, independently signed task+gold and permission/source review, complete frozen DEV+confirmation split/reuse audit, true native provider route/field/operation verification, and a **separate approval** to execute paired model/agent E2 with correct stage/final oracles and host authorization. The canonical [qualification control](../../QUALIFICATION.md) and 19-row matrix, including the held v0.18 release, remain unchanged.

## CI safety

[Isolated GitHub Actions](../../.github/workflows/research-independent-native-intake.yml) runs *synthetic test objects only*, and reuses the existing ClicShopping special-purpose byte-audit tests. No private real dataset is downloaded or uploaded; 0/19 E2, A02/R05 NOT_VERIFIED and #1356 release/default model promotion HOLD.
