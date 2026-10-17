# Production host-field contract policy content witness — S02 engineering

Owner: #1450, with SchemaRouter qualification S02; open PR is an **implementation-level security improvement**, not independent provider E2.

`select_authorized_field_contract` was already principal-scoped, read-only, and guarded against policy **object replacement**, registry version or availability replacement. Its `AuthorizationPolicy` is declared frozen, but its nested authorization rules, data-scope rules and compiled index partitions may mutate while the **same policy instance remains referenced**. A source-selection decision could therefore be emitted based on inconsistent historical policy semantics.

The bounded in-process digest records the policy default effect, ordered authorization and data-scope rules, and the ordered compiled authorization/data-rule tuples and partition contents. It is checked **before retrieval**, **after retrieval**, **after the full authorized-catalog scan**, **before an abstention receipt**, and **before returning a successful selection**. Any malformed contents or drift fail closed with `PolicyViolationError` rather than a stale selection.

Source digests, hidden permissions, policy fields, private rules and identity data are not serialized into public receipts or model-visible inputs. Tests mutate policy contents in-place during retrieval, scanning and contract matching, plus malformed compiled indexes and a legitimate still-selectable catalog.

**Limits:** This read-only selector does not authorize execution, authenticate a principal, provide an atomic transaction across threads, freeze dynamically changing availability-predicate state, or constitute an independent E2 benchmark. The invoking host must reauthorize and validate the complete native schema immediately before any physical operation. No routing default, model, frozen source score or published release changes. S02 stays ENGINEERING_ONLY, E2 qualification stays 0/19, v0.18 release and model promotion HOLD.
