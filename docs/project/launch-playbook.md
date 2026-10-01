# Developer launch playbook

This playbook turns SchemaRouter's existing runnable examples and public evidence into reusable
developer-facing launch material. It is designed for **qualified technical exposure**, not a
one-day star spike.

## Launch objective

A developer should understand this in under two minutes:

> SchemaRouter is a typed capability retrieval and schema-aware execution layer for LLM/RAG agents.
> It narrows a large tool catalog to the capabilities and fields relevant to the current request,
> then keeps execution behind registered schemas, local policy, and trusted bindings.

The primary call to action is:

```bash
pip install "schemarouter==0.14.0"
```

The unpinned `pip install schemarouter` path also resolves to the current stable release; the pinned form is used in launch material so a reproduced launch demo does not silently change later.

Repository: <https://github.com/JDeun/SchemaRouter>

Docs: <https://jdeun.github.io/SchemaRouter/>

Runnable examples: <https://github.com/JDeun/SchemaRouter/tree/main/examples>

## What to claim

Safe public claims should map to a reproducible artifact.

### Stable product

- stable release: `0.14.0`, Beta / pre-1.0;
- Python 3.10-3.14 are release-blocking CI targets;
- supports typed ingestion/execution paths across MCP, OpenAPI, OPTIMADE, GraphQL, OData,
  OpenRPC/JSON-RPC, Python/SDK bindings, LangChain/LangGraph, and LlamaIndex;
- retrieval/model signals do not grant execution authority;
- release artifacts include wheel, sdist, and SPDX SBOM, with provenance/verification mechanics
  documented in the public trust page.

### Controlled research evidence

One frozen 23-task Qwen3-0.6B B1 experiment recorded:

- SR-5 task pass: **91.30%**;
- FULL task pass: **68.48%**;
- SR-5 schema-token ratio: **5.42%**;
- required-route recall: **100%**.

This is controlled mechanism evidence on that workload. It is **not** a population-level claim that
SchemaRouter improves every agent, model, workload, or final answer.

The structural K3-vs-K5 promotion gate also produced a negative result and was not promoted. Keep
that result visible when discussing the research.

Verification index:
<https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/>

## What not to claim

Do not say:

- "SchemaRouter makes every agent more accurate";
- "SchemaRouter reduces tokens by 94.58% in production";
- "SchemaRouter is safer than all other routers";
- "Jev/Laya/Ollama is the best decision backend";
- "production proven" without an external adopter/case study;
- "used by" an organization without explicit permission.

Issue #15 remains the live decision-backend evidence track. Issue #584 tracks external adoption and
independent validation.

## Core launch narrative

### Problem

Agent stacks often push an entire tool catalog into model context. As the catalog grows, two
different problems get mixed together:

1. **retrieval** — which capabilities and output fields are relevant now?
2. **authority** — which registered operation is actually allowed to execute?

Sending every schema to the model does not solve either boundary well. It increases context, exposes
irrelevant fields, and can tempt an implementation to treat model-selected or remotely described
operations as executable authority.

### Approach

SchemaRouter inserts a typed boundary:

```text
user request
   -> required declared fields
   -> bounded registered capability candidates
   -> local validation/policy/binding checks
   -> trusted invocation
   -> raw output validation
   -> declared-field projection
   -> agent / RAG context
```

It is deliberately not another agent runtime. LangChain, LangGraph, LlamaIndex, or custom
applications can stay in control of orchestration.

### Why it matters

The design aims to reduce context pollution **without turning retrieval into permission**. Provider
metadata can describe a capability, but trusted local application state grants execution authority.

## 30-second demo

Use the deterministic context-reduction demo so the first impression does not depend on network
availability or API keys.

### Recording flow

Terminal:

```bash
git clone https://github.com/JDeun/SchemaRouter
cd SchemaRouter
python -m venv .venv
source .venv/bin/activate
pip install -e .
python examples/context_reduction_demo.py
```

Show, in order:

1. a 40-tool catalog;
2. one natural-language request;
3. the Top-3 typed capability retrieval;
4. the serialized full-catalog bytes versus bounded retrieval bytes;
5. the selected weather route at rank 1.

Overlay/caption:

> "Don't give the model every tool schema. Retrieve the typed capability surface needed for this
> request, then execute only through local contracts."

Do not label serialized bytes as model token counts.

## Five-minute technical walkthrough

### 0:00-0:40 — The failure mode

Show a large tool catalog and explain why "just send all schemas" creates unnecessary context and
mixes relevance with authority.

### 0:40-1:30 — Capability retrieval

Run:

```bash
python examples/context_reduction_demo.py
```

Explain `retrieve(..., k=3)` / `retrieve_executable(..., k=3)` and that candidates retain typed
input/output contracts.

### 1:30-2:40 — Real provider ingestion

Run the public no-auth OpenAPI example:

```bash
python examples/live_openapi_quickstart.py
```

Explain:

```text
external schema -> registered typed capability -> bounded plan -> validated execution -> typed result
```

### 2:40-3:30 — Framework fit

Show the LangChain/LangGraph/LlamaIndex examples and emphasize that SchemaRouter does not own the
agent graph or conversation runtime.

### 3:30-4:20 — Execution boundary

Show the trust model:

- fingerprints/bindings;
- input/output JSON Schema validation;
- local side-effect policy;
- destructive operations fail closed;
- schema drift does not silently replace accepted authority.

### 4:20-5:00 — Evidence and invitation

Open the trust/evidence page and example gallery. State the controlled B1 evidence with its exact
scope, mention the negative K3 result, and ask for feedback on real integration friction.

## "Why not just send all tool schemas to the LLM?"

Use this explanation when the question comes up:

> For a small fixed tool set, sending every schema can be perfectly reasonable. SchemaRouter targets
> the point where the catalog is large, heterogeneous, or operationally sensitive. It retrieves a
> bounded typed capability set and the required output fields, while keeping execution authority in
> local registered contracts. The goal is not "the model must never see schemas"; it is "the model
> should not need the entire catalog, and schema relevance should not become execution permission."

Key distinctions:

| Concern | Sending all schemas | SchemaRouter boundary |
| --- | --- | --- |
| catalog context | whole selected catalog | bounded capability retrieval |
| output context | often full provider response | declared field projection |
| authority | easy to conflate with model choice | local policy + trusted binding |
| drift | application-specific | fingerprinted schema lifecycle |
| framework | tied to prompting pattern | sits beneath/alongside agent frameworks |

## Integration snippets

### OpenAPI

```python
router = await SchemaRouter.from_url(
    "https://api.apis.guru/v2/openapi.yaml",
    kind="openapi",
)
```

### MCP stdio

See the runnable pair:

```bash
python examples/mcp_stdio_quickstart.py
```

### LangChain

```bash
pip install "schemarouter[langchain]"
python examples/langchain_quickstart.py
```

### LangGraph

```bash
pip install "schemarouter[langgraph]"
python examples/langgraph_quickstart.py
```

### LlamaIndex

```bash
pip install "schemarouter[llamaindex]"
python examples/llamaindex_quickstart.py
```

## Channel playbooks

### Hacker News / Show HN

Use Show HN only because the project is directly runnable and inspectable without a signup gate.

Proposed title:

> **Show HN: SchemaRouter – typed capability retrieval for agents with too many tools**

Suggested first comment:

> I built SchemaRouter after repeatedly running into the same agent problem: once a tool catalog gets
> large, "which schema is relevant?" and "what is actually allowed to execute?" start getting mixed
> together.
>
> SchemaRouter is a Python library that sits underneath an agent/RAG stack. It retrieves a bounded
> typed capability set, keeps field-level contracts, and executes only through registered local
> bindings/policy. It supports MCP, OpenAPI, Python/SDK tools, LangChain/LangGraph, LlamaIndex, and
> several structured protocols.
>
> The repo has no-signup runnable examples, including a 40-tool context-reduction demo and public
> OpenAPI quickstart. I also published the release/SBOM/evidence boundary instead of only showing a
> benchmark headline.
>
> I'm particularly interested in criticism from people operating large tool catalogs: where does
> capability retrieval become useful in your stack, and which integration friction would stop you
> from adopting a separate typed boundary?

Rules for the actual submission:

- link directly to the runnable repository, not a signup or marketing page;
- be present to answer technical questions;
- do not ask anyone to upvote or comment;
- do not coordinate votes through another community;
- do not repost minor release updates as repeated Show HNs.

Official guidance:
<https://news.ycombinator.com/showhn.html>

### Reddit

Do **not** copy the same promotional post across many communities.

Candidate communities should be evaluated on the day of posting for their current rules. Prefer a
community only where the technical problem is directly on-topic.

Reusable technical post:

**Title**

> I built an OSS typed tool-schema boundary for agents — looking for feedback on large tool catalogs

**Body**

> I kept running into a separation problem in agent/RAG systems: tool retrieval decides what is
> relevant, but it should not automatically decide what is authorized to execute.
>
> SchemaRouter is an MIT-licensed Python library that parses/registers structured capabilities,
> retrieves a bounded typed candidate set, validates execution through local contracts, and projects
> declared output fields before results return to the model.
>
> It works beside LangChain/LangGraph/LlamaIndex rather than replacing them, and supports MCP,
> OpenAPI, Python/SDK tools and several other structured protocols.
>
> The smallest deterministic demo builds a 40-tool catalog and compares full-catalog serialization
> with Top-3 typed retrieval:
>
> `python examples/context_reduction_demo.py`
>
> Repo: https://github.com/JDeun/SchemaRouter
>
> I'm looking for technical criticism rather than stars: if you run a large tool catalog, what
> information would a capability router need to preserve before you'd trust it in front of your
> agent?

