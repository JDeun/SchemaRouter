# EN/KO full-corpus semantic review queue — 2026-10-11

**Scope:** #1202. This record and the automation are **not** an independent bilingual
sentence-by-sentence editorial attestation. No unattended detector can certify
semantic equivalence for 147 Markdown document pairs.

## Existing evidence versus outstanding acceptance

- Existing validated checks cover document counterparts, heading/fence/table
  structure, complete rendered pages, locale switching, numeric/provenance/
  scholarly citations, and a pinned **27-section** risk-based editorial ledger.
- `scripts/audit_translation_review_units.py` enumerates **all** Markdown
  headings, paragraphs, list items, and individual table rows in both language
  trees; fenced source code is verified by separate mechanical checks.
- The new complete bilingual inventory contains full source text, file-relative
  path, line, section index, review-unit index, SHA-256, and block type. An
  `aligned_by_structure` flag is **not** a translation-quality assertion:
  positional comparison is only advisory when counts and block kinds match.
- A per-block English prohibition signal alerts when its positionally aligned
  Korean block lacks an obvious negative form. It can both miss genuinely
  altered semantics and flag valid Korean paraphrases. Treat findings as a
  review queue, not proof of mistranslation.
- The output deliberately sets
  `independent_sentence_review_complete=false` regardless of scanner scores.

## Human review and acceptance path

1. Download the `translation-review-units.json` artifact from the Korean
   Translation Whole-Corpus Coverage workflow, pinned to the source commit.
2. Review **every** paired document, including blocks on pages not flagged by
   heuristics. Check meaning, negation, authorization, conditions, quantifiers,
   numerics, units, exceptions, causal claims, links, examples, and tables.
3. When Korean merges/splits English paragraphs, create explicit many-to-many
   editorial mappings; **never** silently pair by list position.
4. Record actual EN/KO source SHA or blob identities, block ranges, reviewer,
   comparison disposition, concrete supporting rationale, and any corrective
   patch. Reject stale mappings after either language changes.
5. Seek an independent bilingual reviewer for the full-corpus attestation.
   An automated success job, a self-authored waiver, or a sampled edit is not
   sufficient independent approval.
6. Re-run source, risk, browser/link, whole-corpus, and deployment checks on
   the same accepted revision. Close #1202 only when this evidence really
   covers every bilingual sentence, including all prose blocks and tables.

## Targeted correction verified in this slice

`docs_ko/guides/enterprise-data-onboarding.md` previously described
**internal and external** data-system onboarding in its opening sentence,
while the English source explicitly says **internal** data systems. Korean
now matches the narrower source claim, and its impacted pinned editorial
ledger entry was refreshed. This is one confirmed correction, not an
endorsement of the remaining corpus.

## Separate research boundary

This work does not modify the frozen 0.14 scientific source, task corpora,
models, scorer, held-out recovery, #424 gating, or SafeActBench evaluation.
