# Original Algorithm 1 A6 — per-case native authority and gold witness bytes (E0)

**2026-10-26.** The current independent native intake validates original
publisher-source bytes and *declared* SHA-256 values for each case's native
authority and gold reference, but has no byte-level check for the referenced
documents. A6 must not accept hashes as actual independent source evidence.

## Options

- **Chosen:** opt-in extension of the existing source-pinned preflight with
  two separate **private witness collections**, one native-authority and one
  gold-reference. Each collection must cover exactly the intake case IDs and
  bind each decoded original byte payload to the pre-existing digest in
  `gold.json`. This keeps the original four-/five-file interfaces intact.
- Reformat v1 manifest/gold and require inline witness bytes everywhere:
  incompatible with existing historical publisher intake clients and
  increases risk of accidentally committing private gold.
- Automatically fetch provider URLs or trust a self-signed reviewer receipt:
  unapproved remote access cannot validate source-owner authority, and
  signer assertions cannot establish a trusted reviewer independently.

## Private file shape

Each of two distinct private local UTF-8 JSON files uses exactly:

```json
{"references": [{"id": "publisher-case-01", "evidence_base64": "..."}]}
```

- Original opaque bytes are canonically base64 encoded, 1–65,536 decoded
  bytes per case, within a 5 MiB raw JSON file limit and max 256 cases.
- IDs must be unique, safe, and a bijection with the actual case cohort.
- The *native-authority* digest matches `native_authority_sha256` and the
  separate *gold-reference* digest matches `gold_reference_sha256` for that
  specific ID. No cross-file substitution is accepted.
- Missing/extra/duplicate/corrupted references, noncanonical encodings,
  SHA mismatch or changed inventory/source bytes prevent a report.
- Never emit original queries, case IDs, authority bytes, gold bytes, route
  identities, credentials, raw exceptions or reviewer details; output only
  source-neutral aggregate booleans/counts.

## Scope and external hold

These references are still **submitted by the same untrusted participant**.
Correct byte hashing is not evidence that the source actually belongs to the
asserted publisher, the case's true native field or authorization scope is
correct, the requested license permits execution, or the author and reviewer
were independent. Both `independent_e2_qualified` and `scoring_authorized`
remain **false** even when every byte matches. Independently reviewed
publisher EN/KO/JA source-native examples remain BLOCKED_EXTERNAL #1346.
