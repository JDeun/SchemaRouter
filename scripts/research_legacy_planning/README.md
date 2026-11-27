# Retired lexical planner (research checkout only)

These three modules are the historical lexical planner, planning context, and planning stages formerly installed under `src/schemarouter/`. They remain available only for reproducing existing comparative research and regression fixtures; the wheel packages only `src/schemarouter`. Do not add imports from this directory to the product or use it as a production fallback.

The restored paper planner lives in the product's paper planning modules. Historical lexical results do not constitute validation of that planner. The former v0.17 versus lexical candidate wheel workflow remains in Git history along with its comparator; it cannot be interpreted as a current-product wheel regression after the public lexical API is removed.

The historical flat `PlanRequest` is defined in `requests.py` and the two retrieval facades in `../research_legacy_runtime.py`. The installed request contract is `PaperPlanRequest`; the product never imports the historical envelope or its dispatch.

Fixed Top-K typed-state filtering is archived in `state_retrieval.py`, alongside the separate historical backfill comparator in `../research_legacy_state_backfill.py`. The product retains declared state and precondition evaluation in `schemarouter.execution_state`; those checks do not rank or execute capabilities.

Historical lightweight route DTOs live in `route_models.py`; their field-scope projection lives on `LegacySchemaRouter` in `../research_legacy_runtime.py`. Both retain the existing alias/metadata redaction and authority checks while the installed package no longer exposes lightweight lexical route ranking.
