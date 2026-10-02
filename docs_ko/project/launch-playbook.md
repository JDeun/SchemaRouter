# 개발자 공개 캠페인 playbook

SchemaRouter 0.14.0의 launch narrative는 “많은 heterogeneous tool/schema를 매 turn model context에 모두 넣지 말고 필요한 capability만 typed retrieval한 뒤 schema-aware execution boundary를 유지한다”는 문제에서 시작합니다.

기본 CTA는 재현성을 위해 `pip install "schemarouter==0.14.0"`을 사용합니다. 일반 설치에서는 `pip install schemarouter`가 최신 stable release를 해석하며, 공개 launch demo만 0.14.0으로 고정해 walkthrough의 재현성을 유지합니다. 5분 quickstart와 deterministic demo, “왜 모든 tool schema를 그냥 LLM에 보내지 않는가?” 설명, integration example, limitations를 함께 제공합니다.

Show HN, Reddit/developer community, LinkedIn/long-form article은 각 community 규칙에 맞게 별도 문안으로 조정합니다. 특히 2026년 현재 Hacker News는 submission text와 comment를 submitter 본인이 작성하도록 안내하고 있으며, Show HN 참여에도 계정의 정상적인 community participation과 관련된 제한이 있을 수 있습니다. 게시 직전에 공식 Show HN/site guideline과 maintainer account eligibility를 다시 확인해야 하며, 저장소의 draft는 coverage checklist로만 사용하고 그대로 붙여넣지 않습니다.

연구에서 아직 통과하지 않은 성능 수치를 stable product claim처럼 사용하지 않고 vote solicitation/cross-post spam을 하지 않습니다. Stable product 기준 release는 0.14.0이며 Python 3.10–3.14 CI, typed ingestion/execution path, execution-authority boundary와 공개 verification evidence를 기준으로 설명합니다.

각 publication은 canonical URL/time, 게시 직전 Growth Scorecard snapshot, 24h/7d snapshot, substantive question/objection, 그 결과 생긴 docs/product change를 launch log에 기록합니다. 외부 계정에서 실제 게시되기 전에는 URL이나 adoption outcome을 만들어내지 않습니다.
