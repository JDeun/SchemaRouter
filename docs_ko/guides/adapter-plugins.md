# 서드파티 adapter plugin

SchemaRouter는 Python entry point를 통해 설치된 서드파티 source adapter를 지원합니다. 설치된 entry point를 import하면 로컬 Python code가 실행되므로 plugin loading은 **opt-in**입니다.

## Adapter 패키징

서드파티 package는 다음 entry point를 선언할 수 있습니다.

```toml
[project.entry-points."schemarouter.adapters"]
graphql = "my_package.adapters:GraphQLAdapter"
```

resolved object는 일반 `SourceAdapter` contract를 만족해야 합니다. adapter instance/class/zero-argument factory를 허용합니다.

## Import 없이 탐색

```python
from schemarouter import discover_adapter_plugins

for plugin in discover_adapter_plugins():
    print(plugin.name, plugin.value, plugin.distribution, plugin.version)
```

discovery는 entry-point metadata만 읽고 `EntryPoint.load()`를 호출하지 않습니다.

## 명시적 로드

```python
router.load_adapter_plugins(allowlist={"graphql"})
```

빈 allowlist는 거부하고, 존재하지 않는 요청 이름은 어떤 plugin도 import하기 전에 실패합니다.

## 실행 가능한 외부 package 예제

repository에는 `schemarouter` distribution과 의도적으로 분리된 작은 package가 있습니다.

```bash
python -m pip install -e examples/adapter_plugin_demo
python examples/adapter_plugin_quickstart.py
```

quickstart는 metadata discovery가 plugin code를 import하지 않는지, allowlist로 명시적 import/등록되는지, 정상 planning/validation/projection/execution이 동작하는지 검증합니다. source URL은 `example.invalid`이며 network I/O는 수행하지 않습니다.

## Downstream installed-wheel compatibility smoke

필수 package CI는 clean virtual environment에서 SchemaRouter wheel과 별도 demo distribution을 설치하고 `scripts/downstream_adapter_plugin_smoke.py`를 실행합니다. source tree가 아니라 venv의 `site-packages`에서 import됐는지 확인하고 discovery/import 경계, 정상 실행, schema 위반 거부, trusted local deny rule을 검증합니다.

이는 **downstream compatibility 및 authority-boundary smoke**이며 provider quality/routing accuracy/performance benchmark가 아닙니다.

## 보안 모델

adapter plugin은 다른 application dependency와 마찬가지로 취급하세요. 명시적으로 load하면 Python process 권한으로 실행됩니다. SchemaRouter는 발견한 모든 plugin을 자동 import하지 않고 wildcard allow-all을 제공하지 않으며, remote schema나 planner/model이 설치 package import를 선택하게 하지 않습니다.

로드 후에도 built-in adapter와 동일한 registry, policy, schema validation, binding-drift 경계를 사용합니다.

STAC, gRPC/Protobuf, SOAP/WSDL, bounded AsyncAPI request/reply 사례는 [프로토콜 plugin recipe](protocol-plugin-recipes.md)를 참고하세요.
