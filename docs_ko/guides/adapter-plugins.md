# 서드파티 어댑터 플러그인

SchemaRouter는 Python 엔트리 포인트를 통해 설치된 서드파티 소스 어댑터를 지원합니다.

설치된 엔트리 포인트를 불러오는 과정에서 로컬 Python 코드가 실행되므로 **플러그인 로드는 명시적으로 활성화(opt-in)**해야 합니다.

## 어댑터 패키지 만들기

서드파티 패키지는 다음과 같이 선언할 수 있습니다.

```toml
[project.entry-points."schemarouter.adapters"]
graphql = "my_package.adapters:GraphQLAdapter"
```

실제로 해석된 객체는 일반적인 `SourceAdapter` 계약을 만족해야 합니다.

```python
class GraphQLAdapter:
    kind = "graphql"
    priority = 50

    async def load(self, context):
        ...
```

어댑터 인스턴스, 어댑터 클래스 또는 인자를 받지 않는 팩토리를 사용할 수 있습니다.

## 코드 임포트 없이 탐색하기

```python
from schemarouter import discover_adapter_plugins

for plugin in discover_adapter_plugins():
    print(plugin.name, plugin.value, plugin.distribution, plugin.version)
```

탐색 시에는 엔트리 포인트 메타데이터만 읽습니다. `EntryPoint.load()`를 호출하지 않습니다.

## 명시적으로 로드하기

```python
router.load_adapter_plugins(
    allowlist={"graphql"},
)
```

또는 다음처럼 사용할 수 있습니다.

```python
from schemarouter import AdapterRegistry, load_adapter_plugins

registry = AdapterRegistry()
load_adapter_plugins(
    registry,
    allowlist={"graphql"},
)
```

비어 있는 allowlist는 거부합니다. 존재하지 않는 이름을 요청하면 어떠한 플러그인도 임포트하기 전에 실패합니다.

## 실행 가능한 외부 패키지 예제

저장소에는 `schemarouter` 배포판과 의도적으로 분리한 작은 패키지가 포함되어 있습니다.

```bash
python -m pip install -e examples/adapter_plugin_demo
python examples/adapter_plugin_quickstart.py
```

패키지 메타데이터에는 실제 엔트리 포인트를 선언합니다.

```toml
[project.entry-points."schemarouter.adapters"]
demo_static = "schemarouter_demo_adapter:DemoStaticAdapter"
```

Quickstart는 신뢰 경계를 직접 검증합니다.

1. `discover_adapter_plugins()`가 엔트리 포인트 메타데이터를 찾지만 `schemarouter_demo_adapter`는 아직 `sys.modules`에 존재하지 않습니다.
2. `router.load_adapter_plugins(allowlist={"demo_static"})`가 요청한 플러그인만 명시적으로 임포트하고 등록합니다.
3. `router.add_url(..., kind="demo_static")`가 일반적인 `ToolSpec`과 신뢰된 invoker를 구성합니다.
4. 기존의 계획 수립, 인자·출력 검증, 필드 투영, 실행 경로를 거쳐 `{"value": 5}`를 반환합니다.

소스 URL은 `example.invalid`이며 어댑터는 네트워크 I/O를 수행하지 않습니다. URL은 플러그인이 구조화된 소스 식별자를 알아볼 수 있음을 보여 주기 위해서만 사용하며, 데모의 결정론적 특성을 유지합니다.

소스:
[`examples/adapter_plugin_demo/`](https://github.com/JDeun/SchemaRouter/tree/main/examples/adapter_plugin_demo)

## 별도 설치된 wheel을 이용한 하위 프로젝트 호환성 검사

필수 패키지 CI에서는 **분리된 새 가상환경**을 사용해 플러그인을 테스트합니다.

1. SchemaRouter wheel을 빌드합니다.
2. 새 가상환경에 해당 wheel을 설치합니다.
3. `schemarouter.adapters` 엔트리 포인트를 실제로 선언하는 `examples/adapter_plugin_demo`를 별도 배포판으로 설치합니다.
4. `scripts/downstream_adapter_plugin_smoke.py`를 실행합니다.

이 검사는 SchemaRouter를 저장소 소스 트리가 아니라 가상환경의 `site-packages`에서 임포트했는지 확인합니다. 또한 메타데이터 탐색 과정에서 플러그인 코드가 임포트되지 않는지, allowlist를 통한 명시적 로드가 요청한 플러그인만 임포트하는지, 정상 호출이 성공하는지 확인합니다. 등록된 JSON Schema를 위반한 입력을 거부하고, 신뢰된 로컬 거부 정책이 플러그인이 제공한 invoker에도 적용됨을 검증합니다.

이는 **하위 프로젝트 호환성과 실행 권한 경계**를 위한 스모크 테스트입니다. 공급자 품질, 라우팅 정확도 또는 성능 벤치마크가 아닙니다. 네트워크와 자격 증명을 사용하지 않습니다.

## 보안 모델

어댑터 플러그인은 다른 설치형 애플리케이션 의존성과 동일하게 취급해야 합니다. 명시적으로 로드하면 Python 프로세스와 동일한 권한으로 실행됩니다.

SchemaRouter가 하지 않는 일:

- 발견한 모든 플러그인을 자동으로 임포트하지 않습니다.
- 와일드카드나 암묵적인 전체 허용(allow-all) 모드를 제공하지 않습니다.
- 원격 스키마 콘텐츠가 플러그인 로드를 요청하도록 허용하지 않습니다.
- 플래너나 모델이 어떤 설치 패키지를 임포트할지 선택하게 하지 않습니다.

로드한 뒤에도 어댑터는 내장 어댑터와 동일한 레지스트리, 정책, 스키마 검증, 바인딩 변경 감지 경계를 사용합니다.

## 프로토콜별 사용 방법

STAC, gRPC/Protobuf, SOAP/WSDL, 그리고 제한된 AsyncAPI 요청·응답 패턴은 [프로토콜 플러그인 레시피](protocol-plugin-recipes.md)를 참고하십시오. OpenAPI나 타입이 있는 Python 래퍼를 우선할 조건, SourceAdapter 플러그인이 실제로 가치 있는 경우, 일반적인 ToolCall 추상화 밖에 남겨야 하는 스트리밍·이벤트 생명주기를 설명합니다.
