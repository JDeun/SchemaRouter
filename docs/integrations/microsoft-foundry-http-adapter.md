# Microsoft-Decision-1 Foundry HTTP adapter (opt-in, #1324)

**Status:** structural/mock-transport engineering only. This code has **not**
been exercised against a live Azure Foundry deployment and has **no measured**
quality, speed, no-fit accuracy or cost. Do not set it as a default backend.

Official provider API:
https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision

Microsoft Foundry documents a native decision endpoint at
`<resource-endpoint>/providers/microsoft/v1/systemone`, with a `model`
value equal to your **deployment name**, `state` plus typed `questions`,
and a JSON `answers` response. This differs from the existing
`SystemOneDecisionBackend`'s TypeSafe SDK `response.choices` contract.

## Explicit opt-in use

```python
import os

from schemarouter import DecisionOption, DecisionRequest, choose_sync
from schemarouter.integrations import MicrosoftDecisionOneFoundryBackend

backend = MicrosoftDecisionOneFoundryBackend(
    resource_endpoint=os.environ["AZURE_ENDPOINT"],  # HTTPS Azure origin
    deployment=os.environ["DEPLOYMENT_NAME"],        # YOUR deployment name
    api_key=os.environ["AZURE_API_KEY"],
)
request = DecisionRequest(
    query="Cancel the customer's order",
    options=[
        DecisionOption(
            id="orders_lookup",
            description="Read order data; CANNOT cancel an order",
        ),
        DecisionOption(
            id="none_of_above",
            description="None of these routes performs the operation",
        ),
    ],
)
decision = choose_sync(backend, request)
if decision.abstained:
    # DO NOT issue a tool call: ask for clarification / human review.
    ...
else:
    # Host policy MUST still verify the selected action/arguments/principal.
    # This decision is advisory, NOT an execution authorization.
    ...
```

Authentication: exactly one `api_key` or `bearer_token` may be provided.
Only HTTPS resource origins are accepted. The application owns credentials
and **pays for any real `decide()` invocation**. No hidden fallback to
Jev, Laya or OpenRouter exists; OpenRouter has a separate Decisions API.

Only the `choice` question is implemented; `noul` and `score` are
NOT silently interpreted as tool IDs. The model must select among actual
string option IDs, and `none_of_above` is required by default and yields
`DecisionResult(abstained=True)`. Without an explicit valid no-fit
option, the request fails before network I/O. Caller-provided option
metadata and decision context are not sent by default. Set
`include_context=True` **only** with the host's disclosure approval.

The documented response's selected option is authoritative only as a
**bounded suggestion**. The official documentation does not fix the
probability field's exact serialized representation, so the adapter
does **not invent a confidence** when `probabilities` is absent. If a
per-option `probabilities` map is provided, it must contain only the
original option IDs and finite 0–1 numbers. Malformed types, out-of-set
IDs, duplicate JSON keys, nonfinite constants, invalid token counts,
oversized responses or HTTP failures raise `PlanningError`. If the
provider supplies per-option probabilities, the returned choice must be
their **unique highest-probability option**; a tie or contradictory
`choice` is an error, **not** a license to use a lower-probability tool.
This is a structural response consistency check, not model calibration. The
`score=None` fallback is **not** a calibrated confidence and must
not be promoted to 1.0 or used as a threshold.

## Verification scope

Unit tests use `httpx.MockTransport` only, verify Azure API-key and Entra
Bearer header shapes, request state/criteria, opt-in privacy, exact
no-fit behavior, invalid response rejection, and absence of response-body
or credential content in error messages. They do not call Microsoft,
use real accounts, prove exact response fidelity, or create a bill.

Remaining #1324 blockers: **actual response-body/API compatibility** via
an authorized paid deployment, exact deployment/model version record,
published unit pricing at run time, downstream no-call enforcement (#1291),
and a *new* independently reviewed, disjoint supported/near-domain
unsupported/forbidden evaluation cohort. No historical ClicShopping DEV
tuning, Laya negative-run reuse or frozen 0.14 alteration.

### Bounded transport and no-request guarantees

Before making any HTTP request, the adapter checks the complete option
envelope (including bypassed Pydantic `model_copy(update=...)` fields),
requires at least **one real route as well as the no-fit alternative**,
serializes outbound JSON with `allow_nan=False`, and rejects oversized
requests. A no-fit-only catalog therefore **never incurs a model call**.

The HTTP body is read **incrementally** via `httpx.Client.stream` with a
hard 1 MiB decoded-response limit. It stops reading and closes the stream
when the limit is exceeded, rather than buffering an unbounded response
before checking `len(content)`. Mock-stream and oversized/invalid-context
tests exercise these safeguards. They do not prove actual provider behavior.
