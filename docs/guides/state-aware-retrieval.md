# State-aware capability retrieval

The development package no longer exposes the historical state-eligibility filter for lexical Top-K results. Original-paper Algorithm 1 planning does not rerank or backfill candidates based on host workflow state.

Hosts can use the shared typed contracts `TypedExecutionState`, `evaluate_state_eligibility(requirements, state)`, and `evaluate_preconditions(preconditions, state)` to check explicitly declared state requirements and preconditions. These functions neither select candidates nor grant execution authority.

## Fixed Top-K eligibility

The historical fixed Top-K comparison is preserved in `scripts/research_legacy_planning/state_retrieval.py` in a source checkout, and the state-conditioned backfill comparison in `scripts/research_legacy_state_backfill.py`. Neither implementation is an installed API or a fallback for the paper planning path.

The historical comparison checks only already-visible candidates, never exposes hidden routes or infers workflow state, and fails closed on missing or incompatible declared requirements. Workflow selection, execution approval, state mutation, retries and compensation remain host responsibilities. The product's registered execution boundary and authorization checks are unchanged.

## Historical adaptive context baseline

Success-history reranking and session-exposure filtering are no longer part of the installed routing API. The frozen comparison implementation and its regression tests remain in `scripts/research_legacy_adaptive_context.py` and `tests/test_adaptive_context.py`. A host may manage exposure separately, but it must not alter the paper-first plan.
