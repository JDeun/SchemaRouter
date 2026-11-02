# Original OpenAI operation-wide native source and journal E0 — design

## Goal / boundaries

Extend #1560's genuine publisher-source evidence beyond the current 161
supported GET operations to **every adapter-valid original OpenAI HTTP
operation**, including POST/DELETE, using the exact existing byte-pinned
`8243cc8f` original and its license. Keep existing `tool_from_openapi`,
registry, posting index, graph, policy, 50,000-node complexity guard and
source-owned journal; never execute a provider call or infer source semantics.
No default routing, publisher gold, E2 or release qualification.

## Alternatives / decision

- **Selected:** scope each original (path, verb) and its transitive original
  component references, then compile with the canonical adapter. This is
  bounded, verifiable and preserves methods, authentication and inputs.
- Whole-document conversion would weaken or fail the existing structural
  ceiling and is excluded.
- Synthetic expansion/altered query-bearing paths would manufacture source
  authority and is excluded.

## Acceptance

1. Pinned document declares 371 real HTTP operations: GET 163, POST 155,
   DELETE 53. Six literal query-bearing path names represent seven original
   operations. Another **nine** POST operations have only non-JSON request
   bodies (seven required multipart/SDP, two optional multipart); the existing
   adapter cannot retain them. All 16 operations remain unsupported, yielding
   **355 represented native operations** (161 GET, 142 POST, 52 DELETE),
   without invented query-path normalization or file upload.
2. For each scoped operation, exact original method, route, operationId,
   mandatory path parameters, required JSON request bodies and declared
   authentication survive adapter compilation. Only GET is read-only. Unreviewed
   source, policy and semantic grants stay empty.
3. Together with Ollama (2) and Pirate Weather (1), the registry contains
   **358 genuine original operations**. Removing/restoring a real OpenAI
   operation through the source-owned journal must reject stale lookups and
   match full rebuild and independently enumerated original route manifest.
4. Publisher bytes, license and immutable revisions must fail closed on
   changes, and CI Linux Python 3.12 must execute the same offline receipt.

## Limitations

The multiple HTTP operations originate from only three publisher OpenAPI
sources; they do not satisfy heterogeneous ≥500/≥5000 real-provider acceptance,
source-authorized semantic gold, independent E2 or real agent/model outcomes.
POST/DELETE are indexed structural descriptions only, with default-deny and
**zero attempted provider execution**.

## During-implementation ruling

Initial method-only inventory would have counted nine original
multipart/SDP-only POST operations as supported even though the converter
discards their request media types. Exclude all nine, including two optional
multipart bodies, rather than misrepresent runnable argument contracts.
This reduces the advertised native count from 364 to 355; native multipart
support requires separate adapter design and tests.
