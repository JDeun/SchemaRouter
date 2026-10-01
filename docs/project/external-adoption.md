# External adoption and validation plan

Issue #584 tracks evidence that exists **outside the maintainer's own repository**. The goal is not
to collect endorsements. The goal is to make it easy for another project to evaluate a concrete
SchemaRouter integration, publish what happened, and keep limitations visible.

## Outreach rule

Use a contribution-first sequence:

1. understand the target project's existing tool/MCP abstraction;
2. build or propose the smallest reproducible integration;
3. show a runnable example or focused PR;
4. ask whether the integration is useful to them;
5. only after real use/evaluation, request permission to cite the project, maintainer, logo, or quote.

Never ask for a star as the primary action.

## Candidate set — checked 2026-10-01

These are **candidates**, not claimed users.

| Project | Existing relevant surface | Smallest useful SchemaRouter evaluation | Evidence we would want |
| --- | --- | --- | --- |
| PydanticAI | toolsets, MCP, deferred tools, ToolSearch | implement an external/example ToolSearch strategy backed by SchemaRouter retrieval over the same toolset | candidate recall, context/tool-schema reduction, no change to PydanticAI execution authority |
| OpenAI Agents SDK (Python) | MCP servers, dynamic per-run tool filters, approvals/guardrails | use SchemaRouter retrieval to produce the dynamic MCP allow-set while leaving Agents SDK invocation/approval behavior intact | filter parity, shortlist size, task success, no approval bypass |
| lastmile-ai/mcp-agent | MCP connection lifecycle and composable agent workflows | let mcp-agent own MCP sessions while SchemaRouter ranks/structures a large discovered tool catalog before exposure | catalog size, shortlist size, task completion, lifecycle compatibility |
| Hugging Face smolagents | Tool abstraction, MCP ToolCollection, LangChain tool reuse | expose a bounded SchemaRouter-selected tool collection to a smolagents agent | selected-tool recall, schema/context size, task success |
| Agno | large Toolkit ecosystem and MCPTools include/exclude surfaces | map SchemaRouter retrieval results to a per-request bounded toolkit/MCP tool list | tool-list reduction, task success, added latency, incompatibilities |
| CrewAI | BaseTool/custom tools and MCP tools | create a small external bridge/example that turns selected registered endpoints into CrewAI tools | bridge correctness, selected-tool recall, execution-boundary notes |
| Langflow | visual MCP Tools component and agent flows | prototype a custom component/example that performs typed capability retrieval before the agent tool step | usability in a real flow, configuration friction, result shape preservation |
| Letta | explicit MCP list/schema/search/call workflow with ranked search | treat as an **independent comparison/reproduction target**, not an adoption pitch; compare SchemaRouter's typed field/capability contract with Letta's existing MCP search workflow | reproducible comparison, unsupported-query behavior, schema/context differences |

Canonical repositories/docs should be re-checked immediately before any upstream issue or PR because
these projects evolve quickly.

## Why these targets

The candidates already have one or more of:

- many tools/toolsets;
- MCP discovery;
- dynamic tool filtering/search;
- agent framework integration points;
- explicit tool schemas;
- a realistic place where bounded capability retrieval can be evaluated without asking the project
  to replace its runtime.

That makes the proposed evaluation falsifiable. If their native search/filtering already solves the
same problem better, that is useful evidence too.

## Project-specific contribution notes

### PydanticAI

Current fit:

- toolsets gather multiple tools;
- MCP is a first-class capability;
- deferred tools can be searched through ToolSearch;
- custom search strategies exist.

Do **not** pitch SchemaRouter as replacing PydanticAI ToolSearch. The useful experiment is whether
SchemaRouter's field-aware typed capability retrieval is a valuable custom strategy or external
toolset boundary.

First contribution should live in SchemaRouter or a tiny external example package until Pydantic
maintainers indicate that an upstream example/listing is welcome.

### OpenAI Agents SDK

Current fit:

- local MCP servers expose static and dynamic `tool_filter`;
- dynamic filters receive run/agent context;
- approval policies and input/output guardrails remain in the SDK.

A clean experiment is:

```text
run query
  -> SchemaRouter retrieve candidate tool IDs
  -> Agents SDK dynamic tool_filter exposes that subset
  -> Agents SDK keeps its own approval/invocation semantics
```

This is deliberately retrieval-only integration. It should not duplicate or bypass SDK approval
authority.

