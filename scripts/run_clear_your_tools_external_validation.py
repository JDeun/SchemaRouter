"""Run Clear Your Tools v2 native BM25 pruning on a visible development fixture."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from statistics import median
from typing import Any
from cyt_indexer import build_catalog_from_tools, retrieve_tools, PolicyContext, apply_tool_kind
from cyt_indexer.bm25_search import bm25_score_catalog

def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
def run(package_dir: Path, repeats: int, revision: str) -> dict[str, Any]:
    catalog=load(package_dir/"catalog.json")
    cases=load(package_dir/"cases.json")["cases"]
    tools=[{"name":t["name"],"description":t.get("description",""),"input_schema":t["input_schema"]} for t in catalog["tools"]]
    index=build_catalog_from_tools(tools)
    decomposed=index.to_catalog_dict()
    ctx=PolicyContext("prune_optional","prune_all"); apply_tool_kind(ctx,"mcp")
    rows=[]
    for case in cases:
        durations=[]; survivors=[]
        for _ in range(repeats):
            data=json.loads(json.dumps(decomposed)); start=time.perf_counter()
            scored=bm25_score_catalog(data,case["query"])
            survivors=retrieve_tools(scored,catalog=index,ctx=ctx)
            durations.append((time.perf_counter()-start)*1000)
        rows.append({"id":case["id"],"candidate_tools":[x["name"] for x in survivors],"latency_ms":median(durations),"exposed_contracts":survivors})
    return {"schema_version":1,"status":"development_unfrozen","implementation":{"name":"Clear Your Tools native BM25","revision":revision,"boundary":"cyt-indexer-sdk build_catalog_from_tools + native bm25_score_catalog + retrieve_tools","repeats_per_query":repeats},"results":rows}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--package-dir",type=Path,required=True); p.add_argument("--out",type=Path,required=True); p.add_argument("--repeats",type=int,default=5); p.add_argument("--implementation-revision",required=True); a=p.parse_args()
    payload=run(a.package_dir,a.repeats,a.implementation_revision); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(a.out)
if __name__=="__main__": main()
