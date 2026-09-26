import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_decision_routing_v13.py"
RESULT = ROOT / "benchmarks" / "operation-fit-0.10-v13-result.json"
PROTOCOL = ROOT / "benchmarks" / "decision-routing-v13-blind-protocol.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_decision_routing_v13", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v13 generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_consumed_v13_is_exactly_reproducible_and_not_tuning_eligible() -> None:
    generator = _load_generator()
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    seed = protocol["consumed"]["runtime_seed"]
    cases = generator._build(seed)
    generator._validate(cases)
    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    assert len(cases) == 600
    assert digest == "73863c15191d6e75d892a8b0024056abe562aad2ad11d334610871dc5e070596"
    assert digest == result["evaluation"]["corpus_sha256"]
    assert protocol["status"] == "consumed_after_blind_final_scoring"
    assert protocol["tuning_eligible"] is False
    assert result["status"] == "consumed_blind_final_evidence"
    assert result["final_stack"]["errors"] == 0
    assert result["final_stack"]["invalid_plan_rate"] == 0.0