### mcp-agent

mcp-agent already owns MCP connection/session lifecycle. Avoid replacing that lifecycle.

The experiment should import/compile the discovered schema surface for ranking and preserve
mcp-agent as the orchestrator. If tool schema conversion loses information, record that as a
limitation rather than silently filling it in.

### smolagents

smolagents can use MCP and other tool sources. A bounded collection experiment can test whether a
large mixed tool set benefits from SchemaRouter retrieval before model exposure.

Prefer a self-contained example over a new permanent core dependency.

### Agno

Agno's MCP/toolkit layer already has explicit include/exclude surfaces. This is a good place to test
whether a query-dependent SchemaRouter shortlist adds value beyond static filtering.

Do not claim a security improvement merely because fewer tools are shown; Agno's own policy/runtime
remains authoritative for its execution path.

### CrewAI

Start with an external bridge/example around its normal tool abstraction. Keep the proof small:
typed selection and schema preservation are enough. Do not add another agent lifecycle.

### Langflow

This is a higher-effort UI/integration target. A custom component can be useful only after the
lower-friction Python integrations prove the contract. Treat it as `help wanted`, not the first
outreach.

### Letta

Letta already exposes MCP tool search/schema/call as an explicit workflow. That makes it more useful
as independent prior-art/evaluation than as a "please adopt SchemaRouter" target.

A fair comparison should record where the abstractions differ rather than forcing a winner.

## Evaluation package

A proposed adopter should not need to read the research history. Give them:

1. stable install:
   ```bash
   pip install schemarouter
   ```
2. one framework-specific runnable example;
3. the 30-second context-reduction demo;
4. the trust/evidence page;
5. this minimal evaluation protocol.

### Minimal protocol

Record:

- target project + version/commit;
- SchemaRouter version/commit;
- Python/runtime/hardware;
- original number of model-visible tools;
- shortlisted number of tools;
- full versus bounded serialized schema/context size;
- required-tool/capability recall for the test requests;
- task completion or explicit failure;
- added routing latency;
- invalid/unsupported query behavior;
- authority/policy integration notes;
- conversion gaps or unsupported schema constructs.

Use at least one request where no registered capability should be selected.

Do not compare token cost unless the measurement is genuinely model-token based. Serialized byte
counts must stay labeled as bytes.

## Outreach message template

Use a short project-specific note, not a mass template.

> Hi — I maintain SchemaRouter, an MIT-licensed Python layer for typed capability retrieval and
> schema-aware execution in large agent tool catalogs.
>
> I noticed that <project> already has <specific tool/MCP surface>. Rather than asking you to adopt
> another framework, I'd like to test one narrow integration: <specific bounded experiment>.
>
> I can prepare the example/PR and keep <project>'s existing runtime/approval semantics authoritative.
> If the result is not useful, I'll publish that limitation as part of the evaluation.
>
> Would a small reproducible example like that be useful, and if so, where would you prefer it to
> live?

Do not send this unchanged to several projects.

## Evidence levels

External evidence should be labeled explicitly:

| Level | Meaning |
| --- | --- |
| E0 | maintainer-owned example only |
| E1 | external maintainer/user evaluated the example publicly |
| E2 | downstream repository includes SchemaRouter in a reproducible branch/PR/test |
| E3 | downstream default/released path uses SchemaRouter |
| E4 | independent benchmark/reliability reproduction published |

A GitHub star, repository mention, or friendly reply is not an adoption level.

## Public tracking

For each contact/evaluation, record only public or permissioned information:

| Project | Contact/evaluation URL | Level | Status | Evidence | Limitation / next action |
| --- | --- | --- | --- | --- | --- |
| _none yet_ | — | E0 | candidate set prepared | this page | external outreach/evaluation not yet performed |

Do not publish private email addresses, private conversations, or unpublished organization names.

## Case-study promotion rule

A project may appear in a README "Used by" section only after:

- at least E2 evidence exists;
- the integration/use is still current;
- the name/logo/quote usage has permission when required;
- the case study includes a measurable outcome **and** a limitation.

See [External case-study template](case-study-template.md).

## Feedback loop

Recurring adopter friction should result in a bounded issue in one of:

- onboarding/docs;
- adapter conformance;
- framework bridge;
- packaging/compatibility;
- benchmark/evidence.

Do not turn each adopter request into a new core abstraction.
