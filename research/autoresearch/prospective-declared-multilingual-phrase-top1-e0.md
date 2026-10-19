# #1339 — Prospective (author-written) declared CJK phrase Top1 DEV (E0)

Date: 2026-10-19. Goal: *route-selection accuracy*, not another generic security-only patch.

## Correctness diagnosis

Historical #432 independent 2026-10-14 shows on its FROZEN English-metadata 500-tool catalog: EN initial required-route recall 153/160; KO/JA 0/160 each. SchemaRouter's production KeywordAnalyzer cannot invent unavailable native cross-language concepts. Existing E0 DeclaredConceptGraphAnalyzer can map host-approved aliases to semantic field IDs, but only with a **whole-query exact match**. Real positive requests usually include other Korean/Japanese words and grammatical particles, so the exact-mode candidate is insufficient even when a human/provider has already approved a bilingual semantic alias.

We extend ONLY the explicitly opt-in researcher-owned DeclaredConceptGraphAnalyzer with match_mode='bounded_phrase'; default remains 'exact' and production router is untouched. The phrase bridge matches **only** host-declared aliases (no guessed translations, no internet/model, no gold-aware selection), requires a full bounded phrase and cautious CJK particles, rejects explicit common exclusion/negation cues, and refuses to inject a concept when multiple different semantic IDs match. It delegates final principal authorization, typed provider matching, native Top-K and fingerprints to the existing SchemaRouter. Not an autonomous agent and never a dispatch authority.

## Prospective matched diagnostic

New source: scripts/research_multilingual_declared_phrase_dev.py; no replay of frozen #432/#424 or prior #430 case texts. Four registered English-only native typed routes (one decoy and three concept-bearing), fixed Top1, EN/KO/JA positive natural-language sentences (three per language), plus seven English/Korean/Japanese OOD/explicit-negation/multi-target negatives. Every row records actual source route, score, positive semantic evidence, expected native gold held by the scorer only and wall time. Negative 'nonempty' Top1 results with score==0 are NOT safe abstentions or successful no-fit; record only positive-evidence false matches. Compared arms: original exact-mode host-declared concept graph vs bounded-phrase proposal. Both have identical registry, declared concepts, principal and k; source fingerprints and visible field permissions checked.

The dedicated Linux py3.12 workflow tests original exact-mode regression, explicit negation/ambiguity/OOD, Unicode NFD and CJK particle cases and prints source-sha-bound results to CI logs. E0 author-built, short warmup-free wall time on GitHub Actions is NOT CPU production SLO or third-party independent quality evidence.

## Pre-registered acceptance for this opt-in developer experiment

- No source permission widening, new tool/field authority or fabricated translations.
- KO/JA author-built supported cases have positive evidence on correct native Top1 more often than original exact mode, no positive evidence on recorded negatives, no default-mode behavior change.
- Repeat with host-approved realistic heterogeneous native source aliases and **new query authorship**, include unconstrained code-mixed, misleading negative phrasing and multi-intent, then independent #1346 fixed-K route/field gold and paired #1477 task success. Conservative guardrails may falsely refuse many correct complex requests and do not prove acceptable production recall/no-fit.
- This **does not** repair frozen #432 English-only provider 0/160 automatically; a provider/host must independently supply truthful multilingual alias-equivalence data or a separately reviewed model candidate path. No release #1356 until actual independent E2.

No product default promotion, parameter retuning on frozen data, or claim of Cuckoo-like quality.


## Separate 500-route stress cohort (same PR; not a held-out confirmation)

To ensure the four-tool diagnostic is not confused with real catalog scale, a second **prospective, newly written 11-request cohort** is registered under `scripts/research_multilingual_declared_phrase_500_dev.py`: 500 original ToolSpec/EndpointSpec routes, exactly 3 verified canonical concepts, 496 intentionally irrelevant English-only native routes, fixed `Top-K=1`, 2 supported requests for each EN/KO/JA language and 5 unsupported/negated/multi-concept controls. Every row records original output/fingerprint attestation, expected route, positive-score evidence and observed Linux CI wall-time. Each experiment arm uses the same actual native registry and approved semantic-equivalence declarations, unlike a translated query or an oracle route insertion. All unsupported controls remain in the denominator even when zero-score backfill returns a candidate.

**Prior-to-run acceptance:** both arms complete the same exact 500-route source catalog; the new bounded-phrase arm should improve the KO/JA supported correct-positive Top1 count versus exact, without **increasing** unsupported positive-score cases. There is no post hoc edit of the frozen #432 corpus, its expected routes, or this newly written case manifest after seeing its first results. An uncalibrated zero-score candidate is **not** a no-fit declaration. The real historical 500-tool KO/JA 0/160 outcome can only change in a new independently authored and separately preregistered cohort; no measurement from this self-authored E0 substitutes for that. Runtime measurements here are wall-clock diagnostics, not stable CPU p95/SLO.

The 500-route cohort still has intentionally sparse decoys and host-curated multilingual aliases; it **does not** establish the semantic transfer needed for an English-only tool catalog that lacks bilingual trusted aliases. A separate multilingual encoder or host-reviewed source enrichment path plus independent external provider/query origin and full agent success are still required before default adoption.


## First 500-route E0 result and **observed regression** (before correction)

The first independent-in-time **developer-owned** 500-route run at head `3a38bff497b5593602d32e7f6f3ab0f14ca85136` in [GitHub Actions 39237216801](https://github.com/JDeun/SchemaRouter/actions/runs/39237216801) completed successfully. Original exact vs proposed bounded-phrase correct-positive Top1: EN **2/2 → 2/2**; KO **0/2 → 2/2**; JA **0/2 → 2/2**. Crucially, Korean unsupported positives **0/2 → 1/2** (**regression**). Japanese stayed 0/2 and English stayed 1/1. Diagnostic medians (unstable CI wall clock) EN 139.208→154.038ms, KO 142.554→153.706ms, JA 143.656→146.442ms; do not generalize to performance SLA.

The distinct negative `탄성계수와 열전도율 둘 다 비교해야 합니다.` was not correctly recognized as a *two-concept* request because Korean coordination particles were missing from the bounded alias matcher: the first declared alias ended in `와` and was ignored, the second was detected. This falsely enriched a single target. **Do not discard/change this observation or the test query.** The post-observation fix adds Korean coordinators `와/과` to the conservative CJK boundary set, making both approved concepts visible to the existing ambiguity veto, and asserts the same 500-route fixed negative cannot introduce positive evidence. This is debugging a known self-authored DEV regression, not prospectively confirmed independent accuracy.

The latest-head rerun must confirm both positive support and nonincreasing negative positives; if the real CI gate fails, keep this PR Draft and report the negative. The original frozen #432 result remains unchanged.
