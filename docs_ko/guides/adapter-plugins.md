# Third-party adapter plugins

SchemaRouter는 Python entry point를 통해 설치된 third-party source adapter를 지원합니다.

설치된 entry point import는 local Python code를 실행하므로 plugin loading은 **opt-in**입니다.

## Adapter 패키징

third-party package는 다음처럼 선언할 수 있습니다:

```toml
[project.entry-points."schemarouter.adapters"]
graphql = "my_package.adapters:GraphQLAdapter"
```

resolve된 object는 일반 `SourceAdapter` contract를 만족해야 합니다:

```python
class GraphQLAdapter:
    kind = "graphql"
    priority = 50

    async def load(self, context):
        ...
```

adapter instance, adapter class, zero-argument factory를 사용할 수 있습니다.

## Import 없이 탐색

```python
from schemarouter import discover_adapter_plugins

for plugin in discover_adapter_plugins():
    print(plugin.name, plugin.value, plugin.distribution, plugin.version)
```

discovery는 entry-point metadata만 읽고 `EntryPoint.load()`를 호출하지 않습니다.

## 명시적 로드

```python
router.load_adapter_plugins(
    allowlist={"graphql"},
)
```

또는:

```python
from schemarouter import AdapterRegistry, load_adapter_plugins

registry = AdapterRegistry()
load_adapter_plugins(
    registry,
    allowlist={"graphql"},
)
```

빈 allowlist는 거부됩니다. 알 수 없는 이름은 plugin import 전에 실패합니다.

## 실행 가능한 외부 package 예제

repository에는 의도적으로 `schemarouter` distribution과 분리된 작은 package 예제가 포함되어 있습니다:

```bash
python -m pip install -e examples/adapter_plugin_demo
python examples/adapter_plugin_quickstart.py
```

package metadata는 실제 entry point를 선언합니다:

```toml
[project.entry-points."schemarouter.adapters"]
demo_static = "schemarouter_demo_adapter:DemoStaticAdapter"
```

quickstart는 trust boundary를 직접 검증합니다:

1. `discover_adapter_plugins()`는 `schemarouter_demo_adapter`가 아직 `sys.modules`에 없는 상태에서 entry-point metadata를 확인합니다.
2. `router.load_adapter_plugins(allowlist={"demo_static"})`가 요청된 plugin을 명시적으로 import/register합니다.
3. `router.add_url(..., kind="demo_static")`가 일반 `ToolSpec`과 trusted invoker를 compile합니다.
4. 일반 planning, argument/output validation, field projection, execution이 `{"value": 5}`를 반환합니다.

source URL은 `example.invalid`이며 adapter는 network I/O를 수행하지 않습니다. 이 URL은 demo를 deterministic하게 유지하면서 plugin이 structured source identifier를 인식할 수 있음을 보여주기 위한 것입니다.

Source:
[`examples/adapter_plugin_demo/`](https://github.com/JDeun/SchemaRouter/tree/main/examples/adapter_plugin_demo)

## Downstream installed-wheel compatibility smoke

필수 package CI는 **분리된 clean virtual environment**에서도 plugin을 검증합니다:

1. SchemaRouter wheel을 build합니다.
2. 해당 wheel을 fresh venv에 install합니다.
3. 실제 `schemarouter.adapters` entry point를 가진 별도 distribution으로 `examples/adapter_plugin_demo`를 install합니다.
4. `scripts/downstream_adapter_plugin_smoke.py`를 실행합니다.

이 smoke는 SchemaRouter가 repository source tree가 아니라 venv의 `site-packages`에서 import되었음을 검증합니다. 이어서 metadata discovery가 plugin code를 import하지 않는지, explicit allowlisting이 요청된 plugin만 정확히 import하는지, valid execution이 성공하는지, registered JSON Schema를 위반한 input이 거부되는지, trusted local deny rule이 plugin-supplied invoker도 계속 차단하는지를 검증합니다.

이는 provider quality, routing accuracy, performance benchmark가 아니라 **downstream compatibility 및 authority-boundary smoke**입니다. network access와 credential을 사용하지 않습니다.

## 보안 모델

adapter plugin은 다른 설치 application dependency와 동일하게 취급해야 합니다. 명시적으로 load되면 Python process 권한으로 실행됩니다.

SchemaRouter는 다음을 하지 않습니다:

- discover한 모든 plugin의 auto-import
- wildcard/implicit allow-all mode 허용
- remote schema content의 plugin loading 요청 허용
- planner/model이 import할 installed package를 선택하도록 허용

load 후에도 adapter는 built-in adapter와 동일한 registry, policy, schema validation, binding-drift boundary를 사용합니다.

## Protocol별 recipe

STAC, gRPC/Protobuf, SOAP/WSDL, bounded AsyncAPI request/reply 사례는 [Protocol plugin recipes](protocol-plugin-recipes.md)를 참고합니다. OpenAPI/typed Python wrapper를 우선할 때, SourceAdapter plugin이 실제 가치를 더하는 경우, 일반 ToolCall abstraction 밖에 두어야 할 streaming/event lifecycle을 설명합니다.
