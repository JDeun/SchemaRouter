"""Bounded external-model selection DEV probe (no data tools or gold in prompt)."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPHandler, HTTPRedirectHandler, ProxyHandler

from graph_views import Views, flatten
from historical_inventory import FIXTURE, load_apis, normalize, git_blob
from ontology_catalog import canon

ARMS = ('A-flat-full', 'B-graph-full', 'C-flat-browse', 'D-graph-browse')
HERE = Path(__file__).resolve().parent
CORE_BLOBS = {'ontology_catalog.py': 'f6f99bd17d23f25b62522c7bf6692db2640843f4',
              'historical_inventory.py': '7a771611e8737020514589fc042fb89ec16f2b97'}


def selection_prompt(arm):
    dynamic = arm.endswith('browse')
    graph = '-graph-' in arm
    return ('You are choosing tool schema fields for the user, not fetching data or answering the factual question. '
            'Use only available schema information. Never invent IDs. Choose the minimal sufficient fields; '
            'alternatives are allowed but not necessary. Preserve distinctions in meanings, methods and sources. '
            'If the requested capability does not exist, mark unavailable; if the question needs a choice of physical meaning, clarify. '
            'Reply with one JSON object only: {"action":"final","status":"select|unavailable|clarify",'
            '"selections":[{"route":"r0","fields":["r0.f0"]}]}. '
            'For unavailable or clarify, selections must be empty. '
            + ('Graph routes and fields are nodes; edges returns, means and memberOf denote ownership, concepts and groups. '
               if graph else 'Flat routes nest fields; field annotations contain concepts and groups. ')
            + ('You may request {"action":"find","query":"literal phrase"} to see all matching candidates, '
               'or {"action":"inspect","routes":["r0"]} for their schema. Maximum 4 lookup actions. '
               'Find searches literal phrases, not an answer or ranking. Inspect only IDs you have seen. '
               if dynamic else 'The entire permitted schema catalog follows. No lookup actions in this arm.'))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LocalModel:
    def __init__(self, url, model):
        u = urlsplit(url)
        if (u.scheme != 'http' or u.hostname not in ('127.0.0.1', 'localhost', '::1')
                or u.username or u.password or u.query or u.fragment or u.path.rstrip('/') != '/v1'):
            raise ValueError('use a local loopback HTTP /v1 endpoint; no remote endpoints or credentials')
        self.url = url.rstrip('/') + '/chat/completions'
        self.model = model
        self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPHandler())

    def __call__(self, messages):
        payload = {'model': self.model, 'messages': messages, 'temperature': 0, 'max_tokens': 768,
                   'stream': False}
        req = Request(self.url, data=canon(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with self.opener.open(req, timeout=180) as res:
            return json.loads(res.read())


def score(view, task, final):
    """Deterministic selection-only rubric. No invocation or answer scoring."""
    invalid = False
    selected = set()
    if not isinstance(final, dict) or set(final) != {'action', 'status', 'selections'} or final.get('action') != 'final':
        return {'success': False, 'invalid': True, 'needsHit': 0, 'needsTotal': len(task['needs'])}
    status = final['status']
    if status not in ('select', 'unavailable', 'clarify') or not isinstance(final['selections'], list):
        invalid = True
    else:
        for item in final['selections']:
            if not isinstance(item, dict) or set(item) != {'route', 'fields'} or not isinstance(item['fields'], list) or not item['fields']:
                invalid = True
                continue
            rid = item['route']
            if not isinstance(rid, str) or rid not in view.routes:
                invalid = True
                continue
            for fid in item['fields']:
                if not isinstance(fid, str) or fid not in view.fields or view.fields[fid][0] != rid:
                    invalid = True
                else:
                    selected.add((view.routes[rid]['tool'], tuple(view.fields[fid][1]['path'])))
    allowed = set()
    hits = 0
    for need in task['needs']:
        alternatives = [{(a['tool'], tuple(p)) for p in a['paths']} for a in need]
        allowed |= set().union(*alternatives)
        hits += any(alt <= selected for alt in alternatives)
    extra = len(selected - allowed)
    ok = (not invalid and status == task['status'] and hits == len(task['needs'])
          and not extra and (status == 'select' or not final['selections']))
    return {'success': ok, 'invalid': invalid, 'needsHit': hits, 'needsTotal': len(task['needs']),
            'extraFields': extra, 'selectedFields': len(selected), 'status': status}


def episode(view, task, arm, model):
    dynamic = arm.endswith('browse')
    rep = 'graph' if '-graph-' in arm else 'flat'
    sys = selection_prompt(arm)
    if not dynamic:
        sys += '\nCATALOG:\n' + canon(view.view(rep))
    messages = [{'role': 'system', 'content': sys}, {'role': 'user', 'content': task['question']}]
    events = []
    seen = set() if dynamic else set(view.routes)
    inspected = set() if dynamic else set(view.routes)
    final = None
    error = None
    start = time.perf_counter_ns()
    for step in range(5 if dynamic else 1):
        request = json.loads(canon(messages))
        try:
            response = model(request)
            events.append({'request': request, 'response': response})
            content = response['choices'][0]['message']['content']
            action = json.loads(content)
            if action.get('action') == 'final':
                final = action
                # In dynamic arms, do not permit guessed unseen route/field IDs.
                if dynamic and isinstance(action.get('selections'), list):
                    for s in action['selections']:
                        if not isinstance(s, dict) or s.get('route') not in inspected:
                            raise ValueError('final route not inspected')
                break
            if not dynamic or step == 4:
                raise ValueError('lookup budget exhausted or forbidden')
            if action.get('action') == 'find' and set(action) == {'action', 'query'}:
                result = view.find(action['query'])
                seen.update(result['routeIds'])
                seen.update(x['route'] for x in result['fieldHits'])
            elif action.get('action') == 'inspect' and set(action) == {'action', 'routes'}:
                ids = action['routes']
                if not isinstance(ids, list) or not ids or any(r not in seen for r in ids):
                    raise ValueError('inspect unseen route')
                result = view.view(rep, ids)
                inspected.update(ids)
            else:
                raise ValueError('invalid action')
            messages += [{'role': 'assistant', 'content': content},
                         {'role': 'user', 'content': 'Catalog observation: ' + canon(result)}]
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            final = None
            break
    if final is None and error is None:
        error = 'no final selection'
    totals = {'prompt_tokens': 0, 'completion_tokens': 0}
    for event in events:
        usage = event['response'].get('usage') or {}
        for key in totals:
            value = usage.get(key)
            totals[key] = (totals[key] + value if totals[key] is not None and type(value) is int and value >= 0 else None)
    if not events or error:
        totals = {k: None for k in totals}
    return {'task': task['id'], 'arm': arm, 'score': score(view, task, final), 'error': error,
            'usage': totals, 'wall_ms': (time.perf_counter_ns() - start) / 1e6,
            'events': events, 'final': final}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', type=Path, default=FIXTURE)
    p.add_argument('--api-extract', type=Path)
    p.add_argument('--base-url', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    for name, sha in CORE_BLOBS.items():
        if git_blob((HERE / name).read_bytes()) != sha:
            raise ValueError('frozen core mismatch')
    v = Views(*normalize(load_apis(a.api_extract or a.fixture, extracted=bool(a.api_extract))))
    if canon(flatten(v.view('graph'))) != canon(v.view('flat')):
        raise ValueError('representation parity failed')
    tasks = json.loads((HERE / 'graph-agent-dev-tasks.json').read_text())
    model = LocalModel(a.base_url, a.model)
    a.out.mkdir(parents=True, exist_ok=False)
    with (a.out / 'episodes.jsonl').open('w', encoding='utf-8') as f:
        for i, task in enumerate(tasks):
            # Cyclic order balances arm position without outcome-based tuning.
            for arm in ARMS[i % 4:] + ARMS[:i % 4]:
                row = episode(v, task, arm, model)
                f.write(canon(row) + '\n')
                f.flush()
    print('DEV selection episodes saved; no task-answer or independent performance claim')


if __name__ == '__main__':
    main()
