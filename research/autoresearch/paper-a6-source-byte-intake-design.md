# Original Algorithm 1 A6 — optional native source-byte preflight (E0)

**Decision (2026-10-26).** Extend the existing unscored native E2 intake,
not a second scorer or a new independent dataset. Existing v1 four-file
preflight remains backward compatible; a separately opted-in fifth original
native-inventory byte stream is compared with the manifest's exact
`native_tool_inventory_sha256` before any report is returned.

## Alternatives and tradeoffs

- **Chosen:** additive byte-binding entrypoint and `--native-inventory` CLI
  argument. Existing synthetic preflight and upstream four-file consumers
  remain unchanged; callers can distinguish a supplied verified byte match
  from a bare unverified digest claim.
- Replace v1 with an incompatible mandatory five-file protocol: stricter
  default but breaks existing external intake clients and historic checks.
- Add an autonomous provider fetch/reviewer: would introduce network,
  identity and license claims which cannot be established by a local E0
  structural validator.

## Acceptance

1. Exact original bytes must be non-empty, `bytes`, bounded by the same 5 MiB
   resource limit, and have the *identical* SHA-256 declared in the v1 manifest.
2. A mismatch refuses to report or score; no original source/query/gold bytes,
   IDs, route names or secrets are printed in the report or error messages.
3. A matching snapshot produces an additional **structural-only** flag, never
   source-authorship verification, gold correctness, provider authorization,
   execution or independent E2 qualification.
4. The original four-file validator and its CLI contract remain unchanged.
   Local synthetic tests are not publisher-authored cases.

## Non-goals / external hold

The digest still comes from the submitter. This step cannot prove that the
inventory is truly the provider's pinned commit, that gold routes/fields are
correct, that case author and reviewer are independent, or that license and
permission attestations are authentic. Original independent EN/KO/JA publisher
cases and source-owner review remain **BLOCKED_EXTERNAL**, and release #1356
remains HARD HOLD.
