# Microsoft-Decision-1 — hosted decision-model intake (#1324)

**Status: discovery / no live SchemaRouter qualification. Not installed,
not a free local model, not a substitute for an execution authorization
policy.** Reviewed 2026-10-13.

## What it is

Microsoft released **Microsoft-Decision-1** on **2026-10-09**, a hosted
single-pass decision-scoring model post-trained from Qwen3.5-9B.
It returns structured `choice` (finite-option selection), `noul`
(binary probability), and `score` (ordered rating) results, not prose.
Microsoft's advertised 36-benchmark accuracy/speed is **vendor** evidence,
not a measured SchemaRouter comparison.

- Announcement: https://commandline.microsoft.com/microsoft-decision-1-model-foundry/
- Native deployment/API: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision
- OpenRouter: https://openrouter.ai/microsoft/microsoft-decision-1/

Microsoft documents an input price of **USD $0.042 per million tokens,
$0 for output** as of 2026-10-13. Foundry requires a billed Azure account,
deployment and authentication. OpenRouter likewise requires an account/API
key. The Microsoft-adapted weights have **not** been publicly released;
an open-weight Qwen3.5 base model is not the Microsoft decision checkpoint.

## Transport/API: not a proven SDK drop-in

Microsoft Foundry documents:

```text
POST <foundry-resource-endpoint>/providers/microsoft/v1/systemone
Content-Type: application/json
api-key: <foundry-key>
# OR: Authorization: Bearer <Entra access token>
```

The body has the same *conceptual* System One request fields:

```json
{
  "model": "<the-created-Foundry-deployment-name>",
  "state": {
    "query": "Cancel a customer's order."
  },
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "Select a supported route. Choose none_of_above if no registered route performs the requested action.",
      "criteria": {
        "orders_lookup": "Look up an order; cannot cancel it",
        "none_of_above": "No offered route supports the requested operation"
      }
    }
  }
}
```

The **Foundry `model` field is a deployment name**, not the
`microsoft/microsoft-decision-1` OpenRouter model ID. That OpenRouter ID
is used on OpenRouter's **Decisions API**, whose alpha route is separately
versioned; never interchange credentials or paths.

**SchemaRouter currently has `SystemOneDecisionBackend`, but it wraps the
TypeSafe SDK, with SDK client `system_one()` calls and parsed
`response.choices["selection"]`. Microsoft's *documented Foundry HTTP
response* instead uses `answers` and distinct Azure authentication.
Therefore neither a plain `SystemOneDecisionBackend(base_url=...)` nor
`--system-one-base-url` has been qualified to work against Foundry.
Likewise, OpenRouter model-ID swaps require response and SDK transport
verification.** A small independent HTTP/CallableDecisionBackend adapter is
the appropriate experimental integration boundary, with strict
local-option-ID and numeric probability validation; do not change planner
defaults merely to register a provider.

## No-fit detection and safety (#1291)

The model does **not** infer an implicit rejection option when a `choice`
is constrained to registered routes. Explicitly include a reserved
`none_of_above` candidate and use an independent, preregistered
supported/unsupported/near-domain/forbidden test cohort to measure:

- exact supported operation routing and supported false-refusal;
- unsupported false-match and correct no-fit rejection;
- probability calibration, order/wording perturbations and rate/transport errors;
- real request latency, input tokens, exact provider/deployment revision
  availability and dated costs.

A provider decision remains **advice**. Deny the reserved no-fit choice
before any tool call; on supported candidates, still require the host
authorization, schema/argument contract and execution no-match gate.
Never turn an `noul` score or arbitrary confidence into access authority.
Do **not** fit a threshold using previously published ClicShopping DEV
unsupported requests or rerun/retune frozen 0.14 #432/#424.

## Evidence and go/no-go

The Jev team's small 2026-10-11 OpenRouter comparison (one pass; 200
supported BFCL items and 240 no-fit items) reports no-fit rejection of
**92.5% Microsoft** vs **88.8% Jev** and median round trips of
**688ms vs 623ms** respectively. It is useful directional evidence
but is a provider-competitor-authored result, not a SchemaRouter
reproduction. Microsoft's mixed-provider latency headline is also
not a matched-serving comparison. Independent leaderboards have
disagreed on the overall model ordering.

This intake changes **neither** core execution code nor promotion targets.
The corresponding issue #1324 remains open until the concrete transport
is verified against an authentic provider response, the model identity is
recorded, and genuinely disjoint supported/unsupported results are obtained
without retrospective threshold tuning. This doc does not trigger
network calls, billing or an API deployment.
