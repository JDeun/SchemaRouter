# PydanticAI 외부 검증 경로

PydanticAI의 ToolSearch 전략과 SchemaRouter의 bounded capability retrieval을 조합하는 maintainer-side validation입니다. PydanticAI가 agent/runtime lifecycle을 소유하고 SchemaRouter는 registered capability를 좁혀 typed contract를 제공하는 경계를 유지합니다.

이 문서는 **E0 근거**이며 PydanticAI가 SchemaRouter를 채택했다는 의미가 아닙니다. 외부 issue/discussion/PR/test가 공개적으로 생성되어야 E1/E2로 승격할 수 있습니다. 실행 approval과 transport authority는 downstream runtime이 소유하고 SchemaRouter retrieval 결과 자체는 권한이 아닙니다.
