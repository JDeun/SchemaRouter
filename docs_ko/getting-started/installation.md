# 설치

SchemaRouter는 **Python 3.10 이상**이 필요합니다.

## 공개 릴리스 설치

현재 공개 안정판은 `0.15.0`입니다.

```bash
pip install schemarouter
```

0.14.0은 0.12에서 정한 stable-core 경계를 유지하면서 운영 수명주기와 외부 생태계 검증을
보강한 릴리스입니다. Source probe, startup rebinding, storage migration, schema-drift review,
unified shutdown, Capability Explorer, 한·영 문서 전환이 포함됩니다.

[0.14.0 릴리스 노트 보기](../releases/0.14.0.md)

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

공개 release tag와 package metadata에서 현재 정식 배포 버전은 `0.15.0`입니다.
개발 브랜치는 PEP 440의 `.dev0` 표기를 사용해 PyPI에 올라간 안정판과 구분합니다.

## 릴리스 검증

CI에서는 package metadata, wheel/sdist 빌드, 깨끗한 환경에서의 설치, 통합 계약, strict docs
build를 확인합니다. 외부 서비스 상태는 PR 통과 조건과 분리해, 제3자 장애가 릴리스를 막지 않게
했습니다.
