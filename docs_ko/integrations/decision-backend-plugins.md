# Decision backend plugin

SchemaRouter는 model-specific integration을 core에 추가하지 않고 installed Python package에서 third-party bounded decision backend를 load할 수 있습니다. `SystemOneDecisionBackend` 같은 stable built-in transport가 이미 커버하지 않는 decision-model family용입니다.

## Entry-point contract

```toml
[project.entry-points."schemarouter.decision_backends"]
anyjev = "schemarouter_anyjev:create_backend"
```

Entry point는 backend class, factory callable, 또는 `decide(request)`를 가진 preconstructed object일 수 있습니다. Class/factory는 load 시 explicit keyword configuration을 받을 수 있습니다.

## Discovery는 metadata-only

```python
from schemarouter import discover_decision_backend_plugins
for plugin in discover_decision_backend_plugins():
    print(plugin.name, plugin.distribution, plugin.version)
```

Discovery는 plugin code를 import/execute하지 않습니다.

## Explicit loading

```python
from schemarouter import load_decision_backend_plugin
backend = load_decision_backend_plugin(
    "anyjev",
    config={"model": "example/model", "device": "cuda"},
)
```

정확히 지정한 plugin만 import합니다. Plugin load는 trusted installed Python code를 실행하며 SchemaRouter가 모든 installed decision plugin을 auto-load하지 않습니다. Returned backend도 normal bounded-decision contract를 따르고 selected option ID는 planning에 영향을 주기 전에 finite offered ID에 대해 검증됩니다.

## Runnable external-package example

```bash
python -m pip install -e examples/decision_backend_plugin_demo
python examples/decision_backend_plugin_quickstart.py
```

Demo package:

```toml
[project.entry-points."schemarouter.decision_backends"]
demo_bounded = "schemarouter_demo_decision:DemoBoundedDecisionBackend"
```

Demo backend는 execution authority를 받지 않습니다. Finite `DecisionRequest.options`만 받고 query가 offered ID/label과 정확히 맞을 때 그 ID를 반환하며 없으면 abstain합니다. SchemaRouter가 `choose_sync()`/`choose_async()`로 ID를 검증하므로 invented ID는 `PlanningError`로 fail-closed합니다.

Deterministic implementation은 quality benchmark가 아닙니다. Hosted/local model이 `decide()` logic을 대체해도 finite-option validation은 유지됩니다.

## SchemaRouter 수정 없이 plugin benchmark

```bash
export SCHEMAROUTER_DECISION_PLUGIN_CONFIG='{"model":"example/model","device":"cpu"}'
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --decision-plugin anyjev \
  --decision-recall-on-empty
```

다른 configuration env var는 `--decision-plugin-config-env NAME`으로 선택합니다. Report에는 plugin name, discoverable package distribution/version, configuration **key**, configuration env var name을 기록하며 value는 기록하지 않습니다. Secret은 ordinary benchmark metadata보다 dedicated provider credential env var에서 읽는 것이 좋습니다.

## 어떤 extension path를 사용할까?

1. System One wire-compatible model — `SystemOneDecisionBackend`
2. One-off research callable — `CallableDecisionBackend` 또는 `--decision-callable module:function`
3. Reusable third-party integration — `schemarouter.decision_backends` entry-point plugin

Model churn을 SchemaRouter planning/authority model 밖에 유지합니다.

## Quality와 compatibility는 별개

Installed plugin이 자동으로 recommended router가 되는 것은 아닙니다. Production model 교체 전 동일 frozen workload에서 exact routing, unsupported rejection, false-route rate, latency, error, authority violation을 비교해야 합니다.

Provider는 semantic evidence를 제공할 수 있지만 registered local schema와 SchemaRouter validation이 execution authority를 유지합니다.
