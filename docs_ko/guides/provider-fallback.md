# Provider-aware fallback

fallback은 runtime 오류 뒤 model에게 다시 생각하게 하는 open-ended replanning이 아닙니다. planning 시점에 trusted schema로 **유한한 read-only 대체 route**를 미리 컴파일합니다.

`fallback_scope="same_provider"`는 같은 provider의 다른 access mode를 우선하고 `cross_provider`는 명시적 semantic compatibility가 있는 다른 provider까지 허용합니다. 각 fallback은 자신의 argument mapping, field contract, tool/endpoint fingerprint를 가진 완전한 `ToolCall`입니다.

semantic ID, datatype, unit/normalization, qualifier가 호환되지 않으면 자동 대체하지 않습니다. health cooldown은 일시적 실패를 영구 ban으로 만들지 않으며 만료/신뢰된 probe 성공 후 route를 다시 열 수 있습니다. fallback event는 trace에 명시적으로 기록됩니다.
