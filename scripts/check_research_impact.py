#!/usr/bin/env python3
"""Collect OpenAlex candidate works; no candidate is automatically a verified citation."""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs/research/impact/citations.json"
OUTPUT = Path(os.environ.get("IMPACT_CANDIDATES_OUTPUT", "research-impact-candidates.json"))
API = "https://api.openalex.org/works"
SEARCHES = ["SchemaRouter Field-Aware Tool Routing", "2608.21375"]
def get(query):
    params = urllib.parse.urlencode({"search": query, "per-page": 30, "select": "id,title,publication_year,doi,primary_location,ids"})
    req = urllib.request.Request(API + "?" + params, headers={"User-Agent": "SchemaRouter-research-impact/1.0 (public scholarly metadata)"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response).get("results", [])
def main():
    existing = json.loads(REGISTER.read_text(encoding="utf-8"))
    seen = {r["work_id"] for r in existing["records"]}
    candidates = {}
    failures = []
    for query in SEARCHES:
        try:
            for item in get(query):
                ident = item.get("doi") or item.get("id")
                if not ident or ident in seen:
                    continue
                candidates[ident] = {"id": ident, "title": item.get("title"), "year": item.get("publication_year"), "doi": item.get("doi"), "openalex": item.get("id"), "status": "candidate", "verification": "Inspect original full text and bibliography; search hit is not evidence of a citation."}
        except (OSError, ValueError, KeyError) as exc:
            failures.append({"query": query, "error": str(exc)})
    result = {"source": "OpenAlex search", "candidate_count": len(candidates), "candidates": sorted(candidates.values(), key=lambda x: x["id"]), "failures": failures, "warning": "Metadata search can include false positives and miss citations. This is NOT a citation count."}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}: {len(candidates)} unverified candidates; {len(failures)} query failures")
    return 1 if failures else 0
if __name__ == "__main__":
    sys.exit(main())
