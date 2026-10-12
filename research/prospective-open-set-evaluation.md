# Prospective open-set retrieval audit (unscored)

**Status: offline diagnostic tooling only. Not an independently reviewed
benchmark and not a calibrated recommendation.** Follows [#1291](https://github.com/JDeun/SchemaRouter/issues/1291).

The merged opt-in `RetrievalAbstentionPolicy` / `apply_retrieval_abstention`
does **not** alter the default `retrieve()` result, authorize executions, or
automatically refuse unsupported actions. Historically exposed ClicShopping
DEV requests still returned nonempty Top-3 in **4/4** unsupported cases;
using those published queries or their observed scores to choose a threshold
would be post-hoc tuning.

## Preregister inputs before running

`scripts/audit_prospective_no_match.py` requires three independently supplied
immutable JSON documents and **both already-published DEV query files**:

- `plan.json`: exact schema version 1; `status:
  unscored_prospective_draft`, `approved: false`; pinned source/scorer Git
  SHAs and registry SHA-256; `top_k >= 2`; exact preselected policy
  (`min_score`, optional `min_margin`) from a **distinct calibration
  source**, with no threshold fit inside this program; SHA-256 of the
  prospective case cohort.
- `cases.json`: `schema_version: 1`, `role: prospective_unreviewed`, a
  nonempty list of separately authored case IDs, normalized query SHA-256,
  labels `supported/unsupported/ambiguous/forbidden`, expected and forbidden
  candidate route IDs. No task gold, model conclusions or post hoc outcome
  fields. The checker rejects historical 32+10 visible DEV IDs and exact
  normalized-query hashes, as well as duplicate new queries.
- `observations.json`: `schema_version: 1`, exact canonical plan and case
  SHA-256, and one row per new case with the **real
  `CapabilityRetrieval.model_dump(mode="json")`** snapshot and separately
  observed retrieval milliseconds. No extra scores, gold fields or invented
  candidates in an observation row.

Run without any model tool execution:

```bash
python scripts/audit_prospective_no_match.py \
  --plan scratch/plan.json \
  --cases scratch/cases.json \
  --observations scratch/observations.json \
  --known-dev benchmarks/external-validation-clicshopping-v433/dev-cases.json \
  --known-dev benchmarks/external-validation-clicshopping-v433/visible-dev-repin-cases-8ada7f1.json \
  --out scratch/unscored-open-set-audit.json
```

The output reports baseline vs opt-in selected supported route hits;
**false refusal** when a supported route was found before abstention and
discarded; raw vs selected nonempty unsupported replies; ambiguous route
survival; forbidden route exposures; reasons by case; candidate object JSON
metadata bytes and median/p95 **supplied** retrieval timings. Both raw and
post-policy routes stay within the passed retrieval scope. No changes to
frozen 0.14, published 42-case ClicShopping DEV reports, Tool permissions,
live PHP/REST endpoints, model prompts or official benchmarks.

The result is marked `UNSCORED_NOT_INDEPENDENTLY_VERIFIED` and `approved:
false`. An externally fixed numerical threshold does not prove its author
is independent, the labels are correct, candidates are authentic, latency
measurements are representative, the scoped candidate set is authorized,
or the split is semantically independent (paraphrases may escape exact-hash
screening). A future **independent reviewer** must verify those conditions
and approve a distinct held-out execution protocol; never interpret a
positive synthetic result as ClicShopping validation. The audit does not
measure abstention computation time, native REST traffic, agent execution
or end-to-end task success.

Run synthetic local regression tests:

```bash
python -m pytest -q tests/test_audit_prospective_no_match.py
```
