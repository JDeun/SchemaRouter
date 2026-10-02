# Registry와 schema identity

registry는 planner/executor가 사용하는 authoritative catalog입니다. namespace를 포함한 collision-safe key를 사용하고 모든 mutation은 monotonic version을 증가시킵니다. read는 detached snapshot을 반환해 외부 object mutation으로 contract가 조용히 바뀌지 않게 합니다.

fingerprint에는 parameter/field/schema/side-effect/evidence/remote/execution metadata 등 planner·execution contract가 포함되고 arbitrary descriptive metadata는 제외됩니다. 오래된 endpoint/tool fingerprint는 `SchemaDriftError`, 오래된 invoker binding은 `BindingDriftError`로 실패합니다.

`SQLiteRegistry`는 tool order/version을 restart 사이에 보존하고 transactional write를 제공합니다. Pydantic JSON을 저장하며 pickle이나 runtime authority를 저장하지 않습니다. restart 뒤 invoker/credential/policy는 trusted application이 다시 바인딩해야 합니다.

trusted local amendment는 결과 의미를 보강할 수 있지만 execution identity나 validation shape를 바꿀 수 없습니다. semantic ID, alias, result path, unit/normalization/qualifier, identifier/source type/licence 등은 보강할 수 있으나 method/path/parameter/input schema/read-only/destructive/execution metadata나 source-published field 제거는 허용하지 않습니다.
