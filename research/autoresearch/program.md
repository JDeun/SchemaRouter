# SchemaRouter research program — GitHub Actions CPU only

## Immutable infrastructure constraint

**The sole compute environment for research is public GitHub Actions Linux.**
There is no external coding agent, dedicated computer, paid model API, hosted
experiment process, GPU or persistent runner. Do not design around one.

The previous Karpathy-inspired code-editing proposal is superseded. The
current #1416 candidate-only subprocess remains a test infrastructure and
historical control, **not** an autonomous agent or a required code writer.

## What the automated system actually does

Workflow: .github/workflows/research-actions-only-cpu-search.yml

1. On main, recover the most recent successful research state from a prior
   Actions artifact, when retained and available. Check its scorer, source,
   corpus and algorithm hashes before accepting it.
2. Build **current** SchemaPlanner candidate pools from the existing
   six-language, 100/250/500-route synthetic typed DEV catalog.
3. Generate *new numeric configurations*, rather than executable Python,
   using seeded exploration, mutation and crossover of pre-reviewed rankers.
   Operators: base-position, lexical-token overlap, normalized trigram
   overlap, matching output-field semantics, endpoint identifiers.
4. Fit configurations against three previously exposed DEV cases in each
   language/stratum, then make a one-time check of candidate winners on
   the other two examples. No hidden or external independent holdout
   is opened. Do not leak labels into the ranking function.
5. Enforce route-ID permutation integrity and hard non-regression per
   catalog/language/K, together with bounded CPU time/latency and schema
   candidate payload cost. Only research configurations that improve
   Top-5 route recall without those regressions can become champions.
6. Upload report.json plus state.json for the next run, including negative
   attempts. Scheduled runs continue while budget, artifact retention,
   current source hashes and GitHub Actions availability permit.
7. Never edit src/schemarouter, benchmark gold, security guards or
   release configuration from a self-search run.

Run reproducibly on the checked-out source:

    python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
    python -m pytest -q tests/test_research_actions_only_search.py
    python -m scripts.research_actions_only_search --trials 16 \
      --seconds 900 --output-dir artifacts/actions-only-search

## Hard limits of what we can discover

This is an **adaptive configuration optimizer**, not a self-programming
scientist. It can search a large continuous parameter space inside the
registered ranking grammar, but cannot invent entirely new network
architectures, datasets, retrieval stages or models. To enlarge the
algorithm family, add an operator through a normal reviewed code PR, then
let the automated search optimize its parameters.

The initial selected pool of 24 routes is fixed by the current planner.
Re-ranking cannot find a necessary route absent from that pool.
If retrieval misses are dominated by this bound, the reviewed next
algorithm family must address recall and candidate generation at source,
rather than endlessly tuning the reranker.

The previous #430 data is **exposed synthetic DEV** with task patterns
from one generator; its three/two internal split is not genuine independent
confirmation. It has neither required-field gold nor authenticated
principal-scoped real heterogeneous providers or genuine agent completion
traces. High scores here do not demonstrate commercial readiness.

Continuation relies on retained Actions artifacts, not a durable database;
old states expire, and hashes intentionally invalidate incompatible
prior runs. The workflow has only read permissions and cannot commit
a champion or enable production by itself. The GitHub Actions default
branch scheduler and CPU/usage limits constrain how many experiments run.

Before commercial claims, require separately authored and truly disjoint
development plus confirmation data across supported real current-provider
schemas, principal/data scopes, required output fields, and fixed-agent
FULL/SR-K/SR-PROGRESSIVE/ORACLE task-level outcomes.

Historical #432 negative evidence is immutable and #1345/#1346 v0.18
release stays HOLD until its separate acceptance and audit.

Parent: https://github.com/JDeun/SchemaRouter/issues/1412
