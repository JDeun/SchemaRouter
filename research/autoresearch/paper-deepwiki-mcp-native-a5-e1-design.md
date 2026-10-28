# DeepWiki MCP: source-reviewed original P2/A5 native E1

## Problem

The keyless heterogeneous live pilot already executed DeepWiki through the
native MCP invoker, but the original-paper P2 → A5 bridge still used a
synthetic identifier-shaped MCP output. Actual `read_wiki_structure` exposes
only a scalar `result: string`. A reviewed host-source route with that output
currently fails the G5 graph-root build because the G5 root requires an
identifier, even for a **direct** query that performs no join.

## Boundary / design

1. Inspect `https://mcp.deepwiki.com/mcp` using the existing bounded native
   MCP `tools/list`. `probe` returns a deterministic digest of the
   **adapter-visible discovered tool and metadata snapshot**, plus URL,
   existing endpoint names, and result fields; it neither authorizes nor calls
   any source operation. This is not a raw-wire `tools/list` checksum or a
   cryptographic source-owner signature.
2. A *separate host review* pins the exact discovered snapshot fingerprint
   and exact URL, then approves only the existing `read_wiki_structure` endpoint
   when it declares exactly one required scalar `repoName: string` parameter
   and a source-declared required scalar `result: string` output. Untrusted
   `readOnlyHint` never grants permission; the host explicitly reviews the
   operation as read-only, sets `destructive=False`, narrows its input object
   to one required key, and labels its license **unverified / research only**.
   The observed provider annotates `repoName` with a `description` and the
   output envelope with `x-fastmcp-wrap-result: true`: the review accepts
   only these nonvalidation annotations; unknown constraints fail closed.
   Host semantic attestation maps the two *existing* source members to
   `wiki.repository_id` and `wiki.outline`; no identifier field is invented.
3. In G5, an explicitly host-approved read-only source with only nonidentifier
   scalar outputs may be a **direct-only graph root**. It contributes an empty
   `produces` list to the dependency graph, so it cannot fabricate a graph
   edge or satisfy a downstream identifier binding. The field posting index
   already handles matching scalar `wiki.outline` for direct P2.
4. Register the reviewed source into `SchemaRouter` with the original
   `MCPRemoteInvoker`, `replace=False`. Pin runtime source identity: only a
   bounded numbered outline starting `Available pages for <host repo>:` is
   accepted. All model-proposed arguments are discarded in favor of the
   independently host-supplied `repoName`. Execute via the existing original
   Understand → P2 direct plan → A5 ToolCall → native `SchemaRouter.execute`.
5. Validate with a source-shaped async MCP `tools/list` and `call_tool`
   transport fake, and a manual-only public probe/run workflow. Offline E1
   proves wiring and refusals, **not** a live network result or independent E2.

## Critical refusals

- Mismatching source fingerprint or URL; missing/extra/complex source members.
- Changes in adapter-visible MCP annotations or previously approved schema
  descriptions; unrecognized additional validation constraints.
- Untrusted read-only annotation cannot automatically authorize a call.
- Unapproved principal, changed source contract, or nonhost input value.
- Wrong repository heading, missing numbered pages, excessive output bytes.
- Wrong network origin or source invocation without a principal-scoped route.
- Nonidentifier scalar outputs must never create dependency graph edges.

## Out of scope

No autonomous model inference, provider license certification, release gate,
new MCP transport, or independent model E2. Existing mainline and stacked
drafts remain unmerged pending protected review.
