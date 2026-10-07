"""Run CYT v2 native BM25 composite pruning on visible development fixtures."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from statistics import median
from typing import Any
from cyt_indexer import PolicyContext, apply_tool_kind, build_catalog_from_tools, prune_catalog_bm25_and_retrieve

CYT_OPTIONS={"score_tool":0.4,"score_tool_enum":0.1,"prune_enums":True,"pipeline":["bm25"]}

def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))

def run(catalog_path: Path, cases_path: Path, repeats: int, revision: str) -> dict[str, Any]:
    catalog=load(catalog_path); cases=load(cases_path)["cases"]
    tools=[{"name":t["name"],"description":t.get("description",""),"input_schema":t["input_schema"]} for t in catalog["tools"]]
    index=build_catalog_from_tools(tools)
    catalog_data=index.to_catalog_dict()
    build_catalog=catalog_data
    scoring=apply_tool_kind(PolicyContext("prune_optional","prune_all"),"mcp")
    output=apply_tool_kind(PolicyContext("prune_optional","prune_all"),"mcp")
    rows=[]
    for case in cases:
        times=[]; result={}
        for _ in range(repeats):
            start=time.perf_counter()
            result=prune_catalog_bm25_and_retrieve(catalog_data,build_catalog,index,case["query"],scoring,output,options=CYT_OPTIONS)
            times.append((time.perf_counter()-start)*1000)
        survivors=result.get("tools",[])
        rows.append({"id":case["id"],"candidate_tools":[x["name"] for x in survivors],"candidate_count":len(survivors),"latency_ms":median(times),"optional_chunk_count_in":result.get("optional_chunk_count_in"),"optional_chunk_count_out":result.get("optional_chunk_count_out")})
    return {"schema_version":1,"status":"development_unfrozen","performance_evidence":False,"catalog_size":len(tools),"implementation":{"name":"Clear Your Tools native composite BM25","revision":revision,"boundary":"cyt-indexer-sdk prune_catalog_bm25_and_retrieve","options":CYT_OPTIONS,"repeats_per_query":repeats},"results":rows}

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--catalog",type=Path,required=True); p.add_argument("--cases",type=Path,required=True); p.add_argument("--out",type=Path,required=True); p.add_argument("--repeats",type=int,default=5); p.add_argument("--implementation-revision",required=True); a=p.parse_args()
    payload=run(a.catalog,a.cases,a.repeats,a.implementation_revision); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(a.out)
if __name__=="__main__": main()
