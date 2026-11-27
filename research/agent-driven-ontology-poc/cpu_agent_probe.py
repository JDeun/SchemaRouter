"""Isolated, pinned CPU model runner for the frozen four-arm DEV probe."""
import argparse
from hashlib import sha256
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import subprocess
import time

from agent_probe import ARMS, CORE_BLOBS, HERE, episode
from graph_views import Views, flatten
from historical_inventory import FIXTURE, git_blob, load_apis, normalize
from ontology_catalog import canon

MODEL_ID = 'Qwen/Qwen3-0.6B'
MODEL_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
MAX_NEW_TOKENS = 768
THREADS = 4
SEED = 20260929
PILOT_BLOBS = {**CORE_BLOBS, 'agent_probe.py': '844141335857620458581527eef7ea8f769ad8f7',
               'graph_views.py': '9f9a1bd49df19fa3fa1ce345ffecb3996786b875',
               'graph-agent-dev-tasks.json': '5a0397bf8b03105892d405e995d4b66d273e2a7d'}


def file_hash(path):
    with path.open('rb') as f:
        return sha256_stream(f)


def sha256_stream(f):
    h = sha256()
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def tasks_for_shard(tasks, shard):
    if len(tasks) != 12 or len({t['id'] for t in tasks}) != 12 or shard not in (0, 1, 2):
        raise ValueError('expected fixed 12 tasks and shard 0,1,2')
    return [(i, t) for i, t in enumerate(tasks) if i % 3 == shard]


def aggregate_attempts(attempts):
    # Retain consumed usage on malformed/failing final replies, even when the
    # frozen episode contract nulls its successful-episode usage field.
    keys = ('prompt_tokens', 'completion_tokens')
    return {k: sum(a[k] for a in attempts if type(a.get(k)) is int)
            if attempts and all(type(a.get(k)) is int for a in attempts) else None for k in keys}


class CpuModel:
    def __init__(self, snapshot):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.attempts = []
        self.torch = torch
        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        self.tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(snapshot), local_files_only=True, trust_remote_code=False,
            use_safetensors=True, torch_dtype=torch.float32, attn_implementation='sdpa')
        self.model.eval()
        self.context = int(self.model.config.max_position_embeddings)

    def __call__(self, messages):
        start = time.perf_counter_ns()
        record = {'prompt_tokens': None, 'completion_tokens': None, 'generated': False, 'error': None}
        self.attempts.append(record)
        try:
            prompt = self.tokenizer.apply_chat_template(messages, tokenize=False,
                                                        add_generation_prompt=True, enable_thinking=False)
            ids = self.tokenizer(prompt, add_special_tokens=False, return_tensors='pt')['input_ids']
            n = int(ids.shape[-1])
            record['rendered_prompt_tokens'] = n
            if n + MAX_NEW_TOKENS > self.context:
                raise ValueError('context overflow: no truncation')
            with self.torch.inference_mode():
                output = self.model.generate(ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                             use_cache=True, pad_token_id=self.tokenizer.eos_token_id)
            tokens = output[0, n:]
            record.update(prompt_tokens=n, completion_tokens=int(tokens.shape[-1]), generated=True)
            content = self.tokenizer.decode(tokens, skip_special_tokens=True)
            return {'choices': [{'message': {'content': content}}],
                    'usage': {k: record[k] for k in ('prompt_tokens', 'completion_tokens')}}
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            record['wall_ms'] = (time.perf_counter_ns() - start) / 1e6


def snapshot_receipt(snapshot):
    # A Hugging Face cache snapshot directory at the pinned commit, plus
    # actual file digests for the downloaded configuration/tokenizer/weights.
    if snapshot.name != MODEL_REVISION or snapshot.parent.name != 'snapshots':
        raise ValueError('expected exact pinned HF cache snapshot directory')
    files = sorted(p for p in snapshot.iterdir() if p.is_file())
    if not any(p.suffix == '.safetensors' for p in files) or not (snapshot / 'config.json').is_file():
        raise ValueError('missing pinned model weights/config')
    return {p.name: {'sha256': file_hash(p), 'bytes': p.stat().st_size} for p in files}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--shard', type=int, choices=(0, 1, 2), required=True)
    p.add_argument('--fixture', type=Path, default=FIXTURE)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    for name, expected in PILOT_BLOBS.items():
        if git_blob((HERE / name).read_bytes()) != expected:
            raise ValueError('frozen pilot file mismatch: ' + name)
    tasks = json.loads((HERE / 'graph-agent-dev-tasks.json').read_text())
    assigned = tasks_for_shard(tasks, a.shard)
    view = Views(*normalize(load_apis(a.fixture)))
    if canon(flatten(view.view('graph'))) != canon(view.view('flat')):
        raise ValueError('representation parity failed')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    a.out.mkdir(parents=True, exist_ok=False)
    manifest = {'study': 'C2_GRAPH_PRESENTATION_DEV', 'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                'source_blobs': PILOT_BLOBS, 'snapshot_files': snapshot_receipt(a.snapshot),
                'catalog_revision': view.revision, 'platform': platform.platform(),
                'python': platform.python_version(), 'runtime': {k: md.version(k) for k in
                    ('torch', 'transformers', 'huggingface-hub', 'rdflib', 'jsonschema')},
                'device': 'cpu', 'dtype': 'float32', 'attention': 'sdpa', 'threads': THREADS,
                'seed': SEED, 'thinking': False, 'temperature': 0, 'max_new_tokens': MAX_NEW_TOKENS,
                'shard': a.shard, 'tasks': [t['id'] for _, t in assigned], 'arms': list(ARMS),
                'expected_episodes': 16, 'actual_model_generation_calls': 0, 'complete': False}
    write_json(a.out / 'manifest.json', manifest)
    model = CpuModel(a.snapshot)
    manifest['context_limit'] = model.context
    write_json(a.out / 'manifest.json', manifest)
    with (a.out / 'episodes.jsonl').open('w', encoding='utf-8') as f:
        for i, task in assigned:
            for arm in ARMS[i % 4:] + ARMS[:i % 4]:
                model.attempts = []
                row = episode(view, task, arm, model)
                row['attempts'] = model.attempts
                row['observed_usage'] = aggregate_attempts(model.attempts)
                row['real_generation_calls'] = sum(x['generated'] for x in model.attempts)
                manifest['actual_model_generation_calls'] += row['real_generation_calls']
                f.write(canon(row) + '\n')
                f.flush()
                os.fsync(f.fileno())
                write_json(a.out / 'manifest.json', manifest)
                print(task['id'], arm, row['score'], row['error'], flush=True)
    manifest['complete'] = True
    write_json(a.out / 'manifest.json', manifest)
    if not manifest['actual_model_generation_calls']:
        raise RuntimeError('no actual model generation completed')


if __name__ == '__main__':
    main()
