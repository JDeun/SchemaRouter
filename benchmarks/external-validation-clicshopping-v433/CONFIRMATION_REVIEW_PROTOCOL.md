# ClicShopping 4.33 — independent confirmation handoff

**Status: authoring/review instructions only.** No new held-out corpus, external
review signature, live customer endpoint execution or performance result exists.

## Fixed control

- Original public source commit: `3bac851759234a4babb49d3f351e472cd9e0f31f`.
- Native baseline: permission-eligible **REST endpoint/action matrix**, not
  MCP `tools/list`, an agent, or ClicShopping's own ranking algorithm.
- Paired comparator: SchemaRouter `Top-3` on exactly that same eligible catalog.
- Comparison method, local JSON byte definition, repeats, metrics, permission
  roles and no-network/no-model conditions remain identical to the existing
  prospective `confirmation-plan.json` and source-audited development protocol.
- CustomerOrders permissions alone cannot grant a callable route at the pinned
  source. No live customer identifiers, credentials, writes or authentication
  experiments are authorized.

## Author handoff — before any confirmation scores are opened

1. An **independent case author** who has not consulted development per-case
   misses creates a *separate* UTF-8 JSON case file. Do not prepend a phrase to
   the original 32 queries, rewrite their order, or merely paraphrase them.
2. Source for acceptable route labels is the pinned, public endpoint/action
   and permissions snapshot. The author must explain the meaning of each
   `(endpoint, action)` pairing and role without receiving ranker outputs.
3. Record a source-method note and independently authored task provenance.
   Keep supported, unsupported/OOD, ambiguous and permission-forbidden
   negatives. Do not convert difficult examples to another label after scoring.
4. Run the **unscored input linter** before submitting the candidate:

   ```bash
   python -m scripts.validate_clicshopping_v433_confirmation \
      --plan benchmarks/external-validation-clicshopping-v433/confirmation-plan.json \
      --candidate /path/to/unscored-confirmation-cases.json \
      --dev benchmarks/external-validation-clicshopping-v433/dev-cases.json \
      --inventory benchmarks/external-validation-clicshopping-v433/source-inventory.json
   ```

5. The linter conservatively rejects exact/punctuation-renormalized,
   prefixed/embedded and near-complete token-reordered copies of visible
   development queries. Some genuine queries may be flagged; clarify them
   **before** study freeze. Passing does **not** prove semantic independence.
6. A **different human reviewer** independently checks author independence,
   source provenance, task-label relevance, the six overlapping Products vs
   CustomersProducts actions, negative permissions, cohort/hash coverage and
   all protocol settings. A single author cannot self-attest both roles.
7. Independently freeze the source hashes, candidate JSON SHA-256 and reviewer
   decision **before** any confirmatory scoring. Record the reviewer's
   non-approval as a blocker when independence is not established.

## Evidence tiers

| Tier | Meaning | Status |
|---|---|---|
| Existing 32-case DEV | Locally authored visible development results | Complete, not independent |
| Candidate intake | File accepted by mechanical linter | No new candidate supplied |
| Human author + independent reviewer | Semantically checked and SHA-frozen fresh confirmation | Pending |
| Confirmatory offline paired run | Accepted only after separate author/review freeze | Not authorized |
| ClicShopping maintainer feedback | Discussion of observed results, including failures | Pending new confirmation |

The measured `normalized JSON bytes` are **not** native REST-wire bytes.
Retrieval latency is local and not end-to-end task latency. No output-field
recall is measured. Negative or unsupported outcomes must remain visible.

## Governance

This handoff can be merged before any future confirmation dataset is written.
It does **not** change the frozen 0.14 experiment's inputs, thresholds,
evaluators, model or action authorization policy. Passing this checklist,
or re-running the old development cases, never authorizes a held-out claim.
