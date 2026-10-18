# G4 E0: discover native typed graph targets without target-route gold

[Original architecture #1530](https://github.com/JDeun/SchemaRouter/issues/1530).
[Scoped study #1558](https://github.com/JDeun/SchemaRouter/issues/1558).
[Native attestation #1557](https://github.com/JDeun/SchemaRouter/pull/1557).

## Original-paper increment

G3 requires a host to supply the **final target route ID**. This
research-only G4 instead accepts a host-approved **catalog of up to 32**
registered source/endpoint fingerprint pairs, user query, approved
`NativeConceptCatalog` semantic aliases + complete required FieldGroup,
and explicit principal. G4 uses the native principal/field/availability-
scoped registered schema and discovers every output-field-complete consumer
whose one required *annotated* input can be satisfied by an authorized
parameter-free source of the same exact, typed **identifier semantic**.

There is **no answer-target tool name** in the query catalog or G4
call. G4 delegates each discovered two-endpoint route pair to the
existing canonical **G3→G2 typed graph snapshot and path verifier**.
This is an adjacency discovery view over original source-owned schema,
not a new graph computation engine or semantic classifier. It returns only
non-executable route references, verified field bindings and scoped
snapshot IDs; no tool arguments, agent loops, invocations, or permissions.

## E0 controls and nonclaims

- Exact already-reviewed native tool and endpoint source hashes.
- Source/license checks for the consumer, provenance required for roots;
  approval labels are local host assertions, not verified legal permission.
- Principal-hidden/denied/unavailable output/input contracts excluded
  *before* graph; stale visible source, schema ambiguity, wrong type,
  absent identifier and extra required inputs cannot produce paths.
- Alias matching is host-declared EN/KO/JA, not multilingual open-domain
  understanding. Negation, unknown goals and arbitrary concept synonyms
  are not solved.
- This one-hop **research** path returns every proven chain only while
  count <=5. If >5, **abstain** rather than invent a rank or truncate
  valid candidates. Empty results are unproven, **not calibrated no-fit**.
- The research boundary intentionally accepts at most 32 approved
  routes, walks pairwise O(N²), and does not scan every product catalog
  tool. This is not the desired scalable whole-catalog graph index.
- Offline production OpenAPI and MCP parsers, synthetic host-reviewed
  source/ontology and simple task examples: not independent retrieval
  metric or actual provider/agent task completion.

## Remaining product milestones

Scale from local approved segment to a persistent canonical typed
ontology graph covering all registered tools, index query concepts,
FieldGroup and dependency adjacency without O(N²) scanning. Rank
all qualified native graph targets at Top-K with independently
defensible ranking and explicit over-K metrics, support multi-hop
and heterogeneous domains under principal/source/license controls.

Only source-independent publisher-authored gold #1346 and paired
external agent/provider #1477 can establish retrieval advantage or
commercial-grade final-task quality. Frozen #432 results and v0.18
#1356 release HOLD unchanged.
