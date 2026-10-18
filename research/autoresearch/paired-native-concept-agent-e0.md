# Original-agent paired lexical vs declared concept fixed K5 (E0 only)

Issue [#1554](https://github.com/JDeun/SchemaRouter/issues/1554);
parent [#1553](https://github.com/JDeun/SchemaRouter/pull/1553);
owning integrated evaluator [#1477](https://github.com/JDeun/SchemaRouter/issues/1477);
original mission [#1530](https://github.com/JDeun/SchemaRouter/issues/1530).

## Why this is not another agent implementation

The paired E0 driver calls the **unchanged**
`run_generated_episode` and `FrozenCorpusExecutor` under the already isolated
`EVAL-FIXED5-OPTIN` condition. The fixed baseline callback calls the original
`router.retrieve_authorized(query, principal, k=5)`; the comparison callback
uses `AuthorizedConceptFixed5Selector` → native
`retrieve_authorized_concepts` → native FieldGroup **before-K** filter.
Both callbacks run against the same registered source, exact original query,
source-/policy-/principal-scoped `AuthorizedAgentToolSurface` and native
endpoint/tool fingerprint witness. Candidate IDs never come from task gold.

The trusted scorer holds fixture gold and stage transitions; neither
callback receives the fixture, required route, expected arguments, observation,
or final task verdict. The same agent factory creates a fresh agent instance
for each condition. **Callers must independently attest** that their agent
factory genuinely uses the same model/weights, decoding parameters and
hardware in both arms; this function cannot prove that. For its local
unit tests it uses an intentionally scripted model stub.

## What is actually measured

The driver returns **only aggregate, allowlisted**, no-query/no-task-ID
metrics: paired scripted-fixture passes/wins/ties; EN/KO/JA case counts;
supported passes versus unsupported scripted no-call passes; candidate count;
input/tool-schema tokens and observed selection/episode milliseconds.
Untrusted or unsafe telemetry, shifted route membership, source fingerprints,
principal/policy drift, invalid gold task identity, unsafe destructive
execution and mutated host ontology fail closed.

All numbers from this workflow have evidence tier
`E0_SCRIPTED_DEV_NOT_INDEPENDENT`. A high fixture pass rate is not an
LLM's ability to discover or correctly invoke hidden tools. A lexical miss
in a deliberately author-constructed example is *not* a generalization or
statistically significant improvement. The script does **not** claim an
independent case author, real model, live original provider, end-user final
answer, calibrated no-fit or completed task success.

## Promotion and external intake

The publishable study must use externally authored and verified #1346 source,
gold and access controls, EN/KO/JA query-disjoint supported + unknown/forbidden
cases, frozen SHA and agent/model provenance. Feed it into existing #1477
evaluator with the identical native catalog, authorized principal, fixed K5,
seed, token/context limits and original trusted tool execution. Compare
paired true route/field coverage and final grounded response/task pass, and
record false refusals, unsupported false accepts, CPU p50/p95/p99/RSS,
language strata, statistical uncertainty and full source/agent revision.
Without these, the result stays E0 and cannot authorize a release.

Never change #432 frozen negative outcome, default production
`retrieve_authorized` or v0.18 #1356 HARD HOLD.
