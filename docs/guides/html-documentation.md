# Human-readable documentation

A human-readable API page is weaker evidence than OpenAPI or MCP. SchemaRouter therefore treats it
as a **proposal source**, not an executable schema source.

## Inspect a documentation page

```python
from schemarouter import SchemaRouter

async def documentation_model(payload: dict) -> dict:
    # Send payload to a structured-output model.
    ...

router = SchemaRouter()
proposal = await router.inspect_url(
    "https://docs.example.com/api",
    model=documentation_model,
)
```

The proposal contains:

- a grounded/non-grounded status;
- a proposed `ToolSpec` when enough evidence survives;
- a grounding score;
- uncertainties;
- rejected items.

## Grounding rule

Every accepted endpoint, parameter, and field must carry an evidence quote that appears in the
fetched document.

```text
model proposal
 -> exact quote present?
    -> yes: candidate survives
    -> no: candidate is rejected
```

Scripts, styles, noscript content, and SVG are removed before the model sees the document text.

## Approval is a separate authority transition

A grounded proposal is still non-executable.

```python
router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
    min_grounding_score=0.8,
)
```

Mutating methods require an additional explicit opt-in:

```python
router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
    allow_mutations=True,
)
```

Execution policy still applies after approval, so approval does not bypass the runtime side-effect
gate.

## Redirect and URL safety

Documentation URLs must be absolute HTTP(S) URLs without embedded credentials. Redirects are limited
to the original origin.

SchemaRouter deliberately supports local/private endpoints. If untrusted end users can supply URLs,
the hosting application must add its own URL admission and egress policy. See the
[security threat model](../security/threat-model.md).

## Limitations

The current path reads the initial HTTP response. Documentation that requires browser-side
JavaScript rendering or spans many pages may need a future crawler/rendering adapter.
