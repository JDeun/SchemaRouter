"""Gate C1: conditional exposed DEV schema retrieval, no agent/provider."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata as md
import json
import math
from pathlib import Path
import platform
import re
import statistics as st
import time

from historical_inventory import FIXTURE, FIXTURE_BLOB, git_blob, load_apis, normalize
from ontology_catalog import Catalog, canon, route_key

CASE_BLOB = '5b3f89358fe2bdaee8011bbb62786039e0ae19c1'
CODE_BLOBS = {'ontology_catalog.py': 'f6f99bd17d23f25b62522c7bf6692db2640843f4',
              'historical_inventory.py': '7a771611e8737020514589fc042fb89ec16f2b97'}
ARMS = [('FULL', None), ('BM25-5', 5), ('RDF-5', 5),
        ('BM25-all', None), ('RDF-all', None)]


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def load_inputs(fixture, api_extract=None, case_extract=None):
    if bool(api_extract) != bool(case_extract):
        raise ValueError('both extracts required')
    if api_extract:
        apis = load_apis(api_extract, extracted=True)
        raw = case_extract.read_bytes()
    else:
        apis = load_apis(fixture)
        raw = compact([{'id': c['query_id'], 'category': c['category'],
                        'terms': list(dict.fromkeys(c['concepts'])),
                        'reference': [{'tool': a['tool'], 'fields': a['fields']}
                                      for a in c['archived_calls']]}
                       for c in json.loads(fixture.read_bytes())['cases']])
    if git_blob(raw) != CASE_BLOB:
        raise ValueError('case extract hash mismatch')
    cases = json.loads(raw)
    if len(cases) != 110 or len({c['id'] for c in cases}) != 110:
        raise ValueError('case cardinality')
    return apis, cases


def words(text):
    return re.findall(r'[^\W_]+', text.casefold())


def full_view(route):
    return {'route': list(route_key(route)), 'sourceRevision': route['sourceRevision'],
            'inputSchema': route['inputSchema'], 'outputSchema': route['outputSchema'],
            'fields': route['fields'], 'projectionKind': 'full_schema'}


class BM25:
    def __init__(self, concepts, routes):
        self.routes = sorted(routes, key=route_key)
        self.docs = []
        for route in self.routes:
            ids = {c for f in route['fields'] for c in f.get('concepts', [])}
            aliases = [a for c in sorted(ids) for a in concepts[c]]
            self.docs.append(Counter(words(canon(route) + ' ' + ' '.join(aliases))))
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = st.mean(self.lengths)
        df = Counter(t for d in self.docs for t in d)
        self.idf = {t: math.log(1 + (len(self.docs) - n + .5) / (n + .5))
                    for t, n in df.items()}

    def discover(self, terms, budget):
        query = set(words(' '.join(terms)))
        scores = []
        for i, doc in enumerate(self.docs):
            k = 1.2 * (.25 + .75 * self.lengths[i] / self.avg)
            score = sum(self.idf[t] * doc[t] * 2.2 / (doc[t] + k)
                        for t in sorted(query) if t in doc)
            if score > 0:
                scores.append((-score, route_key(self.routes[i]), i))
        selected = sorted(scores)[:budget]
        return {'views': [full_view(self.routes[i]) for _, _, i in selected],
                'omittedRoutes': len(scores) - len(selected)}


def exposed(result):
    pairs = set()
    tools = set()
    schema_bytes = 0
    for v in result['views']:
        tool = v['route'][1]
        out = v['projectedOutputSchema'] if 'projectedOutputSchema' in v else v['outputSchema']
        tools.add(tool)
        pairs.update((tool, f) for f in out['properties'])
        schema_bytes += len(canon(v['inputSchema']).encode()) + len(canon(out).encode())
    return tools, pairs, schema_bytes


def elapsed(call):
    start = time.perf_counter_ns()
    result = call()
    return result, (time.perf_counter_ns() - start) / 1e6


def benchmark(apis, cases):
    concepts, routes = normalize(apis)
    rdf, build_rdf_ms = elapsed(lambda: Catalog(concepts, routes))
    bm, build_bm_ms = elapsed(lambda: BM25(concepts, routes))
    full = {'views': [full_view(r) for r in sorted(routes, key=route_key)]}
    all_tools, all_pairs, _ = exposed(full)
    rows = []
    for case in cases:
        terms = case['terms']
        # Retrieval receives only the frozen concept strings, never references.
        for arm, budget in ARMS:
            payload = b'' if arm == 'FULL' else canon(
                {'terms': terms, 'max_routes': budget}).encode()
            def invoke():
                if arm == 'FULL':
                    result = full
                elif arm.startswith('BM25'):
                    result = bm.discover(terms, budget)
                else:
                    result = rdf.discover(terms, max_routes=budget)
                return result, canon(result).encode()
            timings = []
            prior = None
            for _ in range(3):
                (result, wire), ms = elapsed(invoke)
                timings.append(ms)
                if prior is not None and prior != wire:
                    raise RuntimeError('nondeterministic output')
                prior = wire
            got_tools, got_pairs, schema_bytes = exposed(result)
            if not got_tools <= all_tools or not got_pairs <= all_pairs:
                raise RuntimeError('noncatalog exposure')
            refs = {a['tool'] for a in case['reference']}
            ref_pairs = {(a['tool'], f) for a in case['reference'] for f in a['fields']}
            rows.append({'id': case['id'], 'category': case['category'], 'arm': arm,
                         'nterms': len(terms), 'ref_tools': len(refs), 'ref_fields': len(ref_pairs),
                         'hit_tools': len(refs & got_tools), 'hit_fields': len(ref_pairs & got_pairs),
                         'missing_from_full': sorted(ref_pairs - all_pairs),
                         'complete': bool(refs) and refs <= got_tools and ref_pairs <= got_pairs,
                         'tools': sorted(got_tools), 'fields': sorted(got_pairs),
                         'response_bytes': len(wire), 'request_bytes': len(payload),
                         'schema_bytes': schema_bytes, 'wall_ms': st.median(timings),
                         'coverage': result.get('coverage'),
                         'response_sha256': hashlib.sha256(wire).hexdigest()})
    return rows, {'rdf_build_ms': build_rdf_ms, 'bm25_build_ms': build_bm_ms,
                  'revision': rdf.revision, 'triples': len(rdf._graph),
                  'routes': len(routes), 'fields': len(all_pairs)}


def summarize(rows):
    out = {}
    for arm, _ in ARMS:
        a = [r for r in rows if r['arm'] == arm]
        p = [r for r in a if r['ref_tools']]
        n = [r for r in a if not r['ref_tools']]
        def score(hit, total):
            valid = [r for r in p if r[total]]
            return {'micro': sum(r[hit] for r in valid) / sum(r[total] for r in valid),
                    'macro': st.mean(r[hit] / r[total] for r in valid)}
        out[arm] = {'positive': len(p), 'negative': len(n),
                    'tool_recall': score('hit_tools', 'ref_tools'),
                    'field_recall': score('hit_fields', 'ref_fields'),
                    'complete': sum(r['complete'] for r in p),
                    'empty_positive': sum(not r['tools'] for r in p),
                    'nonempty_negative': sum(bool(r['tools']) for r in n),
                    'mean_tools': st.mean(len(r['tools']) for r in p),
                    'mean_fields': st.mean(len(r['fields']) for r in p),
                    'mean_context_bytes': st.mean(r['request_bytes'] + r['response_bytes'] for r in p),
                    'mean_schema_bytes': st.mean(r['schema_bytes'] for r in p),
                    'p50_ms': st.median(r['wall_ms'] for r in p),
                    'p95_ms': sorted(r['wall_ms'] for r in p)[math.ceil(.95 * len(p)) - 1],
                    'missing_from_full_cases': sum(bool(r['missing_from_full']) for r in p)}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--api-extract', type=Path)
    parser.add_argument('--case-extract', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for path, expected in CODE_BLOBS.items():
        if git_blob(Path(__file__).with_name(path).read_bytes()) != expected:
            raise ValueError('frozen code blob mismatch: ' + path)
    apis, cases = load_inputs(args.fixture, args.api_extract, args.case_extract)
    rows, setup = benchmark(apis, cases)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'rows.jsonl').write_text(''.join(canon(r) + '\n' for r in rows), encoding='utf-8')
    summary = {'kind': 'conditional_schema_exposure_DEV', 'fixture_blob': FIXTURE_BLOB,
               'case_blob': CASE_BLOB, 'code_blobs': CODE_BLOBS,
               'python': platform.python_version(), 'platform': platform.platform(),
               'deps': {k: md.version(k) for k in ('rdflib', 'jsonschema', 'pyparsing')},
               'setup': setup, 'arms': summarize(rows)}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
