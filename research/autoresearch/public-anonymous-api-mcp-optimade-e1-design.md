# B1 E1 — actual keyless API, OPTIMADE and public remote MCP task matrix

## Purpose

Complement the original-source 1,009-operation E0 index experiment with
**observed external provider behavior**, on a real mixed-protocol catalog,
using public read-only endpoints that do not require API keys. Derive each
task's acceptance condition from that provider's own data, not from an
invented uniform benchmark metric or a simple count of paths.

## Existing assets and design choices

- The repository already implements public live Crossref metadata,
  COD OPTIMADE structure search, Open-Meteo geocoding→forecast and local
  Streamable HTTP MCP reference server. Reuse the existing SchemaRouter
  source loaders, execution/validation and those proven boundary patterns.
- **Chosen:** register Crossref REST, public COD OPTIMADE, and the public
  DeepWiki Streamable HTTP MCP simultaneously in **one SchemaRouter**;
  run three source-specific fixed, read-only tasks, and independently
  cross-check the Crossref DOI through anonymous Europe PMC REST.
- **Observed 2026-10-27:** one real 3-tool mixed registry, three bound native
  endpoint executions, one independent Europe PMC HTTP read; all three
  source-specific scenarios passed on **four independent actual network
  runs** (4.32, 5.14, 5.00, 4.94 seconds); this is an anecdotal wall-time record,
  not a latency/SLA distribution. Live registration/discovery adds other
  network reads, so four is a **task-invocation** count, not a total wire
  request count. Source result contents are not logged.
- **Rejected:** create fake provider schemas, infer a shared semantic
  ontology from unrelated metadata, or fetch any arbitrary model-supplied
  URL. This task is host-selected and host-parameterized; no LLM choice
  accuracy is implied.
- **Rejected:** gate every PR on free public services. Keep CI deterministic,
  with an explicitly opted-in live run and a source-shaped offline unit
  test suite. Public services have availability and rate limits.

## Provider-specific fixed tasks

1. **Crossref + Europe PMC (REST):** read one publicly cataloged fixed
   scholarly DOI from Crossref using the existing provider profile and
   validated read-only `get_work`, then use its **source-confirmed DOI**
   as the bounded input to the Europe PMC public search API; accept only
   if a published Europe PMC result includes the same normalized DOI.
   Both services must be genuinely contacted (no recorded response can
   count as live success). Europe PMC is an independent cross-check, not
   a SchemaRouter-owned original native source contract in this slice.
2. **COD OPTIMADE:** discover the provider's original `/info`/entry
   contracts and search a bounded Si/O two-element crystal structure with
   `filter='elements HAS ALL "Si","O" AND nelements=2'`, `page_limit=1`.
   Require a real nonempty structure identity, `nelements == 2`, and
   an original formula field; do not pretend the provider is returning
   a guaranteed fixed material ID.
3. **DeepWiki public MCP:** perform the actual unauthenticated
   Streamable HTTP discovery against `https://mcp.deepwiki.com/mcp` and
   invoke **only** the source-described read-only `read_wiki_structure`
   for `modelcontextprotocol/servers` with validated required input.
   Refuse any unrelated tool, missing safe read contract, remote auth
   challenge, malformed MCP result or unbounded response.
   The actual remote FastMCP source advertises a `result: string` field;
   request it explicitly. Source annotations do not assert read-only, so
   trust is limited to the **host-pinned documented tool name**, never all
   discovered methods of the public MCP server. Require a literal
   `Available pages for modelcontextprotocol/servers:` heading and at least
   two numbered source pages; generic long error text fails the task.

Independent read-only code review identified three E1 safety gaps and the
implementation addresses them with failing-then-green tests:

- Europe PMC reads through `httpx.AsyncClient.stream()` and stops pulling
  bytes once the 256 KiB bound is exceeded, including chunked responses.
- The research-only SDK MCP client uses a pinned-origin `httpx2.AsyncClient`
  whose HTTP response stream is capped at 512 KiB **before SDK parsing**;
  SSE events obey that same cap. It requests `Accept-Encoding: identity`
  and **rejects non-identity `Content-Encoding`** before `httpx2` could
  decompress a tiny gzip body into an unbounded larger buffer. A regression
  reproduces that bypass and confirms rejection. `terminate_on_close=False` prevents the
  default session-cleanup HTTP DELETE request. This does not impose a
  global memory limit on the process or change the production MCP adapter.
- One-shot CLI suppresses upstream SDK logs containing possible untrusted
  data and exits nonzero with only a sanitized error class on failure;
  public CI writes no raw source exceptions to its log artifacts.

Observed safe failure before the successful run: COD returned the requested
original chemical fields, but the first explicit projection omitted its
`id`; structural identity validation correctly failed. Adding the native
source-declared `id` output field allowed the same actual structure result to
pass. An HTTP 200 or discovery success alone is not a successful scenario.

Existing separate Open-Meteo EN/KO/JA two-hop tests remain valid and
may be recorded as a fourth independent task family, not silently
presented as execution within the three-source mixed registry.

## Safety and evidence tier

- No API keys, OAuth, side effects, arbitrary outbound hosts, request
  redirects, generated shell commands, or unapproved tool calls. All
  provider URLs, DOI, repository, OPTIMADE filter and limits are host
  pinned. Public service terms and source attribution apply. Crossref
  public tier is 5 calls/s with one concurrent request; our smoke uses
  one bounded request. Open-Meteo free usage is noncommercial, so it is
  deliberately **not** represented as an unrestricted commercial grant.
- Output only provider IDs, selected tool names, booleans, structured
  reason codes and latency/size counters. No whole MCP wiki, paper
  abstracts or raw untrusted responses are stored in CI artifacts.
- A live PASS means real read-only protocol interoperability and
  source-shaped validation for one fixed host-selected task; it does
  **not** mean independent publisher-reviewed semantic gold, model-
  selected tools, independent EN/KO/JA answer-quality E2, or a stable
  production SLA. Each failed source remains a failed/incomplete task;
  never replace it with a synthetic success receipt.
- #1346/#1477 stay BLOCKED_EXTERNAL, #1356 HARD HOLD, #1755 Draft.

## Primary source references

- https://docs.devin.ai/work-with-devin/deepwiki-mcp
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- https://europepmc.org/RestfulWebService
- https://www.optimade.org/specification/latest/
- https://www.crystallography.net/cod/optimade
