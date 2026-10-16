# Exact frozen-incumbent comparison — V1 vs V2 (retrospective DEV)

Parent [#1412](https://github.com/JDeun/SchemaRouter/issues/1412).

## Why this comparison, not another random search

The completed V1 GitHub Actions-only chain ran **12 batches, 275
configurations** and preserved a research incumbent in [Actions run
#38828196450](https://github.com/JDeun/SchemaRouter/actions/runs/38828196450),
artifact **12015752983**. V2 [PR #1420](https://github.com/JDeun/SchemaRouter/pull/1420)
evaluated nine joint-width/weight settings in [Actions run
#38828191428](https://github.com/JDeun/SchemaRouter/actions/runs/38828191428),
artifact **12016545301**. Its reported +9 DEV-fit improvement used
the *unmodified* K24 planner as the comparator, **not the final V1
incumbent**.

The actual `state.json` and `report.json` in those downloaded ZIP
artifacts were inspected, including their SHA-256 content digests,
source Git SHAs, DEV corpus SHA and the constrained weights. The
reviewed `benchmarks/autoresearch-v1-v2-frozen-incumbents.json`
pins these exact values so that GitHub's artifact retention expiry
does not make a research rerun impossible. The manifest is a snapshot,
not a claim of independently audited third-party attestation.

V1 reranks actual registered **K24** candidates. V2 reranks **K64**
candidates. The public current `SchemaPlanner.retrieve(k=24/64/128)`
is called separately on the **same** 100/250/500-route catalogs and
the **same** EN/KO/JA/ES/DE/mixed case rows; actual CPU retrieval
time for each width is measured independently. The full comparison
uses **all 240 previously exposed V5 synthetic DEV tasks per catalog**.

Per K3/K5/K10 and language/catalog cohort, we report actual required
registered-route recall, required multi-route FullCoverage, selected
schema bytes, request p95 and source/fixture fingerprints. Raw
case-level disagreements (without filter or cherry-picking), along
with the existing reviewed `decide()` regression guard, are stored
in the artifact. A positive aggregate gain **never masks** per-language
or per-catalog/K regression in the research decision. No model
receives route gold or can invent registered capabilities.

## Scientific and authority boundary

**Both V1 and V2 were tuned using this exact exposed synthetic
generator.** A retrospectively repeated case, including any
previously unseen case *row* from the same generator, cannot
qualify as a new independent test. Therefore a positive paired
comparison proves at most that V2 outperforms V1 **on known
synthetic DEV**, not that SchemaRouter is optimal, safe in live
service, or ready to replace production ranking.

Candidate generation may still miss needed registered routes
beyond K64; host authorization and typed execution contracts still
own tool selection and execution permissions. The comparison does
not invoke any tool or agent, evaluate host/user authentication,
check required field gold, or use the #432 independently frozen
heldout. Neither passing this report nor finding a DEV incumbent
can merge production optimizer code, certify v0.18 or restart
an unlimited research chain. Historical release gate remains HOLD.

## Reproduce on GitHub Actions Ubuntu CPU

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_v1_v2_paired_cpu_dev.py
python -m scripts.research_v1_v2_paired_cpu_dev \
  --cases-per-group 5 \
  --output artifacts/v1-v2-paired-cpu-dev/report.json
```

The next separate confirmation should be a **new truly disjoint
real-source evaluation**, with principal/field visibility and
end-to-end fixed-agent FULL/SR-K/SR-PROGRESSIVE/ORACLE outcomes.
Only after that should a broader V2 Actions self-search policy be
reviewed for use beyond the exposed DEV research sandbox.
