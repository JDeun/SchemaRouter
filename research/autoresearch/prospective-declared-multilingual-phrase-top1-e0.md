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
