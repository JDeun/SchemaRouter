# Research knowledge index — agent and maintainer entry point

> **Navigation, not evidence.** This index links canonical research and implementation records.
> Never promote a development-only result to independent validation, or copy benchmark numbers
> here as though this page were the experiment ledger.
>
> Tracking: [#1712](https://github.com/JDeun/SchemaRouter/issues/1712).
> Canonical cross-session research tracker: [#200](https://github.com/JDeun/SchemaRouter/issues/200).

## Read in this order

1. [Research program and current gates](research-program-2026.md): current priorities,
   counterexamples, research scope and non-negotiable constraints.
2. [Research governance](governance.md): preregistration, development, freeze, calibration,
   blind-final evaluation and the required session-resume sequence.
3. [Tool-routing landscape](tool-routing-landscape.md): external OSS comparisons,
   already-tested approaches, negative outcomes and no-repeat decisions.
4. [Prior-art roadmap](prior-art-roadmap.md): literature and historic hypotheses.
5. [Routing status](routing-status.md) and [experiment index](experiment-index.md):
   historical experiment interpretation.
6. [Experiment ledger](../../benchmarks/research-experiment-ledger.json) and
   [prior-art registry](../../benchmarks/research-prior-art-registry.json):
   machine-readable provenance; consult these **before** citing performance claims.
7. [Research milestone plan](../../.github/RESEARCH_MILESTONES.md): *proposed*
   milestone-to-issue mapping; verify live assignments before claiming completion.

## Evidence-to-implementation navigation

| Stable topic | Question / decision | Evidence source | Implementation or interface | Tracking | Evidence status |
| --- | --- | --- | --- | --- | --- |
| SR-R01 | Typed schema and source authority | [Research program](research-program-2026.md) | [Architecture](../architecture.md) | [#1450](https://github.com/JDeun/SchemaRouter/issues/1450) | Design and partial tests; external security gate not independently cleared |
| SR-R02 | Native G5 graph, FieldGroups and fixed K | [Research program](research-program-2026.md) | [Capability graph](../../src/schemarouter/capability_graph.py) | [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) | Development evidence; independent promotion pending |
| SR-R03 | EN/KO/JA retrieval and no-fit | [Research program](research-program-2026.md) | [Routing status](routing-status.md) | [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) | Frozen negative evidence retained; subsequent DEV is not blind |
| SR-R04 | OSS tool selection and integration | [OSS landscape](tool-routing-landscape.md) | [Pydantic AI validation](../project/external-validation-pydanticai.md), [Agents SDK validation](../project/external-validation-openai-agents.md) | [#644](https://github.com/JDeun/SchemaRouter/issues/644), [#645](https://github.com/JDeun/SchemaRouter/issues/645) | Limited E0 integration; not broad task success |
| SR-R05 | Open-set rejection and prior art | [Prior-art roadmap](prior-art-roadmap.md) | [Experiment index](experiment-index.md) | [#388](https://github.com/JDeun/SchemaRouter/issues/388) | Mixed and rejected historical approaches |
| SR-R06 | Full-catalog versus bounded retrieval | [Research program](research-program-2026.md) | [Experiment ledger](../../benchmarks/research-experiment-ledger.json) | [#432](https://github.com/JDeun/SchemaRouter/issues/432) | Frozen independent negative result; do not overwrite |
| SR-R07 | Research lifecycle and reproducibility | [Governance](governance.md) | [Experiment ledger](../../benchmarks/research-experiment-ledger.json) | [#200](https://github.com/JDeun/SchemaRouter/issues/200) | Process documented; individual artifact completeness not audited here |

**Interpretation:** A link to source code proves a navigation path, **not** that the
linked implementation satisfies a research gate. PR merge, CI-green, development
benchmarks, independent confirmation and release approval are distinct states.
Check live issues and PRs before updating this table.

## Before starting a new experiment

1. Search this index, the OSS landscape, prior-art registry and experiment ledger.
2. Search GitHub issues and open PRs for the same hypothesis and exact evaluation slice.
3. Record the existing decision, negative evidence and remaining uncertainty.
4. Create or resume a canonical issue; preregister allowed and forbidden data,
   frozen configuration, baseline, success and abstention gates.
5. Link **issue → protocol → run/artifact → ledger → decision → implementation PR**.
6. Update this navigation table only after the original evidence and decision records
   have been committed. Do not silently change historic statuses.

## Agent retrieval contract

- Start with this small index; open only the relevant canonical sources.
- Prefer source-owned schemas and the ledger over summaries or chat recollection.
- Never treat semantic similarity, score > 0, a retrieved candidate, or a successful
  CI run as execution authority or proof of downstream task completion.
- If an evidence/implementation link cannot be verified, mark it **unverified**.
- Keep English/Korean navigation aligned; avoid duplicating metric tables in translations.
- For a new session, follow [governance's resume order](governance.md#session-resume)
  and verify live issue/PR/workflow state.
