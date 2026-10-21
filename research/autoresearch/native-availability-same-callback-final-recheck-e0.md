# #1618 / #1560 — qualified route live-health recheck E0

The original native posting and G5 graph lookups were source-snapshot
pinned, policy/field scope/availability-filtered BEFORE K and protected
by a retrieval authority witness. However, a caller-supplied live health
predicate can retain *the same Python callable identity* while its
underlying mutable health set is changed by a **later** candidate during
the same lookup. The earlier candidate had already been included in
the qualifying list. This can compromise both returned path identities
and the `qualified_count` returned for over-K abstention, without
changing the registered source version or policy object identity.

Two explicitly opted-in native-index readers now re-validate **every
previously-qualified route at the end of the candidate scan**, before
publishing any candidate OR over-K count. A revoked G5 graph producer
or consumer, missing required visible output field/projection, or changed
original source fingerprint fails closed with a data-minimized
`PolicyViolationError`. Posting readers similarly recheck the exact
registered route, source/license, current authorization, live
availability and projected mandatory FieldGroup. Exceptions from
provider/availability callbacks are not disclosed.

The already-present G5 experimental ranker still independently
revalidates after its untrusted callback; this change closes the
**ordinary unranked/default** path, not merely the optional ranker.

Regression E0:
- One of two and one of six paths is revoked by a later native
  candidate's callback while the availability function object and
  source registry version remain identical.
- Fail closed for both normal K5 responses and over-K qualified
  cardinality, for both G5 and the native semantic posting reader.
- Stable availability returns the exact already-authorized native
  source paths; 5K unrelated noise is not scanned.
- This is an opt-in native-index runtime safety fix, not a
  production default path change, independent provider task/E2 result
  or new ranker/no-fit classifier.

**Concurrency boundary:** this second bounded validation pass narrows
same-thread mutable callback races but is not a linearizable external
health-monitor transaction. Revocation *after* the final check still
requires the host/executor to reauthorize before executing tools.
#1618/#1560/#1535 remain open, #1356 v0.18 HARD HOLD.
