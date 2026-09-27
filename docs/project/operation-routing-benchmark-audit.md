# Operation-routing benchmark audit

## Scope

This audit reviews the current graph-v1 development corpus as a research-selection surface. It does not invalidate results already produced under the preregistered 0.10 graph-projection protocol.

## What graph-v1 does well

- 1,200 deterministic cases with balanced supported routes and six language groups.
- Exact normalized-query overlap guards against all checked-in predecessor corpora.
- Supported, near-domain unsupported, and ordinary OOD cases are reported separately.
- Route counts are balanced: 16 supported routes with 48 cases each.
- The corpus is explicitly development-only and may be used for architecture selection.

## Limitations for production-quality claims

### 1. Label-revealing wrapper language

Many near-domain wrappers explicitly contain phrases equivalent to `unsupported`, `reject`, `schema explicitly supports`, `do not substitute`, or `registered graph cannot express`. Supported wrappers likewise contain routing-oriented instructions such as `declared endpoint`, `registered tool contract`, and `capability graph`.

These are useful adversarial controls for a development experiment, but they are not representative user traffic and can create lexical shortcuts between query text and the expected abstain/route label.

### 2. One unsupported action family per domain

Each of the eight tool domains has one near-domain unsupported core action translated across languages and wrapped eight ways. This gives 384 cases, but the semantic diversity is much lower than the raw case count suggests.

A production-quality corpus should include several independent unsupported-operation families per tool domain and should hold out entire unsupported families, not only wrappers.

### 3. Template-family dependence

Supported cases combine one route-specific core template with a small wrapper set. Exact string deduplication does not detect semantic/template near-duplicates. A model can therefore improve on wrapper regularities without learning robust operation semantics.

### 4. OOD is intentionally small and easy

Only 48 ordinary OOD cases are present, and many are obviously unrelated to registered tool domains. This is appropriate for the current cycle because near-domain rejection is the harder safety target, but it is insufficient for a production claim.

### 5. Synthetic balance differs from deployment traffic

Perfect route/language balance is excellent for diagnosis, but deployed traffic will be skewed. Production evaluation should therefore report both macro-balanced metrics and workload-weighted metrics from a separate naturalistic sample.

## Requirements for the next fresh cycle

Do not modify graph-v1 retroactively. Instead, the next cycle should create a new development/calibration/blind family with:

- natural user utterances that do not mention routing, schemas, rejection, support status, or endpoint selection;
- at least 4 independent unsupported-operation families per domain before wrapper/paraphrase expansion;
- family-level holdout so unsupported actions in calibration/blind are semantically distinct from development families;
- paraphrase-family holdout for supported routes, not only exact-query overlap;
- semantic near-duplicate audit in addition to normalized exact overlap;
- ambiguous-but-supported, ambiguous-and-unsupported, mutation, read/write, and side-effect boundary cases;
- realistic short queries, terse commands, typos, code-switching, and conversational follow-ups;
- per-language native or independently authored phrasing rather than translation-only equivalents where feasible;
- macro route/language metrics plus a separate naturalistic workload-weighted evaluation;
- false-route analysis by unsupported-operation family;
- explicit minimum sample counts before interpreting worst-language or worst-route percentages.

## Claim policy

Graph-v1 results may support architecture-selection and regression claims for the 0.10 graph-projection cycle. They should not by themselves support a claim that SchemaRouter has reached the standing 85% production-quality target.

The standing production scorecard should be applied only after a candidate also succeeds on fresh, non-label-revealing calibration/blind evidence.