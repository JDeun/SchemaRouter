"""Detect newly declared public execution methods without a wiring inventory row.

This is a source-level inventory guard, not an E2 execution qualification.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-wiring-v1.json"
PUBLIC_OWNERS = {
    "SchemaRouter": ROOT / "src/schemarouter/runtime.py",
    "SchemaFieldRoutingSession": ROOT / "src/schemarouter/field_routing_session.py",
}
# Known public async entrypoint not yet independently mapped to a real invoker
# test in the execution manifest. Explicit debt is preferable to silent omission.
NOT_TESTED = {
    "schemarouter.SchemaRouter.ainvoke": "#1821: add an async registered invoker E2E mapping",
}


def test_public_execution_methods_are_mapped_or_explicitly_not_tested():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mapped = {row["public_entrypoint"] for row in manifest["paths"]}
    discovered = set()
    for owner, path in PUBLIC_OWNERS.items():
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == owner)
        for method in cls.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name in {"execute", "invoke", "ainvoke", "aexecute_direct"} or (
                not method.name.startswith("_")
                and (method.name.startswith("execute_") or method.name.startswith("invoke_")
                     or method.name.startswith("aexecute_") or method.name.startswith("ainvoke_"))
            ):
                discovered.add(f"schemarouter.{owner}.{method.name}")
    missing = discovered - mapped - NOT_TESTED.keys()
    assert not missing, f"New public execution methods need wiring evidence: {sorted(missing)}"
    assert NOT_TESTED.keys() <= discovered, "Remove stale NOT_TESTED exceptions"
    assert mapped & discovered, "Execution manifest lost all public execution coverage"
