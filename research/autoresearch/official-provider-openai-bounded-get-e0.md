# B1 E0 — official OpenAI OpenAPI bounded native GET catalog

## Source and license

- Official publisher source: [openai/openai-openapi](https://github.com/openai/openai-openapi),
  immutable upstream revision `8243cc8fa6f04430fb1f1a6a2cb926fbeb4f7f26`.
- Original `openapi.yaml`: 4,210,167 bytes, SHA-256
  `cc2a329f77bb06b451b9eb6c14cacd6c1c36276ae778f2d63940fab1c7bbb6f6`,
  upstream Git blob `8d777683a29adc528382f163a88b0cd62613552d`.
- Original `LICENSE`: 1,083 bytes, MIT notice, SHA-256
  `bcba3de214851cce46ed5af42d6698044616eeace887c3231bc7a20474ab639e`,
  upstream Git blob `4f14854c3243516f3de1487a60f14882874d7e3a`.
- The repository retains a deterministic gzip **container** around the exact
  original source bytes (not a rewritten OpenAPI spec): 486,142 bytes,
  SHA-256 `703048f660242020c05019b8c776e5f65a87d079ae4e6148fbe7da4b96e10417`.
  Both the compressed container and decompressed original bytes are verified
  before parsing. The original publisher license is retained separately.

## Why a bounded projection

The original document has 237 paths and 371 HTTP operations, including 163
GET operations. Passing the entire document to `tool_from_openapi` fails its
intentional 50,000-node structural complexity limit. This research audit must
**not change or disable the production complexity guard**. Instead, it selects
one original GET operation and its original path-level metadata, follows only
exact local `#/components/<kind>/<name>` references to their original source
nodes, and passes the smaller unmodified source-derived projection through
the existing adapter. Missing/foreign references fail closed. Owner security
requirements and source-level authentication definitions are preserved.

The exact pinned source has 163 GET entries; 161 have adapter-supported paths.
The two query-bearing paths `/responses/{response_id}?beta=true` and
`/responses/{response_id}/input_items?beta=true` are rejected by the existing
native path validator and must **not** be silently normalized, invented or
treated as supported. Exact supported/skipped counts are fixed for this E0 pin.

## Acceptance and exclusions

- Verify raw source/license digests and Git blobs before parsing; reject a
  single-byte or compressed-length mutation before any registration.
- Preserve each selected original method, path, parameters, and referenced
  component objects; do not replace `$ref` with model-generated fields.
- Reuse the production `tool_from_openapi` converter, original registry and
  `NativeSchemaPostingIndex` / `NativeSchemaGraphIndex`. No second index or
  executable provider client; no token, network, request or inference call.
- Combine the supported OpenAI GET routes with the earlier two exact
  Ollama and Pirate Weather snapshots in **one 164-route canonical
  native registry**. This is a real three-publisher OpenAPI E0 source
  mixture, not a 500/5000-case heterogeneous E2 or owner-approved ontology.
- Default-deny principal and missing host semantic attestations produce zero
  semantic postings, zero typed dependency edges and zero permission grants.
- Explicitly label all measurements **E0 provider-authored SOURCE ONLY**:
  neither actual provider permission nor independently authored benchmark
  query/field/route gold, E2 model quality, license policy approval or
  500/5000 genuinely heterogeneous source-route coverage follows from it.

The 500/5000 synthetic research oracle remains separate. #1346/#1477 stay
`BLOCKED_EXTERNAL`; #1356 remains `HARD HOLD`, and Draft #1755 must not be
merged or promoted solely on this source-only evidence.
