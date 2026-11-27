"""Research-only E comparator: pinned original router, same CPU agent refinement.
Original private checkout is an explicit local input, never copied to this repo.
"""
import argparse
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

from agent_probe import ARMS, HERE, episode
from cpu_agent_probe import (CpuModel, PILOT_BLOBS, MODEL_ID, MODEL_REVISION,
                             MAX_NEW_TOKENS, THREADS, SEED, aggregate_attempts,
                             snapshot_receipt, tasks_for_shard, write_json)
from graph_views import Views
from historical_inventory import APIS_BLOB, FIXTURE, api_bytes, git_blob, load_apis, normalize
from ontology_catalog import canon

PAPER_REV = '368116746170d6dd0d95a91352daba8abc42ca13'
CPU_BLOB = '2074eb52e4bc568db7e0ce30b6497279871b730b'
PAPER_BLOBS = {
    'experiments/routers/schema_router.py': '09d84dba0f7354ce2e46016b74ff12c3ee0fba5c',
    'experiments/common/llm.py': 'bd896eab27e7ab7a5396d3446e92f342c728175b',
    'experiments/common/plan_schema.py': '90cd0cb465173d21083f1c2e8019b89e2ed71ab6',
    'experiments/routers/base.py': 'd7a213aa5e6f9eae93366682e89c1dd66b701d02',
    'experiments/schema/inventory.json': '71713203dd7145898201868bf1c2435229cdb709',
}


def verify_paper(root):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    if git('rev-parse', 'HEAD') != PAPER_REV or git('status', '--porcelain'):
        raise ValueError('original paper checkout must be exact, clean revision')
    for name, expected in PAPER_BLOBS.items():
        if git_blob((root / name).read_bytes()) != expected:
            raise ValueError('original paper file mismatch: ' + name)
    inventory = json.loads((root / 'experiments/schema/inventory.json').read_text())
    if git_blob(api_bytes(inventory['apis'])) != APIS_BLOB:
        raise ValueError('original and public API inventory differ')


def original_router(root, model):
    verify_paper(root)
    if any(k == 'experiments' or k.startswith('experiments.') for k in sys.modules):
        raise ValueError('original modules must be loaded in a fresh process')
    sys.path.insert(0, str(root))
    llm = importlib.import_module('experiments.common.llm')
    if Path(llm.__file__).resolve() != root / 'experiments/common/llm.py':
        raise ValueError('unexpected original model module')

    def deny(*args, **kwargs):
        raise RuntimeError('original remote client disabled for this probe')

    def local_chat(system, user, **kwargs):
        if kwargs.get('temperature', 0.0) != 0.0:
            raise ValueError('nonzero temperature forbidden')
        response = model([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}])
        return response['choices'][0]['message']['content']

    # Leave original chat_json parser and algorithm intact; replace transport.
    llm._client = llm._tei_key = llm._api_key = llm.embed = deny
    llm.chat = local_chat
    module = importlib.import_module('experiments.routers.schema_router')
    if Path(module.__file__).resolve() != root / 'experiments/routers/schema_router.py':
        raise ValueError('unexpected original router module')
    return module.SchemaRouter()


class SelectedView:
    """Only fields that the original native plan offered, same stable IDs."""
    def __init__(self, full, plan):
        tools = {r['tool']: rid for rid, r in full.routes.items()}
        by_name = {(full.routes[rid]['tool'], tuple(f['path'])): fid for fid, (rid, f) in full.fields.items()}
        selected = {}
        for call in plan['selected_tools']:
            tool = call['tool']
            if tool not in tools or call['endpoint'] != tool + '.search':
                raise ValueError('original plan references unknown tool or endpoint')
            for name in call['fields']:
                key = (tool, (name,))
                if key not in by_name:
                    raise ValueError('original plan references unknown field')
                selected.setdefault(tools[tool], set()).add(by_name[key])
        self.routes = {}
        self.fields = {}
        concept_ids = set()
        for rid, ids in sorted(selected.items()):
            route = deepcopy(full.routes[rid])
            projection = full.selected_schema(rid, sorted(ids))
            route['outputSchema'] = projection['projectedOutputSchema']
            route['fields'] = {}
            for fid in sorted(ids):
                owner, annotation = full.fields[fid]
                self.fields[fid] = (owner, deepcopy(annotation))
                route['fields'][fid] = deepcopy(annotation)
                concept_ids.update(annotation.get('concepts', []))
            self.routes[rid] = route
        self.concepts = {c: deepcopy(full.concepts[c]) for c in sorted(concept_ids)}

    def view(self, representation):
        if representation != 'flat':
            raise ValueError('E refinement is a flat selected-schema menu')
        return deepcopy({'concepts': self.concepts, 'routes': self.routes})


