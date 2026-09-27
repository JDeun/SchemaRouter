# Router ecosystem source-code audit

## Purpose

This note records implementation-level patterns observed directly in upstream open-source router code. It is design input for SchemaRouter, not copied implementation and not evidence that the projects solve the same problem.

SchemaRouter routes registered tool/endpoint capabilities under schema authority. Several projects below route models, query engines, or pipeline branches instead, so their patterns are only adopted where the semantics match.

## Aurelio Semantic Router

Inspected source:

- `semantic_router/routers/base.py`
- `semantic_router/routers/semantic.py`
- `semantic_router/routers/hybrid.py`

Observed implementation patterns:

- `BaseRouter` owns an index, `top_k`, aggregation policy, a global score threshold, and per-route thresholds.
- Query-time routing encodes the query, retrieves top-k indexed routes, aggregates scores, then checks each candidate against its route-local threshold.
- A route can fail its threshold and produce no route; route filtering restricts which routes are eligible before selection.
- Hybrid routing combines dense and sparse representations and adjusts the effective threshold to the score geometry of the hybrid representation.

SchemaRouter takeaway:

- Keep a first-class abstain/no-route state.
- Calibrate thresholds against the score kind that produced them; do not assume one threshold transfers between embedding/reranker/projection score families.
- Candidate eligibility should be restricted before scoring whenever caller/schema authority already narrows the route set.

## RouteLLM

Inspected source:

- `routellm/routers/routers.py`
- `routellm/controller.py`

Observed implementation patterns:

- The abstract router exposes one scalar `calculate_strong_win_rate(prompt)` in `[0,1]`.
- The final route is a direct scalar-threshold comparison: score >= threshold selects the strong model, otherwise the weak model.
- Controller code validates router identity and threshold bounds before dispatch.

SchemaRouter takeaway:

- Separate evidence estimation from the final decision boundary.
- Keep threshold validation explicit and deterministic.
- Do not import RouteLLM's binary always-route semantics into tool routing: SchemaRouter needs a real abstain state and schema authority.

## LlamaIndex

Inspected source:

- `llama-index-core/llama_index/core/query_engine/router_query_engine.py`

Observed implementation patterns:

- `RouterQueryEngine` gives a selector only candidate metadata plus the query, then executes the selected query engine(s).
- `ToolRetrieverRouterQueryEngine` performs retrieval first and operates on the retrieved subset rather than every registered tool.
- Multi-selection and response combination are distinct from candidate retrieval.

SchemaRouter takeaway:

- Candidate reduction and final operation selection should remain separate stages.
- Retrieval may reduce the authorized candidate surface but must not manufacture authority.
- Keep multi-call planning separate from single-call route classification.

## Haystack ConditionalRouter

Inspected source:

- `haystack/components/routers/conditional_router.py`

Observed implementation patterns:

- Routes are explicit ordered boolean conditions.
- The first matching route wins.
- If no condition matches, the component raises `NoRouteSelectedException` rather than silently inventing a branch.
- Output type validation and sandboxed expression evaluation are explicit parts of the routing component.

SchemaRouter takeaway:

- Deterministic hard evidence should execute before semantic evidence.
- No hard-rule match should remain a first-class no-route/escalate outcome.
- Typed output/plan validation belongs inside the routing contract, not as an afterthought.

## LiteLLM

Inspected source:

- `litellm/router_strategy/quality_router/quality_router.py`
- `litellm/router_strategy/complexity_router/capability_classifier.py`

Observed implementation patterns:

- QualityRouter validates admin-declared routing preferences before using them and can apply explicit keyword overrides before classifier-based routing.
- Deterministic tie-breaking uses declared order, quality tier, cost, and stable model name.
- Capability classification returns a strict structured verdict with a qualitative boundary plus calibrated `p_solve`.
- Different capability boundaries map to different required routing thresholds instead of using one global threshold for every situation.

SchemaRouter takeaway:

