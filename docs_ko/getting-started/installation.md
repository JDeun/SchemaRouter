# 설치

SchemaRouter는 **Python 3.10 이상**이 필요합니다.

## 공개 릴리스 설치

현재 공개 안정판은 `0.13.0`입니다.

```bash
pip install schemarouter
```

0.13.0은 0.12 stable-core 경계를 유지하면서 universal capability ingestion, nested field
contract, schema refresh/watch, trusted SDK/client binding, 더 넓은 protocol/framework integration을
추가한 operational-completeness 릴리스입니다.

[0.13.0 릴리스 노트 보기](../releases/0.13.0.md)

## 개발 체크아웃

로컬 개발과 테스트:

```bash
git clone https://github.com/JDeun/SchemaRouter.git
cd SchemaRouter
pip install -e ".[dev]"
```

## 선택 설치 항목

사용하는 통합만 설치하면 됩니다.

=== "MCP"

    ```bash
    pip install "schemarouter[mcp]"
    ```

=== "LangChain"

    ```bash
    pip install "schemarouter[langchain]"
    ```

=== "LlamaIndex"

    ```bash
    pip install "schemarouter[llamaindex]"
    ```

=== "Jev / TypeSafe"

    ```bash
    pip install "schemarouter[jev]"
    ```

=== "Laya"

    ```bash
    pip install "schemarouter[laya]"
    ```

=== "OpenTelemetry"

    ```bash
    pip install "schemarouter[otel]"
    ```

=== "문서 개발"

    ```bash
    pip install -e ".[docs]"
    mkdocs serve
    ```

## 설치 확인

```bash
python -c "import schemarouter; print(schemarouter.__version__)"
```

공개 release tag와 package metadata는 `0.13.0`을 현재 non-prerelease 릴리스로 식별합니다.
개발 브랜치는 PEP 440 `.dev0` 버전을 사용해 공개 artifact와 구분합니다.

## 릴리스 검증

CI에서는 package metadata, wheel/sdist build, clean install, integration contract, strict docs
build를 검증합니다. 외부 provider의 실시간 상태는 deterministic PR gate와 분리합니다.