Before posting:

- check the specific community's self-promotion and link rules;
- disclose that you are the maintainer;
- prefer one substantive community-specific post over repeated exposure;
- no unsolicited DMs;
- no vote requests.

Reddit's sitewide spam guidance explicitly treats repeated/unwanted/unsolicited mass engagement as
spam and notes that individual communities may be stricter.

### LinkedIn

Use the personal engineering story rather than a generic product announcement.

Draft:

> Tool routing looked simple until the tool catalog stopped being small.
>
> In an agent system, "which tool is relevant?" and "which operation is actually allowed to execute?"
> are not the same question.
>
> I built SchemaRouter around that distinction.
>
> It is an open-source Python layer for typed capability retrieval and schema-aware execution across
> MCP, OpenAPI, Python/SDK tools, LangChain/LangGraph, LlamaIndex and other structured sources.
>
> The design is field-first: resolve the data the request needs, retrieve a bounded capability set,
> validate local authority/bindings, execute, validate the raw output, then project only declared
> fields back into agent context.
>
> I also kept the research claims deliberately narrow. A controlled 23-task Qwen3-0.6B experiment
> showed a strong result for the bounded SchemaRouter condition, while another structural K3-vs-K5
> promotion test failed and remains published as a negative result.
>
> Stable release: 0.14.0
> GitHub: https://github.com/JDeun/SchemaRouter
> Verification/evidence: https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/
>
> I'm especially interested in feedback from people building agents with large or heterogeneous tool
> catalogs.

Attach the 30-second terminal demo or one architecture image rather than adding more promotional
claims.

### Technical article

Working title:

> **Why I stopped treating tool retrieval as execution authority**

Outline:

1. When all-tool prompting is still the right answer.
2. What breaks as catalogs become large/heterogeneous.
3. Capability retrieval versus execution authority.
4. Field-first retrieval and result projection.
5. MCP/OpenAPI/Python/framework integration boundaries.
6. Schema drift, bindings, destructive operations, fail-closed behavior.
7. Controlled evidence and the negative result.
8. What still needs independent validation.
9. Runnable examples and installation.

Publish the article only after the repository links/examples it references are stable.

### Discord / Slack / community channels

Only post where project sharing is explicitly permitted. Use a short question-led message and one
link. Never use unsolicited bulk DMs.

Suggested format:

> I maintain SchemaRouter, an OSS typed capability retrieval/execution layer for agent tool catalogs.
> I have a deterministic 40-tool demo and MCP/OpenAPI integrations. Is this the right channel for a
> short technical feedback post? If so, I'll share the runnable example.

### Conference / meetup lightning talk

Title:

> **Tool retrieval is not execution authority**

Five-slide structure:

1. large tool catalog problem;
2. field-first typed retrieval;
3. trusted execution boundary;
4. controlled positive + negative evidence;
5. runnable OSS demo / open questions.

## Campaign sequence

Do not publish everywhere at once.

### Phase 0 — baseline

Already available:

- public adoption scorecard;
- stable 0.14.0 release;
- runnable examples;
- trust/evidence page;
- contributor roadmap and issue templates.

Capture the scorecard artifact immediately before the first public launch post if the current
weekly snapshot is stale.

### Phase 1 — high-signal technical feedback

1. Show HN;
2. respond to technical feedback;
3. convert valid friction into issues/docs fixes;
4. record post URL/date and the next scorecard snapshot.

Do not proceed to broad reposting merely because the post is quiet.

### Phase 2 — owned-network explanation

Publish the LinkedIn technical post and/or technical article after incorporating useful Phase 1
feedback.

### Phase 3 — community-specific posts

Use one or two relevant Reddit/community posts, each rewritten around that community's problem.
Check current rules immediately before posting.

### Phase 4 — evidence follow-up

After a meaningful integration, benchmark reproduction, or external adopter exists, publish a
follow-up based on new evidence rather than repeating the launch announcement.

## Measurement

Record every external publication in
[Launch and outreach log](launch-log.md).

For each entry record:

- UTC/KST date;
- channel;
- canonical post URL;
- exact asset/message variant;
- scorecard snapshot/run before and after;
- stars/forks/download-window changes;
- issue/PR/contributor activity;
- concrete integration/adopter inquiries;
- qualitative feedback that triggered a repository change.

Do not attribute all metric movement to one post without evidence.

## Stop conditions

Pause a channel if:

- moderators/users identify the post as off-topic or promotional;
- the same question is being repeated without new evidence;
- the project cannot respond to incoming issues;
- public copy starts exceeding the evidence boundary;
- traffic rises but first-use failures reveal an onboarding defect.

Fix the repository surface first, then resume.
