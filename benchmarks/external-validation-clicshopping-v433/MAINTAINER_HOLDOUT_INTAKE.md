# ClicShopping independent 20-case holdout: raw intake gate (#1311)

**Status: unscored, not independently adjudicated.** This is an offline intake
guard, **not** a retrieval result, a freeze, or permission to run a held-out scorer.

## Upstream claim and provenance

- Public provenance: [ClicShopping Discussion #91](https://github.com/ClicShopping/ClicShopping/discussions/91),
  maintainer comment `18864827`, dated 2026-10-11.
- Repo/source claimed: `ClicShopping/ClicShopping`,
  `version4.33@8ada7f1f392f3dd2800e825dac8d245dfd53944a`.
- **Maintainer-declared**, not yet independently rederived, digest:
  `a4a3a9d1b9ef6899ca863810247c9709b4b92f8d492fcb866845052db4e7a8f0`.
- Source declares `cs-h01`…`cs-h20`: 12 supported, 3 forbidden
  under a read-only profile, and 5 unsupported.
- Gold-label authority, original **verbatim bytes**, serialization convention,
  independently audited alternative routes and labels remain **unverified**.

## Safe use

1. Capture the **unaltered** UTF-8 JSON attachment/body supplied by upstream.
   Preserve original bytes outside the source tree until their public reuse
   status is clear. Do not manually normalize whitespace or edit source fields.
2. If and only if the upstream JSON object contains a literal `cases` array
   of 20 entries with `id` and `query`, use this read-only scanner:

   ```bash
   python -m scripts.inspect_clicshopping_maintainer_holdout \
     --raw /path/to/verbatim-upstream-holdout.json \
     --json-out /tmp/clicshopping-holdout-intake-unscored.json
   python -m pytest -q tests/test_clicshopping_maintainer_holdout_intake.py
   ```

3. The scanner rejects duplicate JSON keys, nonfinite JSON constants,
   invalid UTF-8/BOM, duplicate/out-of-cohort IDs, empty query strings, and
   explicitly conflicting source-commit fields. It computes SHA-256 of the
   **literal file bytes** and two **candidate** canonical serializations.
   These are three separate hashes; matching any one does **not** establish
   which convention the maintainer used.
4. If the upstream JSON structure differs, **do not transform the canonical
   source just to satisfy the linter**. Update the parser in a separately
   reviewed adapter with a fixture showing the exact upstream format; keep
   the original file and byte hash immutable.

## Deliberately unfinished gates

- Prove original upstream authorship and establish its authoritative JSON
  serialization/digest convention with the maintainer. `cs-hXX` class splits
  come from the *issue declaration*, not semantic inspection of gold labels.
- Review **all 20** query/profile/acceptable-route/forbidden-target records
  against source `8ada7f1`. The `read_only` profile permits only
  `select_data`; `read_write` permits `select_data`, `create_data`,
  and `update_data`; **delete is never authorized**. Alternative acceptable
  facade routes must count as correct without changing the original gold.
- Obtain a separate human/maintainer review of tool/action mappings and
  frozen source/protocol before scoring. The existing 32+10 cases and four
  unsupported DEV failures stay unchanged.
- Keep the Top-K=3 surface, independently set no-match calibration, and
  permissions fixed. **No cohort-derived threshold choice.** If the default
  returns candidates on an unsupported query, report that failure rather
  than silently suppressing it. Do not claim output-field recall without
  independent output-field gold.
- Only after these gates, create a separate scorer authorization and
  independently reproducible evidence package. No live tenant, customer,
  credentials, PHP, write, paid model, or destructive calls.

The checker permanently emits `scoring_authorized=false`,
`gold_routes_and_permissions_verified=false`, and
`digest_serialization_convention_confirmed=false`. Passing mechanical
syntax checks cannot be converted to an independent E2 validation claim.

This independent external-validation work does not touch frozen 0.14 #432/#424.
