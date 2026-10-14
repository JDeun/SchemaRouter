# ClicShopping version4.33 — offline development comparison

Status: **preregistered development fixture; not a held-out, external, or production result**. Parent issue [#1208](https://github.com/JDeun/SchemaRouter/issues/1208).

## Authoritative source

- Upstream commit: `3bac851759234a4babb49d3f351e472cd9e0f31f` on `version4.33`.
- `source-inventory.json`: exact public PHP file paths, Git blob SHAs, read/write whitelists, overlapping action identities, and documented source gaps.
- `dev-cases.json`: 32 synthetic queries authored before any measurements (21 supported, 4 forbidden, 3 unsupported, 4 ambiguous); role contexts and scoring boundaries.
- The native source is REST `?mcp&<Endpoint>&action=...` endpoint/action metadata. It does **not** publish a directly comparable MCP JSON-RPC `tools/list` / `inputSchema`.

The pinned tree has no `CustomerOrders` Page, although `CustomerOrdersPermissions.php` declares five actions. Those **cannot** be treated as confirmed callable routes. `CustomersProducts` declares zero writes; `DISPLAY_BROWSER_JSON` controls direct GET reachability, not action existence. `ChatRagBI` only admits a read-only principal.

## Execute locally

```bash
python scripts/validate_clicshopping_v433_inventory.py
python scripts/run_clicshopping_v433_dev.py --out /tmp/clicshopping-433-development.json
pytest -q tests/test_clicshopping_v433_inventory.py tests/test_clicshopping_v433_dev.py
```

The runner makes **zero** model calls and **zero** HTTP/API calls. It constructs a normalized public metadata catalog and applies upstream-declared permission scopes *before* either condition:

1. **Full eligible baseline:** expose the entire permission-eligible endpoint/action matrix. This is **not** an upstream ranking model or measured ClicShopping transport.
2. **SchemaRouter preselection:** rank that exact same local eligible catalog and expose at most `top_k=3` route contracts.

The route identity is the **(endpoint, action) pair**, never just the action string. Six product actions overlap between `AnthropicEcommerce` and `CustomersProducts`. The scorer records supported route recall, forbidden-route exposure, unsupported nonempty candidate diagnostic, ambiguity candidates, normalized JSON byte exposure, and hot local retrieval/serialization latency.

## Interpretation boundaries

- Normalized local metadata bytes are **not** native REST wire bytes or actual agent input-schema token counts.
- Full eligible baseline recall on supported examples is tautological; it is not an independent native routing quality score.
- No output-field ground truth exists in the published endpoint/action matrix; **field recall is not applicable**.
- The 32 authored cases are a **development example**, not held-out evidence. No changing their wording, labels, shortlist budget or enrichment after seeing output to manufacture a favorable result.
- No credentials, permission bypass, action execution, customer records, writes, or paid models.
- Any negative or null measurement must remain visible. The next independent confirmation set, if warranted, needs its own prospective freeze and provenance before scoring.


## Independent confirmation intake — prospective only

A separate `confirmation-plan.json` fixes the **original upstream source**
`3bac851759234a4babb49d3f351e472cd9e0f31f`, native eligible
endpoint/action-matrix controls and primary Top-3 **before any new scored
confirmation**. No new held-out cases exist in this branch.

The independent-author handoff and second-reviewer checklist are in
[`CONFIRMATION_REVIEW_PROTOCOL.md`](CONFIRMATION_REVIEW_PROTOCOL.md).
The linter now rejects prefixed and near-complete token-reordered copies
of visible development queries as well as exact/punctuation-normalized reuse,
and refuses changes to the rest of the frozen protocol (not just Top-K).
These conservative textual checks still cannot certify semantic independence.

`python -m scripts.validate_clicshopping_v433_confirmation` accepts an
externally authored candidate case package and rejects known reused
development IDs/queries, permission-scope drift, post-hoc K changes and
unverified `customerOrders` calls. Passing these mechanical tests
**does not prove true independent case authorship** or authorize scoring.
A distinct human reviewer must verify that the cases were authored without
viewing failed development rows, sign their semantic labels, freeze the
candidate SHA-256 and source bytes, and authorize a separate execution run.

The already observed 32-case development errors/unsupported behavior
**must not** influence the new held-out design. A later ClicShopping
`version4.33` revision containing a CustomerOrders page requires an
entirely separate source/permission/authentication protocol; this original
source freeze must not silently move. No customer credentials, native
HTTP calls, writes, or claims of field recall are permitted here.


## Maintainer-supplied 20-case holdout — distinct 8ada7f1 cohort

The later ClicShopping maintainer source pin `8ada7f1f392f3dd2800e825dac8d245dfd53944a`
and new `cs-h01`…`cs-h20` cohort belong to [issue #1311](https://github.com/JDeun/SchemaRouter/issues/1311),
**not** the original `3bac851` DEV or the prospective confirmation input above.

See [`MAINTAINER_HOLDOUT_INTAKE.md`](MAINTAINER_HOLDOUT_INTAKE.md)
and `python -m scripts.inspect_clicshopping_maintainer_holdout --help`
for the read-only verbatim-byte/ID validation gate. The original upstream JSON
bytes, declared digest convention, permission/route gold labels, human signoff
and any scored comparison remain unverified. A successful structural lint
does not grant independent confirmation or scoring authority.

## Repinned 8ada7f1 visible DEV preflight — source and protocol identity (#1208)

The separate source-repinned, **visible DEV-only** script
`scripts/run_clicshopping_v433_repin_dev.py` now fails closed before
measuring either arm if the transition manifest changes the exact verified
`CustomerOrders.php` path/Git blob SHA or the corrected public route
declaration path/Git blob SHA/target. It draws the frozen public identities
from the *same code constants* as the standalone pinned-upstream source
auditor; it does **not** fetch or execute the upstream source at runtime.
The independent Git checkout/source-byte audit remains a distinct
prerequisite for actually verifying upstream files.

The new cohort must also preserve literal integer `top_k=3` and
`hot_repeats=5`, integer-zero model/HTTP activity, strictly disabled
credential/PHP/model/held-out execution and all Boolean role grants.
Python `True == 1` and `False == 0` must **not** pass these numeric
checks. Duplicate, malformed or non-list required/forbidden/ambiguous
route labels and forged count types are rejected before ranking.
Regression tests mutate only synthetic in-memory copies of the original
frozen fixture and verify the genuine 32+10 DEV control still runs.

**No change to the 42 original DEV queries/labels, the original
source SHA manifests, the 8ada7f1 independent-holdout #1311 intake,
or the already disclosed DEV results.** The permission-filtered full
baseline is still an offline REST endpoint/action exposure matrix, not
ClicShopping's actual ranking algorithm. These checks neither prove
runtime `customers_id` tenant safety nor grant independent human review,
score new held-out cases, call PHP/HTTP or validate native REST latency.
