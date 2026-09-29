# 0.14 adaptive DEV authoring scaffold

Tracking issue: **#430**

This scaffold reserves the preregistered **240 development semantic-task slots** without creating
task text, gold routes, rankings, scores, or condition outcomes.

## Why a scaffold first

The successor protocol is frozen separately in PR #469. Before that protocol is merged, the
repository may prepare structural authoring infrastructure but must not generate or score the DEV
corpus.

The scaffold therefore enforces:

- 8 task strata;
- 6 languages;
- 5 independent tasks per stratum-language cell;
- 240 total semantic-task slots;
- exactly one language per semantic task;
- no query or gold-route fields;
- no ranking, score, condition, or result fields;
- no confirmation-surface generation;
- no scoring authorization.

## Independence boundary

Task authors must not use B1/B2 row content, #434 DEV queries, #432 rows, #424 rows, or paraphrases
of prior benchmark queries. Those sources are explicitly marked forbidden in the generated plan.

This file is **not** the DEV corpus. It contains no benchmark content and cannot be used for scoring.

## Generation

```bash
python scripts/generate_agent_utility_v5_adaptive_authoring_plan.py \
  --out artifacts/adaptive-v5/dev-authoring-plan.json
```

The output is deterministic. Corpus authoring remains blocked until the preregistration is merged.
