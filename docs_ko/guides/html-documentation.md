# 사람이 읽는 API 문서

사람이 읽는 API 페이지는 OpenAPI/MCP보다 약한 근거이므로 SchemaRouter는 이를 실행 가능한 schema source가 아니라 **proposal source**로 취급합니다.

## 문서 페이지 검사

```python
from schemarouter import SchemaRouter

async def documentation_model(payload: dict) -> dict:
    # structured-output model로 payload 전송
    ...

router = SchemaRouter()
proposal = await router.inspect_url(
    "https://docs.example.com/api",
    model=documentation_model,
)
```

proposal에는 grounded 여부, 근거가 충분할 때의 proposed `ToolSpec`, grounding score, uncertainty, rejected item이 포함됩니다.

## Grounding 규칙

허용되는 모든 endpoint, parameter, field에는 가져온 문서에 실제로 존재하는 evidence quote가 있어야 합니다. model proposal의 exact quote가 문서에 없으면 해당 candidate는 거부됩니다. script/style/noscript/SVG는 model에 문서 text를 전달하기 전에 제거합니다.

## 승인은 별도의 권한 전환

grounded proposal도 아직 실행할 수 없습니다.

```python
router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
    min_grounding_score=0.8,
)
```

mutating method에는 추가 명시적 opt-in이 필요합니다. 승인 후에도 execution policy가 적용되므로 runtime side-effect gate를 우회하지 않습니다.

## Redirect와 URL 안전

문서 URL은 embedded credential이 없는 absolute HTTP(S) URL이어야 하며 redirect는 원래 origin으로 제한됩니다. SchemaRouter는 local/private endpoint를 의도적으로 지원하므로 untrusted end user가 URL을 제공할 수 있는 서비스라면 hosting application이 자체 URL admission/egress policy를 추가해야 합니다. [보안 threat model](../security/threat-model.md)을 참고하세요.

## 한계

현재는 최초 HTTP response를 읽습니다. browser-side JavaScript rendering이 필요하거나 여러 페이지에 걸친 문서는 향후 crawler/rendering adapter가 필요할 수 있습니다.
