# G1 native authorized dependency-graph retrieval (research only)

Issue [#1538](https://github.com/JDeun/SchemaRouter/issues/1538),
architecture parity [#1530](https://github.com/JDeun/SchemaRouter/issues/1530),
and the [original field-aware paper](https://arxiv.org/abs/2608.21375).

## Design gap and origin of evidence

The product already stores explicit `FieldSpec.semantic_id` and offers
authorized Top-K, and `build_capability_dependency_graph` already
compares typed producer→consumer field contracts. But `ParameterSpec`
does **not** have an authoritative `semantic_id`: the system must NOT
invent a consumer input semantic by comparing variable names.

The G1 research entrypoint
`scripts/research_authorized_native_graph_edges_g1.py` accepts a
**host-authored** exact EN/KO/JA query alias→target route/output semantic
and a trusted target *required parameter*→input semantic mapping. The
declared mapping supplies an explicit edge **hypothesis**, never
authorization, parameter values or an unverified execution binding.

At each request, obtain the current **principal-scoped** typed registry
using the existing policy/data-scope projection. Select only visible,
available, read-only/non-destructive endpoints. Construct
`CapabilityContract` for visible output fields with declared semantic IDs
and typed schemas, and for the declared target required parameter only
when its typed native parameter and intended response semantic are
visible. Pass these to the **existing**
`build_capability_snapshot` with the **visible endpoint fingerprints**
as `CapabilitySourceRevision` receipts, validate its deterministic
snapshot digest with `validate_capability_snapshot`, and invoke the
snapshot's native `build_graph().predecessors(target)` relation.
Return only bounded, stable
`NonExecutableDependencyHint` references with source/target field
and input parameter names. A source/permission/availability witness
must remain unchanged. The tool and agent execution pipelines are
**never** called.

## Non-claims and limitations

- A **one-hop adjacency hint** is not a tool execution sequence, graph
  database, joined provider state or guaranteed downstream task result.
- The declared input semantic mapping is **trusted external metadata**
  supplied by the host; SchemaRouter does not infer it from arbitrary
  native parameter names. A single target required parameter is
  supported; additional required parameters fail closed.
- The graph is built from *currently authorized* source views, not
  filtered only after graph construction. Denied or data-scope-hidden
  output IDs must not influence candidates or returned hints.
- **G1 typed input/output evidence is intentionally stricter than the
  general JSON Schema language**: only a simple scalar `{"type":"..."}`
  shape with no pattern/enum/other constraints is accepted for producer
  fields and target required parameter. Unverified implicit unit
  normalization and target credential/header inputs are rejected, as are
  unknown extra required parameters in native `input_schema`.
  Unsupported constraints must not be silently treated as compatible.
- The per-request research construction caps the authorized graph at
  **512 visible read-only routes and 4,096 visible output fields**.
  Exceeding the fixed K5 predecessor count fails closed rather than
  arbitrarily claiming the first five graph edges are best.
- The result does not return provider data, calculate input values,
  invoke either tool, decide an agent's actions or create an execution
  grant. No multi-hop dataflow, semantic rank over more than five
  predecessors, conversion-inferred units, source licensing judgment,
  negative-confidence calibration or model translation is claimed.
- If more than K5 authorized predecessors are found, **fail closed**
  rather than silently truncating graph candidate support. Unknown
  source input typing, stale authority and unregistered routes are
  rejected.
- Synthetic EN/KO/JA exact declarations and graph tests do **not**
  qualify independent E2 under [#1346](https://github.com/JDeun/SchemaRouter/issues/1346).
  Preserve frozen #432 negative, v0.18 #1356 HARD HOLD, unchanged
  production `retrieve_authorized` defaults and no autonomous agent.
