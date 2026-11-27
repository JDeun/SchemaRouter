# Gate C2 DEV — Does graph presentation help the external agent?

2026-11-27 · #1900 / #1897. Before model trials. Core at 51744aa; C1 negative evidence remains immutable at df3127c. Owner clarification: the product is a structured tool-schema knowledge graph that the external agent explores; it does not need to decide which capability the question means. This supersedes the assumption that deterministic alias resolution must be the primary agent interface. Do not repair C1 scores with outcome-driven ontology changes.

## Hypotheses and four arms

A vs B isolates representation with the full allowed catalog. C vs D isolates representation during on-demand lookup. Dynamic vs static can reveal context tradeoffs but is not a pure representation intervention. Same normalized 19-route/166-field/171-concept catalog, exact source revisions, metadata, aliases, field groups, input/output schemas and IDs in every arm; no new meaning annotations. Flat and graph must round-trip to identical information, including each individual route neighborhood. Graph view uses actual RDF-verified endpoint, response field, concept and group links, with metadata attributes (not dumping redundant internal RDF triples). Both dynamic arms have the same unranked literal locator and inspect interface, no cap on candidates; a query such as band_gap returns all relevant literal hits, not an automatic ambiguity rejection. The agent selects explicit route/field IDs; projection occurs only after selection. The comparison tests graph presentation and browsing, not whether RDF is faster than a specialized search engine.

| Arm | Initial context / lookup |
|---|---|
| A-flat-full | All flat route records and shared vocabulary, no lookup |
| B-graph-full | All graph nodes, edges, shared vocabulary, no lookup |
| C-flat-browse | Same literal locator and selected flat route inspection |
| D-graph-browse | Same literal locator and selected graph neighborhood inspection |

No internal LLM, planner, executor, automatic sense selection, automatic field group expansion or K5. Field selection uses original complete input schema and explicit output paths. Host-sanitized catalog only; not a dynamic authorization service or native provider contract.

## Frozen pilot protocol

12 newly written **developer-authored DEV** natural-language questions, eight supported, two unavailable, two explicitly ambiguous. They are designed from already-exposed historical schema inventory, not independent holdout or original paper task reproduction. No archived concepts or calls provided to the agent. Tasks and answer rubric in graph-agent-dev-tasks.json; only question text reaches model. Supported selection success requires at least one complete acceptable alternative per need, no invalid route/field pairs, and no selected field outside the union of accepted alternatives; statuses unavailable/clarify require empty selections. An ID is valid only for its original route; dynamic selections must come from inspected routes. This is a narrow schema-selection rubric, not data acquisition, argument validity or answer correctness. Real-world task success remains untested. All tasks and arms included even on failures.

Run the same explicitly identified external model and loopback OpenAI-compatible HTTP /v1 endpoint, temperature 0, max 768 completion tokens per turn, one final JSON response in static arms, at most four find/inspect actions plus final turn in dynamic arms. No retry or repair. Cyclic arm order balances position. Freeze model weights/version and server settings in run record before scoring; runner's requested model string alone is not a weight attestation. Model may be local vLLM/llama.cpp/Ollama compatibility endpoint; no hosted paid API or secret transmission. Require a sufficient model context window for both full representations; if context is too small record failure, do not truncate one arm. Retain each request/response, elapsed wall time, selected fields and scores; sum reported prompt/completion tokens over every call, including observations and repeated context, leave missing usage null. No judge calls. Scripted callbacks in unit tests only validate the harness, never count as a model outcome. Pilot descriptive paired task results only; 12 tasks insufficient for noninferiority, independent evaluation or release decision.

Before model availability, check equal information, all route neighborhoods, explicit field projection, alternate/ambiguous locator behavior and invalid IDs, and measure canonical serialized bytes for full catalog, each route neighborhood and fixed lookup+inspection traces: band_gap, elastic modulus, research paper. The traces inspect all returned route IDs (union of route hits and field-hit owners) without ranking; this is a deterministic mechanism/byte proxy, not agent efficiency or tokens. Report exact model blocker if unavailable. No new model score is implied. The original #1900 decision-grade independent cohort and paired full-task protocol remain outstanding; C1 failure remains separate.

## Reproduce

From research/agent-driven-ontology-poc on this branch with the pinned environment:

```sh
python -m unittest -v test_graph_views test_agent_probe
python agent_probe.py --base-url http://127.0.0.1:8000/v1 --model YOUR_LOCAL_MODEL --out /tmp/sr-agent-probe
```

Optional --api-extract points to the exact historical API-only bytes, hash verified. No user records or real source requests. Do not run before a model is available and settings are recorded. Main/release/paper branches unchanged.

## Original paper comparator (E), planned separate gate

The owner requested comparison with the original Algorithm 1. E must use the immutable original manuscript and implementation revision, not C1, an archived output replay, or an approximation renamed as the paper. The original router has an Understand model call, intent registry, deterministic candidate ranking and projection, and produces a tool plan. Retain its native field-group/identifier behavior; compare supported need coverage, extra fields, and total routing plus agent cost under a common rubric that reports the paper's native plan separately from any final agent refinement. Unavailable/clarify behavior, required inputs and permitted catalog semantics must be prospectively aligned; do not force the original router's output to mimic the A–D response protocol or score intentional identifier fields as arbitrary false positives. E may use a separately authorized local private paper checkout; no private paper code or data copied into the public branch. Freeze exact paper hash, model, input prompts, adapter and scoring before any E model run. E is **not implemented or scored in this pilot**. Do not use E as a reason to delay the narrow A–D representation diagnostic, or interpret A–D as a comparison with the paper.
