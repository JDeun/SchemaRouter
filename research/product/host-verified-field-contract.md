# Host-verified field contract selection (opt-in, read-only)

Commercial hosts frequently need to distinguish similarly worded OpenAPI/MCP capabilities without granting a model permission to infer or execute a tool action. The product API `select_authorized_field_contract()` offers a **deliberately conservative, zero-execution** contract diagnostic. It is **NOT an automatic natural-language required-field extractor, a no-fit classifier or an authorization grant**.

## Example

```python
from schemarouter import (
    HostFieldContract, RequiredEnumValue, select_authorized_field_contract,
)

# router MUST have an explicit host-owned AuthorizationPolicy.
# principal MUST come from verified identity claims — SchemaRouter does
# not authenticate it. requirement values must come from trusted host inputs,
# never directly from E5, LLM predictions, client-controlled tool text,
# or adversarial fields inferred by an agent.
receipt = select_authorized_field_contract(
    router,
    "Fetch wave height and ocean current observations",
    principal=trusted_principal,
    k=500,  # must cover the whole currently visible, available catalog
    contract=HostFieldContract(
        operation="read",
        required_enums=[
            RequiredEnumValue(parameter="hourly", value="wave_height"),
            RequiredEnumValue(
                parameter="hourly", value="ocean_current_velocity",
            ),
        ],
    ),
)
if receipt.disposition == "selected":
    # This is only a DIAGNOSTIC. Independently reauthorize, verify version,
    # validate arguments/operation/evidence and apply the execution gate.
    print(receipt.selected_route_id)
```

## Safety invariants

- **Require RBAC configured and host-supplied `PrincipalContext`**. Candidate fields used for matching come exclusively from `router.retrieve_authorized`, including principal data-scope projections. The selector also performs an **internal-only** registry scan through the same principal RBAC, local availability and data-scope endpoint projection. No excluded route identity, count, or schema is surfaced.
- Contract is strictly **read-only** with 1–8 exact declared query enum or output fields. The required conjunction is matched against each *already authorized* candidate's typed `ParameterSpec.json_schema.items.enum` and visible output-field names/semantic IDs. It never looks for substring relevance or imports a human-oracle gold route.
- Multiple required values for **the same query parameter** must be satisfiable in a *single call*: one scalar enum can satisfy only one distinct value, while a declared array `items.enum` can satisfy multiple values only if `maxItems` permits that many items. Values distributed across multiple same-named declarations cannot jointly prove a match. Unsupported or contradictory typed schemas conservatively fail to match rather than granting an impossible unique receipt.
- **No candidate gets executed**. A receipt containing a route/fingerprint is not a dispatch token; host-side authorization and runtime execution policy remain mandatory.
- If the authorized Top-K is **truncated**, respond `incomplete_authorized_catalog` rather than claiming uniqueness over unexamined routes. This currently means hosts may request an expensive full authorized surface; it is a safety-first tradeoff, **not an optimized 500+ route contract index**.
- With no matches, zero candidates, or multiple matches, **abstain**. No fallback to highest lexical/E5 score. If registry version changes or malformed/forged Pydantic envelopes appear, **deny** rather than issuing a selection.
- Any model-suggested intent, action or variable is **untrusted data**. The host must verify semantic correctness and complete field requirements independently. This API does not infer temporal domain, variable synonyms, units, missing required input arguments, downstream data presence, or final task success.

## Completeness semantics and privacy boundary (#1450)

- `CapabilityRetrieval.total_ranked` is **not** an authorization-completeness witness. Without data-scope projection it normally counts planner-scored routes before Top-K; with data-scope projection the current `_project_retrieval_data_scope()` resets it to the number of candidates **already returned and surviving projection**. Therefore `total_ranked == len(candidates) == k` does **not** independently prove completeness. This public field remains unchanged for compatibility.
- The selector computes an **ephemeral private route-identity witness** for the **current registry version and verified principal**. It filters the registry through `AuthorizationPolicy.visible`, the same planner-local availability predicate, and the same `_data_scope_endpoint_view` transformation used by principal-scoped retrieval. Entirely invisible output scopes are excluded; a field hidden from a visible route remains hidden. This avoids false abstentions caused by separately counting denied, locally unavailable, or fully data-hidden routes.
- The candidate identities must be a subset of the private witness, the registry/policy/availability context must remain stable, and the complete witness must fit the candidate set; otherwise **deny** or `incomplete_authorized_catalog`. `total_ranked` excess is an additional conservative reason to abstain, never a substitute for the witness.
- Each returned candidate's **declared read/write flags, typed query parameters and visible output fields** must also equal the current principal-scoped publisher/registry contract during the same internal catalog scan. Valid route IDs and fingerprint-shaped strings alone do not authenticate a potentially forged retrieval envelope. This attests the metadata used for positive matching *including competing routes*, not external principal identity or an atomic concurrent snapshot. A mismatch raises a generic policy error and never produces a receipt.
- Returned candidates' **tool and endpoint fingerprints** are independently checked against the original, unprojected registered ToolSpec/EndpointSpec fingerprints (one tool hash per returned parent tool). Data-scoped visible fields remain separately verified; they must not overwrite the source identity on the receipt. A changed selected or competing candidate fingerprint fails closed before an authority receipt.
- **No hidden counts or routes enter public receipts.** Candidate count refers only to the authorized returned shortlist; there is no exported count of forbidden, unavailable, or data-hidden routes. The witness is not reusable across principals or registry versions and is not an execution authorization.
- This deliberately scans the visible catalog each time. Tail-latency, concurrent registry updates, mutable host availability callbacks, source fingerprint validity and downstream task utility require their own tests and external evidence. Never claim p95 improvement, complete commercial safety, or v0.18 release readiness from this change.

## Evidence and limitations

This API follows original real Open-Meteo publisher OpenAPI DEV evidence [#1440–#1446](https://github.com/JDeun/SchemaRouter/pull/1446), where local multilingual E5 successfully improved **tool candidate recall** on one provider but naive field inference over 632 enum variables failed a strict author-gold proxy (`Top5 2/24`). Earlier manually supplied *oracle* field conjunctions could select **12/27** exact routes with high abstention, **not** production automatic accuracy. These are separate capabilities and evidence tiers.

Add offline tests for RBAC, denied principal, data-scoped invisible output, exact 2-field conjunction, ambiguous one-field match, truncated Top-K, forged model-copy contract, stale registry and **zero tool invocations**. Full protected CI/CodeQL and targeted Ubuntu GitHub Actions test run are required before product merge. New independent external provider/user agent success remains necessary for v0.18 release and any commercial-quality claim.

**v0.18.0 #1356 remains HOLD**; historical independent #432/#424 failures unchanged.
