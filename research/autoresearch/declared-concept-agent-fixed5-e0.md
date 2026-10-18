# Declared-concept fieldgroup selector in the original agent evaluator E0

## Scope and source
Issue [#1477](https://github.com/JDeun/SchemaRouter/issues/1477),
original north star [#1530](https://github.com/JDeun/SchemaRouter/issues/1530).
The native opt-in product components are [#1550](https://github.com/JDeun/SchemaRouter/pull/1550)
and [#1552](https://github.com/JDeun/SchemaRouter/pull/1552).

A source-owner-declared `NativeConceptCatalog` supplies an explicit,
bounded query alias→typed FieldGroup contract. The new
`AuthorizedConceptFixed5Selector` is ONLY a callback for the **existing**
`agent_utility_generated_common.run_generated_episode`
`EVAL-FIXED5-OPTIN` isolated condition. It does not modify the agent,
original task executor, frozen FULL/SR-5/SR-10/SR-PROGRESSIVE/ORACLE
conditions, output grader or default SchemaRouter retrieval.

The callback receives exactly the original query and the principal-scoped
`AuthorizedAgentToolSurface.visible_route_ids`. It calls the product
`retrieve_authorized_concepts`, rechecks scope/source-version/route
fingerprints and strict K5, and refuses selection if one retrieved candidate
is absent from the captured principal-visible source. The callback never
receives the fixture `required_routes`, expected fields, argument rules,
state transitions, provider observation or end-task labels. No gold-aware
refill after K; no new caller authority or argument invention.

Unknown concept and declared but unsatisfiable fieldgroup are different
**uncalibrated** empty-list results, not calibrated unsupported/no-fit
verdicts. Ambiguous/invalid concepts, altered ontology and policy/source
drift fail closed. In the existing agent evaluator, unsupported tasks may
produce a safe no-call result, but such a synthetic event does not establish
real model calibration.

## Tests / limits

- Existing `run_generated_episode` + `FrozenCorpusExecutor` under a
  scripted no-model agent, source-visible one-step synthetic fixture.
- EN/KO/JA author-declared mentions; hidden required field, unknown query,
  malformed/overlapping aliases, query/set/source drift and frozen-condition
  exclusion. Reuses existing `tests/test_integrated_fixed5_agent_selector.py`
  for two-step policy and strict-budget controls.
- No real model inference, remote provider, independent case authorship,
  multi-hop graph execution or scored user-facing answer accuracy is claimed.
- Qualify independently authored #1346 task/gold and downstream paired
  #1477 E2 on a fixed K5, equal principal/source/version and schema/token
  budgets. Historical #432 remains frozen and v0.18 #1356 HARD HOLD.
