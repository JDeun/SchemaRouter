"""Generate the frozen 576-case v4 capability-fit holdout corpus."""

from __future__ import annotations

import json
import re
from pathlib import Path

from generate_decision_routing_v3_holdout import CONFIG as BASE_CONFIG

V4 = json.loads(r'''{
  "wrappers": {
    "en": [
      "Operational request: {core}.",
      "Skip the analysis and {core}.",
      "The intended action is this — {core}.",
      "Do exactly this task: {core}."
    ],
    "ko": [
      "실행 요청: {core}.",
      "분석은 생략하고 {core}.",
      "의도한 작업은 이것이야: {core}.",
      "정확히 이 작업만 해줘: {core}."
    ],
    "es": [
      "Solicitud operativa: {core}.",
      "Omite el análisis y {core}.",
      "La acción prevista es esta: {core}.",
      "Haz exactamente esta tarea: {core}."
    ],
    "ja": [
      "実行依頼: {core}。",
      "分析は省いて{core}。",
      "意図している操作はこれです: {core}。",
      "この作業だけを正確に実行して: {core}。"
    ],
    "de": [
      "Operative Anfrage: {core}.",
      "Lass die Analyse weg und {core}.",
      "Die beabsichtigte Aktion ist: {core}.",
      "Führe genau diese Aufgabe aus: {core}."
    ],
    "mixed": [
      "execution request: {core}.",
      "analysis는 skip하고 {core}.",
      "intended action은 이거야: {core}.",
      "exactly 이 task만 해줘: {core}."
    ]
  },
  "categories": [
    "operational",
    "directive",
    "intent_explicit",
    "strict_scope"
  ],
  "ood": {
    "en": [
      "explain how climate change affects rainfall patterns",
      "explain why silicon has a band gap",
      "write an abstract for my paper about retrieval augmented generation",
      "explain what a price-to-earnings ratio means",
      "write a polite invitation message for a project meeting",
      "rewrite this customer support response to sound friendlier",
      "calculate inventory turnover from these accounting numbers",
      "design a user profile card interface"
    ],
    "ko": [
      "기후 변화가 강수 패턴에 어떤 영향을 주는지 설명해줘",
      "실리콘에 밴드갭이 생기는 이유를 설명해줘",
      "검색증강생성에 관한 내 논문의 초록을 써줘",
      "주가수익비율이 무엇을 의미하는지 설명해줘",
      "프로젝트 회의용 정중한 초대 문구를 써줘",
      "이 고객지원 답변을 더 친절한 문장으로 고쳐줘",
      "이 회계 숫자로 재고회전율을 계산해줘",
      "사용자 프로필 카드 UI를 디자인해줘"
    ],
    "es": [
      "explica cómo afecta el cambio climático a los patrones de lluvia",
      "explica por qué el silicio tiene una banda prohibida",
      "escribe un resumen para mi artículo sobre generación aumentada por recuperación",
      "explica qué significa la relación precio-beneficio",
      "escribe una invitación educada para una reunión de proyecto",
      "reescribe esta respuesta de soporte para que suene más amable",
      "calcula la rotación de inventario con estas cifras contables",
      "diseña una interfaz de tarjeta de perfil de usuario"
    ],
    "ja": [
      "気候変動が降雨パターンにどう影響するか説明して",
      "シリコンにバンドギャップがある理由を説明して",
      "検索拡張生成についての私の論文の要旨を書いて",
      "株価収益率の意味を説明して",
      "プロジェクト会議の丁寧な招待文を書いて",
      "このサポート回答をもっと親切な表現に書き直して",
      "この会計数値から在庫回転率を計算して",
      "ユーザープロフィールカードのUIをデザインして"
    ],
    "de": [
      "erkläre, wie der Klimawandel Niederschlagsmuster beeinflusst",
      "erkläre, warum Silizium eine Bandlücke hat",
      "schreibe eine Zusammenfassung für meine Arbeit über Retrieval-Augmented Generation",
      "erkläre, was das Kurs-Gewinn-Verhältnis bedeutet",
      "schreibe eine höfliche Einladung für ein Projekttreffen",
      "formuliere diese Support-Antwort freundlicher",
      "berechne den Lagerumschlag aus diesen Buchhaltungszahlen",
      "entwirf eine Benutzerprofilkarten-Oberfläche"
    ],
    "mixed": [
      "climate change가 rainfall pattern에 미치는 영향을 explain해",
      "silicon에 band gap이 생기는 이유를 explain해",
      "내 retrieval augmented generation paper abstract를 write해",
      "P/E ratio가 무슨 뜻인지 explain해",
      "project meeting용 polite invitation message를 write해",
      "이 support response를 friendlier하게 rewrite해",
      "이 accounting numbers로 inventory turnover를 calculate해",
      "user profile card UI를 design해"
    ]
  }
}''')

def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for route in BASE_CONFIG["routes"]:
        route_id = route["route"].replace(".", "-").replace("_", "-")
        for language_index, language in enumerate(BASE_CONFIG["languages"]):
            for index in range(4):
                values = route["values"]
                value = values[(index + language_index) % len(values)]
                core = route["cores"][language].replace("{v}", value)
                cases.append({
                    "id": f"v4-{route_id}-{language}-{index + 1}",
                    "query": V4["wrappers"][language][index].replace("{core}", core),
                    "expected": route["route"],
                    "category": V4["categories"][index],
                    "expect_abstain": False,
                    "split": "fresh_holdout",
                    "language": language,
                })
    for language in BASE_CONFIG["languages"]:
        for core_index, core in enumerate(V4["ood"][language]):
            for index in range(4):
                cases.append({
                    "id": f"v4-no-route-{language}-{core_index + 1}-{index + 1}",
                    "query": V4["wrappers"][language][index].replace("{core}", core),
                    "expected": None,
                    "category": "near_domain_ood",
                    "expect_abstain": True,
                    "split": "fresh_holdout",
                    "language": language,
                })
    return cases

def validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 576:
        raise ValueError(f"expected 576 cases, got {len(cases)}")
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case IDs")
    normalized: set[str] = set()
    for case in cases:
        query = str(case["query"])
        norm = re.sub(r"[^\w]+", "", query.casefold())
        if norm in normalized:
            raise ValueError(f"duplicate normalized query: {query!r}")
        normalized.add(norm)

def main() -> None:
    cases = build()
    validate(cases)
    destination = Path("benchmarks/decision-routing-v4-holdout.json")
    destination.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} cases to {destination}")

if __name__ == "__main__":
    main()
