# M0 #1532 — Original lexical scoring canary noninterference (E0)

Date: 2026-10-19. Dependency #1602 was merged before this PR can be considered for review. This is strictly a principal-paired local regression, not an independent evaluator.

## Security/correctness root cause

Even after #1602 removed source-authored ToolSpec and EndpointSpec descriptions from the scoped analyzer and user-visible candidate, the native SchemaPlanner had an upstream side channel: _score_endpoint used the ORIGINAL ToolSpec.description with an otherwise principal-scoped EndpointSpec. The same unapproved description could therefore increase the published numeric relevance score, change Top-K ordering or appear in ScoreComponent.matched. The optional semantic candidate recall request also interpolated the original source ToolSpec.description.

## Narrow patch

- In the original planner _candidates and _semantic_recall_catalog only, use a temporary ToolSpec with only public canonical tool.name-derived words in its description for lexical scoring **iff** endpoint_transform produced a distinct principal-scoped EndpointSpec. This preserves safe spaced identifier matching (retry_records -> retry records) without private source-authored descriptions. Return the original ToolSpec identity in the _Candidate for source fingerprints/registered invoker and policy witnesses. For unrestricted endpoints no copy or scoring change.
- In structural specificity, apply the same temporary scoring tool if the actual _Candidate has an explicitly projected visible endpoint. Avoid another source description rank side channel.
- The optional candidate-recall decision-request description must omit original tool description for scoped candidates. It retains canonical visible output field identities.
- All provider source definitions, methods, original endpoints, authorization predicates, execution payload schemas and fingerprints are unchanged. This patch introduces no new model selection backend and no execution grant.

## E0 test and exact limitations

Paired independent local registries that differ only in the original ToolSpec.description use an identical principal with visible_fields restriction. They must produce identical public score, score_components, matched_fields and route identity for queries including the adversarial canary and the canonical visible field. Their original source fingerprint must differ and remain source-correct. A separate unrestricted principal test confirms the original public/source description still contributes to lexical score. The optional semantic candidate-recall choice description must not include the source canary.

The first blank-description version falsely refused an existing scoped retry_records plan and broke retry-time scope revocation tests; we corrected it by deriving deterministic public name words and added a mandatory exact plan/retry regression to the dedicated suite. This is **not** general private-data noninterference. Original tool/endpoint identifiers, license/source_type/provider, server_projection, auth descriptions and semantic IDs are still potential side channels; user query itself is not a source secret. Model-generated text, multilingual aliases, API/invoker behavior, 500-tool recall, repeated/adaptive trajectories and independent E2 have not been measured. #1602 must merge first; M0 #1532 remains open. #1356 release stays HARD HOLD.
