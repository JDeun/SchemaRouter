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
    k=500,  # must cover whole authorized catalog; otherwise abstain
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

- **Require RBAC configured and host-supplied `PrincipalContext`**. All candidate metadata comes exclusively from `router.retrieve_authorized`, including principal data-scope projections. No raw registry bypass or privileged full-catalog schema leaking.
- Contract is strictly **read-only** with 1–8 exact declared query enum or output fields. The required conjunction is matched against each *already authorized* candidate's typed `ParameterSpec.json_schema.items.enum` and visible output-field names/semantic IDs. It never looks for substring relevance or imports a human-oracle gold route.
- **No candidate gets executed**. A receipt containing a route/fingerprint is not a dispatch token; host-side authorization and runtime execution policy remain mandatory.
- If the authorized Top-K is **truncated**, respond `incomplete_authorized_catalog` rather than claiming uniqueness over unexamined routes. This currently means hosts may request an expensive full authorized surface; it is a safety-first tradeoff, **not an optimized 500+ route contract index**.
- With no matches, zero candidates, or multiple matches, **abstain**. No fallback to highest lexical/E5 score. If registry version changes or malformed/forged Pydantic envelopes appear, **deny** rather than issuing a selection.
- Any model-suggested intent, action or variable is **untrusted data**. The host must verify semantic correctness and complete field requirements independently. This API does not infer temporal domain, variable synonyms, units, missing required input arguments, downstream data presence, or final task success.

## Evidence and limitations

This API follows original real Open-Meteo publisher OpenAPI DEV evidence [#1440–#1446](https://github.com/JDeun/SchemaRouter/pull/1446), where local multilingual E5 successfully improved **tool candidate recall** on one provider but naive field inference over 632 enum variables failed a strict author-gold proxy (`Top5 2/24`). Earlier manually supplied *oracle* field conjunctions could select **12/27** exact routes with high abstention, **not** production automatic accuracy. These are separate capabilities and evidence tiers.

Add offline tests for RBAC, denied principal, data-scoped invisible output, exact 2-field conjunction, ambiguous one-field match, truncated Top-K, forged model-copy contract, stale registry and **zero tool invocations**. Full protected CI/CodeQL and targeted Ubuntu GitHub Actions test run are required before product merge. New independent external provider/user agent success remains necessary for v0.18 release and any commercial-quality claim.

**v0.18.0 #1356 remains HOLD**; historical independent #432/#424 failures unchanged.
