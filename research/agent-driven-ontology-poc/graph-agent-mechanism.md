# Gate C2 — graph presentation mechanism checkpoint

Protocol and exact pilot source: [68bf0b2](https://github.com/JDeun/SchemaRouter/commit/68bf0b239904215877343f2247d003889c2913f3). The local test files were prepared in the prior interrupted session and verified by Git blob identity. All 9 unittest methods passed (five view checks, four scripted harness checks); no actual model trials. Core and public API-only extract are unchanged. Tests used Python 3.13.5 with existing dependencies and exact API blob da3b3dbda4173fec83d7fee064d01202fa69b04e. Local source code blobs: graph_views.py 9f9a1bd49df19fa3fa1ce345ffecb3996786b875; agent_probe.py 844141335857620458581527eef7ea8f769ad8f7; test_graph_views.py e2d193cc43826d295bdaa51eb26d467f6763573c; test_agent_probe.py 3e049adc91b5d2b29ad188247b3196a149c89286; tasks 5a0397bf8b03105892d405e995d4b66d273e2a7d.

## Measured mechanism results (not model scores)

Actual frozen graph-derived view: 19 routes, 166 fields, 171 concepts, 505 relationship edges. The flat view and inverse graph flattening compare equal by canonical JSON for the full catalog and all 19 individual route neighborhoods. Both use identical original input/output schema and metadata; graph changes annotation relationship representation only. The graph is an agent-visible projection of the RDF relationships, not a test of arbitrary SPARQL reasoning by the model.

| Observation | Flat bytes | Graph bytes |
|---|---:|---:|
| Full catalog | 92,792 | 100,190 |
| Median single-route neighborhood | 4,004 | 4,406 |
| band_gap lookup + all matched-route inspection | 25,742 | 27,543 |
| elastic modulus lookup + all matched-route inspection | 22,384 | 24,082 |
| research paper lookup + all matched-route inspection | 26,025 | 28,011 |

These are actual canonical UTF-8 serialized observation bytes only, **not LLM tokens or cumulative request cost**. Fixed traces include identical literal lookup result + one inspection of all hit routes. No actual agent selected these traces. Full graph representation is 7.97% larger; all 19 route neighborhoods are larger in graph form. Hence no representation compression advantage shown. A dynamic lookup is smaller than dumping the full catalog in these traces, but that is not evidence of a graph-specific advantage or an agent efficiency win. Repeated context, instructions, lookup requests, completion and later calls must be counted in the real pilot.

The unranked shared literal locator returns three band-gap candidates (Materials Project, NOMAD, OQMD); elastic modulus yields four fields across two routes and three candidate concepts, including Young modulus without any matching field. Research paper yields ten field matches across five tools. It does not resolve meanings or choose the final fields. Both dynamic arms share this same locator; this deliberately isolates presentation and is not a full test of graph-native multihop navigation. Explicitly selected fields are projected without automatic group expansion, preserving original input schema. Original C1 results remain valid negative conditional diagnostics, not direct agent results.

Full measured values: [graph-agent-mechanism.json](graph-agent-mechanism.json), exact Git blob 196caf818e7b9516321f5116c183d45226887cd4.

### Reproduction

Run the unit tests in the research directory with the pinned environment. For the byte diagnostic, instantiate Views(*normalize(load_apis())), assert canonical equality of flat vs flatten(graph) for full and every route; measure len(canon(view).encode()) for each. For each of the three fixed terms above, call find(term), take the sorted union of routeIds and fieldHits[].route, then measure locator and view(rep, ids) separately. Sum the two observation byte counts. Actual local run used an exact API-only extract rather than the full fixture checkout.

## Actual inference blocker and next experiment

Local Python lacks transformers/llama_cpp and a configured loopback inference backend. DNS resolution to GitHub/Hugging Face/PyPI failed in the local container. No model weights downloaded, no provider called, no A–D model episodes run. A–D runner and 12 developer-authored DEV questions are checked in. Model revision, context length, backend and settings must be recorded before running. Tests using scripted responses are harness checks only. No task success/recall/token/latency claim. E (original Algorithm 1) requires an additional authorized, pinned original implementation adapter and fair common scoring, as specified in the protocol; not implemented here. No private paper source published. Keep #1900 open; no release or legacy merger. Decision remains INCONCLUSIVE.

Example execution from the research directory on the owner's model host, with an already-running loopback OpenAI-compatible server and its exact model ID:

```sh
python -m pip install -r requirements-local-py313.txt
python -m unittest -v test_graph_views test_agent_probe
python agent_probe.py --base-url http://127.0.0.1:8000/v1 --model YOUR_LOCAL_MODEL --out /tmp/sr-graph-pilot
```

Use a model with enough context for both complete representations. If the context limit is exceeded, retain the failure, do not silently truncate. The result directory contains all request/response receipts and reported token counts. No hosted paid inference. The requested model string does not attest weights. A model-running session is still needed to measure the original hypothesis.