def native_metrics(selected, task):
    offered = {(selected.routes[rid]['tool'], tuple(f['path'])) for rid, f in selected.fields.values()}
    expected = [{frozenset((a['tool'], tuple(p)) for p in a['paths']) for a in need} for need in task['needs']]
    allowed = set().union(*(set().union(*need) for need in expected))
    return {'needsHit': sum(any(a <= offered for a in need) for need in expected),
            'needsTotal': len(expected), 'offeredFields': len(offered),
            'fieldsOutsideAcceptableAlternatives': len(offered - allowed),
            'nativeEmpty': not offered}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paper-root', type=Path, required=True)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--shard', type=int, choices=(0, 1, 2), required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    for name, expected in {**PILOT_BLOBS, 'cpu_agent_probe.py': CPU_BLOB}.items():
        if git_blob((HERE / name).read_bytes()) != expected:
            raise ValueError('frozen pilot mismatch: ' + name)
    root = a.paper_root.resolve()
    verify_paper(root)
    view = Views(*normalize(load_apis(FIXTURE)))
    tasks = json.loads((HERE / 'graph-agent-dev-tasks.json').read_text())
    assigned = tasks_for_shard(tasks, a.shard)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    a.out.mkdir(parents=True, exist_ok=False)
    manifest = {'study': 'C2_E_ORIGINAL_PLAN_AND_REFINEMENT_DEV', 'paper_revision': PAPER_REV,
                'paper_blobs': PAPER_BLOBS, 'snapshot_files': snapshot_receipt(a.snapshot),
                'source_blobs': {**PILOT_BLOBS, 'cpu_agent_probe.py': CPU_BLOB},
                'model_id': MODEL_ID, 'model_revision': MODEL_REVISION, 'threads': THREADS,
                'seed': SEED, 'dtype': 'float32', 'attention': 'sdpa', 'thinking': False,
                'temperature': 0, 'max_new_tokens': MAX_NEW_TOKENS,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                'shard': a.shard, 'tasks': [t['id'] for _, t in assigned],
                'complete': False, 'native_plan_status_not_classification': True}
    write_json(a.out / 'manifest.json', manifest)
    model = CpuModel(a.snapshot)
    router = original_router(root, model)
    with (a.out / 'episodes.jsonl').open('w', encoding='utf-8') as f:
        for _, task in assigned:
            model.attempts = []
            row = {'task': task['id'], 'arm': 'E-original-plus-agent', 'nativePlan': None, 'error': None,
                   'nativeMetrics': None, 'refinement': None}
            try:
                plan = router.route({'query_id': task['id'], 'query': task['question']})
                row['nativePlan'] = plan
                row['routingAttempts'] = list(model.attempts)
                if (not any(x['generated'] for x in model.attempts) or
                        any(str(e).startswith('understand_error') for e in plan.get('errors', []))):
                    raise RuntimeError('original Understand failed; do not score as unavailable')
                selected = SelectedView(view, plan)
                row['nativeMetrics'] = native_metrics(selected, task)
                # One common static selection prompt over only plan-selected schemas.
                model.attempts = []
                row['refinement'] = episode(selected, task, ARMS[0], model)
                row['refinementAttempts'] = list(model.attempts)
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                row['failureAttempts'] = list(model.attempts)
            row['observedUsage'] = aggregate_attempts(row.get('routingAttempts', []) + row.get('refinementAttempts', []))
            row['real_generation_calls'] = sum(x['generated'] for x in row.get('routingAttempts', []) + row.get('refinementAttempts', []))
            f.write(canon(row) + '\n')
            f.flush()
            os.fsync(f.fileno())
    manifest['complete'] = True
    write_json(a.out / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
