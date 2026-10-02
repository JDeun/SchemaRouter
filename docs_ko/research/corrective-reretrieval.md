# Corrective re-retrieval

issue #431 연구는 첫 retrieval 이후 execution/answer state를 이용한 bounded corrective re-retrieval이 static shortlist보다 실패 복구를 개선하는지 평가합니다.

설계는 180 tasks × catalog 100/250/500에서 SR-5-STATIC, SR-PROGRESSIVE-STATIC, SR-5-STATE-AWARE, FULL, ORACLE 조건을 비교합니다. scientific source revision과 workload를 고정하고 infrastructure/cache failure는 scientific failure와 분리합니다.

state-aware 방식이 추가 retrieval을 허용하더라도 registered capability와 local execution authority 밖의 route를 만들 수 없습니다. downstream #432 held-out와 #424 final-answer 연구는 이 결과를 독립적으로 확인하는 역할을 합니다.
