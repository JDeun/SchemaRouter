# B1 genuine GitHub REST OpenAPI GET catalog E0 — design

## Scope and source

Use the official MIT-licensed `github/rest-api-description` repository,
immutable upstream revision `755ee33b4a81d51f6f07a902cce26cbec3b822f2`,
published `descriptions/api.github.com/api.github.com.2022-11-28.json`.
The exact publisher file has **823 paths and 651 GET operations** under
OpenAPI 3.0.3. Its raw bytes and original LICENSE.md are independently
checked against upstream Git blobs and SHA-256; a deterministic gzip copy
retains the original JSON unchanged. Offline only.

## Choice

- Use the **existing** bounded original `(path, verb)` projection and native
  `tool_from_openapi`, then group the resulting source GET endpoints into
  **one publisher tool** (unique original operation IDs). This lets an
  atomic original provider removal/restoration yield an exact one-key
  source-owned journal delta without weakening the 64-key journal cap.
- Do not load the full 13 MB spec into the native converter in one step;
  that would violate the existing 50,000-node structural protection.
- Do not synthesize route schemas, policy grants, semantic fields, source
  permissions or any execution transport. The publisher's MIT license
  allows use of its spec, but is **not** a permission grant to call APIs.

## Acceptance

1. Original raw file **13,429,427 bytes**, SHA-256
   `309e30296b212d220ed143beeba216dbb0df11915daf79ee2ed01e06c6c9a586`,
   Git blob `28c3aec115589c92b6c584579b5572b5d6a2d78b`.
   Original MIT LICENSE.md **1,063 bytes**, SHA-256
   `3243761cbac07e6d169a5a2f4e7c25cc544da85248e735df74c3672e055cc87b`,
   blob `b50625eb63949013cae604b1cadd42cfa1eaf825`.
   The deterministic source gzip is separately pinned at **962,226 bytes**,
   SHA-256 `f65b4b2db635589e713979e50dbcf019d205044a76cfcd71f57f6b6070acfe4d`.
2. All 651 original GET paths, original `operationId`, read-only HTTP
   method and mandatory path inputs pass the unchanged native converter.
   One same-provider tool contains **651 distinct original endpoints**,
   not generated aliases or 651 invented independent providers.
3. Register that original GitHub bundle with byte-pinned Ollama (2 GETs)
   and Pirate Weather (1 GET): **654 source-native routes** in a single
   registry, no semantic postings, typed edges or authorization grants.
   Provider removal/restoration must prove **654→3→654**, two stale-index
   rejections and complete journal/full rebuild/original-manifest parity.
4. Add exact-source tamper tests, dedicated offline Python 3.12 CI receipt,
   no default behavior change and no release/E2 promotion.

## Explicit gaps

This >500 real publisher-source operation corpus still comes from three
OpenAPI publishers, not independently publisher-verified query/field gold,
heterogeneous MCP/OPTIMADE authorizations, ≥5000 real routes, model/agent E2,
or calibrated Top-K/no-fit. Keep #1346/#1477 BLOCKED_EXTERNAL, #1356 release
HARD HOLD, Draft #1755 unmerged.