- Treat trusted configuration as authoritative and validate it eagerly.
- Keep deterministic overrides/constraints separate from probabilistic routing.
- Introduce explicit evidence/boundary classes before attempting a single universal semantic threshold.
- Structured uncertainty is more useful than forcing every query into one scalar similarity decision.

## vLLM Semantic Router

Inspected source:

- `src/semantic-router/pkg/decision/engine.go`
- `src/semantic-router/pkg/decision/engine_unknown.go`
- `src/semantic-router/pkg/classification/classifier_projections.go`
- `src/semantic-router/pkg/config/tool_selection_plugin.go`

Observed implementation patterns:

- `SignalMatches` keeps keyword, embedding, domain, safety, classifier, metadata, projection, and other signal families distinct.
- Signal confidences, raw numeric values, and signal errors are stored separately.
- Decision evaluation has a true/false/unknown state rather than collapsing unavailable evidence into false.
- `on_unknown` supports explicit `match`, `no-match`, and `fail request` policies.
- Projection failures delete derived scores and record an error; unavailable input is explicitly not converted to numeric zero because that could create a false low-risk signal.
- Confidence is only considered comparable when it comes from one declared score kind; structurally manufactured/error-policy matches are excluded from confidence ranking.
- Tool selection distinguishes add/filter modes, top-k, similarity thresholds, and fallback-to-empty behavior.

SchemaRouter takeaway:

- This is the strongest implementation-level confirmation for the next cycle.
- Add explicit score/evidence kinds and never compare raw confidence across incompatible signal families.
- Represent unavailable/failed evidence as unknown, not zero.
- Give every semantic stage an explicit unknown policy with fail-closed support.
- Separate tool-domain evidence, operation-action evidence, field/concept evidence, and negative/unsupported evidence before projection into a route decision.
- Prefer filtering an already-authorized set over semantic creation of new executable routes.

## LangGraph

Inspected source:

- `libs/langgraph/langgraph/graph/state.py`
- `libs/langgraph/langgraph/graph/_branch.py`

Observed implementation patterns:

- Conditional edges map a routing function's bounded result to declared graph destinations.
- `path_map` can explicitly restrict the set of reachable destinations.
- The routing function chooses among graph edges; it does not dynamically create graph nodes.

SchemaRouter takeaway:

- This reinforces the distinction between semantic decision evidence and predeclared execution topology.
- SchemaRouter should hand an orchestrator a bounded typed route/abstain result; the orchestrator remains responsible for graph execution.

## Cross-project synthesis

The source-level comparison favors the following next-cycle architecture:

1. build the executable universe from the trusted schema graph;
2. apply deterministic caller/policy/health constraints first;
3. compute separate signal families for tool domain, operation action, response field/concept, qualifiers, and explicit negative evidence;
4. preserve signal failure as `unknown`; never substitute zero similarity for unavailable evidence;
5. project only compatible score kinds into calibrated route evidence;
6. retrieve/filter a bounded candidate subset before expensive reranking;
7. accept only when graph consistency and calibrated evidence agree;
8. abstain/fail closed on unresolved or contradictory evidence;
9. expose the bounded result to LangGraph/LlamaIndex/etc. rather than taking orchestration authority.

## What not to copy

- RouteLLM's forced strong-vs-weak binary choice is inappropriate for tool routing because there is no abstain.
- LlamaIndex's selector execution model does not by itself enforce SchemaRouter's schema/field/argument authority.
- Semantic Router's route thresholds are useful, but a missing threshold that always returns a route would be unsafe as SchemaRouter's default.
- Model-routing quality tiers and tool execution authority are different concerns; model-router heuristics must remain soft evidence only.

## Immediate consequence of the failed fresh calibration

The frozen 0.10 candidate reached 68.75% supported exact-route accuracy but only 91.67% natural near-domain unsupported rejection. Both the candidate and full-BGE baseline failed the same 95% rejection gate, indicating the next cycle needs a better representation of unsupported capability boundaries rather than another threshold tweak on the frozen candidate.

The strongest source-backed direction is therefore multi-signal, typed-evidence routing with explicit unknown handling and negative capability evidence, evaluated on fresh natural development families.