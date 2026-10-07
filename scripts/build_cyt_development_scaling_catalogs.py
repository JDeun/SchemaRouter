"""Generate deterministic visible development scaling catalogs for CYT preflight.

Synthetic distractors are development-only. They are never promoted into held-out evidence.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SIZES=(100,250,500,1000)

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--source",type=Path,required=True); p.add_argument("--out-dir",type=Path,required=True); a=p.parse_args()
    source=json.loads(a.source.read_text(encoding="utf-8"))
    base=list(source["tools"])
    a.out_dir.mkdir(parents=True,exist_ok=True)
    for size in SIZES:
        tools=list(base)
        i=0
        while len(tools)<size:
            tools.append({"name":f"dev_distractor_{i:04d}","description":f"Visible development distractor capability {i:04d}; synthetic and not relevant to benchmark tasks.","input_schema":{"type":"object","properties":{"value":{"type":"string","description":f"Synthetic development value {i:04d}"}}}})
            i+=1
        payload={"schema_version":1,"status":"development_unfrozen","synthetic_distractors":True,"tools":tools[:size]}
        raw=(json.dumps(payload,indent=2,sort_keys=True)+"\n").encode()
        path=a.out_dir/f"catalog-{size}.json"; path.write_bytes(raw)
        print(size,hashlib.sha256(raw).hexdigest(),path)
if __name__=="__main__": main()
