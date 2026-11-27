# Retired lexical planner (research checkout only)

These three modules are the historical lexical planner, planning context, and planning stages formerly installed under `src/schemarouter/`. They remain available only for reproducing existing comparative research and regression fixtures; the wheel packages only `src/schemarouter`. Do not add imports from this directory to the product or use it as a production fallback.

The restored paper planner lives in the product's paper planning modules. Historical lexical results do not constitute validation of that planner. The former v0.17 versus lexical candidate wheel workflow remains in Git history along with its comparator; it cannot be interpreted as a current-product wheel regression after the public lexical API is removed.
