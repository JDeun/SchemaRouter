# Post-hoc overlap audit of the immutable ServiceNow native E5 DEV archive

**Evidence type: EXPLORATORY / POST-HOC, not preregistered.** This was designed
*after* inspecting the negative original E5 K5-vs-lexical K5 scores and the
six changed cases. It cannot be treated as a statistically independent
holdout, an agent-level task-completion result, or a product candidate gate.

Source and lock:
- Existing original [#1464 genuine source/model run #38909470584](https://github.com/JDeun/SchemaRouter/actions/runs/38909470584)
- [Original unchanged archived ZIP artifact #12049273340](https://github.com/JDeun/SchemaRouter/actions/runs/38909470584/artifacts/12049273340)
- Original ZIP SHA-256: `4dd548ff90da0c748ad886c18a405dc02a599802c7178d262a525a2524b582aa`
- Original raw `report.json` SHA-256: `4b82ffee9b55b4f8eae86a8cde87bec28429edda7d22afddc28789a18dce0237`
- Original raw `servicenow-readonly-tools.json` file SHA-256: `0bfddf03f20811ee8d0b5b34221e1b14868622f9350bebcf62e1003fbad6ade8`
- Publisher original 12 native readonly contracts digest `006045422791939ff603420080e2f759de38a19329eeb0c1b80e264ab4897940` from original Xerrion revision `5bcb83b29ab5b30aee07cabaa8df974881c47126`.
- Real local CPU E5 model revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`.
- Exactly the same developer-visible **20 supported + 4 unsupported, English-only** published questions in `benchmarks/external-validation-servicenow-platform-mcp-dev-v1/cases.json`.

## Source-only derivation

For each original query, start with the original `lexical_k5` ordered five
native IDs. Append each `e5_k5` ID not yet present, in original E5 order.
No model recall or scoring is rerun. The resulting list has **variable width
5–10**, not K5. Verify the SHA-locked raw inputs; original 12-route ranking
permutation, exact K3/K5 prefixes, exact case prompts, original source-declared
input schema fields and original measured per-case macro/micro metrics. Recompute
native schema bytes and required-tool/field coverage directly from registered
original source + published case labels; reject missing, duplicate or modified
IDs, altered original score or unsupported gold.

## Exploratory findings, NOT a strict-budget win

From the raw original archived report (manual independent read):

| Same unchanged original DEV | Lexical K5 | E5 K5 | Post-hoc K5 union |
| --- | ---: | ---: | ---: |
| Supported required-tool hits (20 supported, one required each) | 17/20 = 85% | 15/20 = 75% | **19/20 = 95%** |
| Mean model-visible original MCP contract bytes, all 24 | 10,108.54 | 9,536.13 | **13,778.25** |
| Mean native tools exposed, all 24 | 5 | 5 | **7.1667** |
| Unsupported questions with nonempty tool candidates | 4/4 | 4/4 | 4/4 |

The union still misses `sn-dev-006`. Per-query union-width histogram:
5:1, 6:5, 7:9, 8:7, 9:2, 10:0. Versus strict K5 lexical, the union exposes
**~36.30%** more original native schema bytes, while not solving OOD/no-fit.
The net **+10 percentage points** shown here is a *recall upper bound from
a looser variable K*, not a strictly comparable K5 result, real latency
SLO, calibrated safety evidence, task execution or a deployable strategy.

Study outputs explicitly forbid model promotion and release. There are
**no independent unseen queries, cross-lingual KO/JA ServiceNow tasks,
external real actions, human-maintainer approved gold, or complete agent
traces** in this archive. The experimental union was defined only after
the E5 failure and thus cannot qualify a commercial fusion score.

## Reproduction

Run the repository-only `ServiceNow Native Published DEV K5 Overlap Audit`
GitHub Actions workflow to retrieve the exact already published artifact
and produce an independently audited archived `overlap.json`. The workflow
needs no ServiceNow tenant, E5 model installation, GPU, API payment, or
tool execution. An original artifact expires after retention; failure to
retrieve it is an explicit **unavailable evidence** result, not permission
to reconstruct the source or fabricate a replacement.

To consider production recall augmentation, first preregister **new, genuinely
disjoint maintainer-authored tasks** across providers and EN/KO/JA, a fixed
schema-byte or token budget, acceptable latency, explicit unsupported/no-fit
and security false-positive gates, and paired downstream agent success.
**#1228/#1339/#1346 remain open; v0.18 release PR #1356 HOLD.**
