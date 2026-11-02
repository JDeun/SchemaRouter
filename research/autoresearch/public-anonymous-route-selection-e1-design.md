# B1 E1: unhinted route selection against real anonymous REST/OPTIMADE/MCP

## Intent and decision

The preceding B1 source matrix proves that three independently published,
keyless services can execute in one actual native router. It does **not**
prove that a user query can retrieve the correct provider/endpoint. The
follow-on study must expose that difference using the source-shaped tasks,
not inject their expected tool into the retrieval request.

Approaches considered:

1. Modify the global lexical/semantic scorer immediately. Rejected until a
   real mixed-source regression baseline exists; source-name heuristics may
   harm unrelated catalogs and permit unsupported multilingual inferences.
2. **Chosen:** frozen host-authored natural-language task labels; register the
   exact authentic public REST/OPTIMADE/MCP sources; retrieve and plan through
   the unchanged current native interfaces; report honest measured ranking,
   projections, missing required arguments and source-agnostic refusal
   characteristics. Only an explicitly opted-in command contacts providers.
3. Real agent/LLM inference paired with externally adjudicated semantic
   quality: remains separate #1477/#1346 external E2 work and is not faked
   by choosing the expected tool or an arbitrary API-keyless chat service.

## Real discovery baseline, 2026-10-27

One actual registry of Crossref REST, COD OPTIMADE and DeepWiki Streamable
HTTP MCP was built without secrets. Crossref is registered via the bundled
source-specific provider profile; the COD service schema and DeepWiki MCP
tool listing are discovered remotely in this run. The preceding separate
E1 execution matrix verified actual Crossref REST responses, but this route
selection study does **not** re-probe Crossref availability or live contract
drift. Unhinted `retrieve_executable` with
`PlanRequest(query=...)` observed:

| Fixed user scenario | Host-authored expected route | Actual Top-1 | Expected rank |
|---|---|---|---:|
| Scholarly article DOI/title (EN) | Crossref `get_work` | COD `get_references` | 3 |
| Si/O binary crystal structures (EN) | COD `search_structures` | COD `get_structures` | 2 |
| Repository wiki structure (EN) | DeepWiki `read_wiki_structure` | COD `get_structures` | 5 |

Korean queries sometimes returned positive but irrelevant candidate scores;
other Korean/off-topic queries exposed zero-scored routes in the Top-5.
Those are **actual observed baseline weaknesses**, not proof of a hidden
model failure, and must not be rewritten as correct by oracle-preferring a
route or treating zero score as positive evidence.

The frozen follow-up expands this initial observation to twelve natural
queries: nine labeled source-specific cases (each endpoint in EN/KO/JA) and
three unrelated requests (one per language). Every positive task supplies
its actual DOI, crystal formula, or public repository identifier, without
naming the expected provider in the request. Actual live schema discovery
followed by unchanged native retrieval/planning observed:

| Host-scored metric | Actual result | Boundary |
|---|---:|---|
| Positive-score expected endpoint Top-1 | 0 / 9 | No successful first-ranked route |
| Positive-score expected endpoint Top-5 | 5 / 9 | EN 3/3, KO 1/3, JA 1/3 |
| Raw Top-5 inclusion including zero scores | 7 / 9 | Not equivalent to meaningful retrieval |
| Native plan exact expected endpoint | 0 / 9 | No correctly selected execution plan |
| Native plan with all expected fields on correct endpoint | 0 / 9 | Denominator is all nine labeled cases |
| Zero-scored candidates surfaced | 8 / 12 | Expected endpoint may be visible at score zero |
| Off-topic no positive scores | 3 / 3 | Scorer threshold, not native execution gate |
| Off-topic native plan proposals | 0 / 3 | Separate actual planner observation |

No candidate endpoint was invoked during this selection study. These
numbers are a small **host-labeled E1 regression baseline**, not E2 gold or
evidence that a semantic source selector meets production quality. The
follow-on ranking work must improve the measured baseline without leaking
host labels into `PlanRequest` or inflating zero-score candidates into wins.

## Evaluation contracts

- Frozen host-authored cases: English / Korean / Japanese descriptions of
  each of three source tasks, and negative unrelated user requests. No
  `preferred_tools`, `preferred_endpoints`, model-generated concepts or
  answer text in the retrieval request. The host label is reserved **only
  for evaluation**, never given to the router as a hint.
- For each query, request actual `retrieve_executable(k=5)` from the single
  live registry; record exactly the source-owned route name and score. A
  zero score is **not** an evidenced positive match even if the native
  Top-5 surface includes it. Measure raw top-1 and top-5 target recall,
  separate positive-score top-1 / top-5 hit rates, off-topic abstention and
  per-language outcomes. Do not call a wrong route.
- Use the unchanged `plan_executable(PlanRequest(...))` to observe its actual
  selected endpoint, output fields and missing mandatory arguments. The
  source-specific expected outputs (`message`, Si/O formula/elements/
  `nelements`, MCP `result`) are host labels; absent fields or source-required
  inputs are reported as missing, never invented. Metric definitions and
  denominators appear in the machine-readable report.
- Result serialization includes only pinned case IDs, provider/endpoint
  names, source-described fields, scores and counts. Never log raw external
  wiki text, copyrighted article abstracts, arbitrary source exceptions,
  credentials or implementation-only chain-of-thought.
- Preserve per-provider schema provenance: bundled Crossref source profile
  versus two actually discovered remote contracts (COD OPTIMADE / DeepWiki
  MCP). A three-source registered catalog is **not** three remotely
  discovered schemas.
- Offline tests use real SchemaRouter ToolSpecs/registry (not mocked ranking
  output), source-shaped contracts, explicit negative/adversarial cases, and
  a strict report scorer with denominator checks. Public CI only runs
  offline. Opt-in live discovery reads authentic provider contracts; it does
  not exercise wrong or irrelevant candidates.

## Evidence and release boundary

This is an observed **retrieval/plan E1 characterization**, not an
independent publisher-reviewed natural-language benchmark, model-selected
E2, full 500/5000-route acceptance, production semantic bridge or license
grant. Open-Meteo's existing noncommercial live cases and the 1,009-route
genuine-source E0 corpus remain separately documented. No change to core
ranking, default promotion, endpoint authorization or release flags. Keep
Draft #1755; #1346/#1477 BLOCKED_EXTERNAL; #1356 HARD HOLD.

## Primary source entrypoints

- https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- https://www.optimade.org/specification/latest/
- https://docs.devin.ai/work-with-devin/deepwiki-mcp
- Existing source-verified harness:
  `scripts/research_public_heterogeneous_live_e1.py`
