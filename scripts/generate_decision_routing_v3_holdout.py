"""Generate the frozen 720-case v3 capability-fit holdout corpus."""

from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG = json.loads(r'''{
  "languages": [
    "en",
    "ko",
    "es",
    "ja",
    "de",
    "mixed"
  ],
  "wrappers": {
    "en": [
      "I do not need an explanation; {core}.",
      "One concrete action only: {core}.",
      "Context may be noisy, but the request is to {core}.",
      "Choose this instead of the nearby alternative: {core}.",
      "user-note[alpha]: {core} — return the relevant result."
    ],
    "ko": [
      "설명 말고 실제로 {core}.",
      "한 가지 작업만 해줘: {core}.",
      "앞뒤 맥락은 무시하고 요청은 {core}.",
      "비슷한 다른 기능 말고 {core}.",
      "사용자 메모[알파]: {core}, 관련 결과만 줘."
    ],
    "es": [
      "No necesito explicación; {core}.",
      "Solo una acción concreta: {core}.",
      "Ignora el ruido del contexto y {core}.",
      "Haz esto y no la alternativa parecida: {core}.",
      "nota-usuario[alfa]: {core}; devuelve el resultado relevante."
    ],
    "ja": [
      "説明ではなく実際に{core}。",
      "具体的な操作を一つだけ: {core}。",
      "周辺の文脈は無視して{core}。",
      "似た別機能ではなく{core}。",
      "user-note[alpha]: {core}、必要な結果だけ返して。"
    ],
    "de": [
      "Keine Erklärung; bitte {core}.",
      "Nur eine konkrete Aktion: {core}.",
      "Ignoriere den Kontextlärm und {core}.",
      "Nicht die ähnliche Alternative, sondern {core}.",
      "user-note[alpha]: {core}; gib nur das passende Ergebnis zurück."
    ],
    "mixed": [
      "설명 말고 actually {core}.",
      "one action만: {core}.",
      "context noise는 ignore하고 {core}.",
      "nearby alternative 말고 {core}.",
      "user-note[alpha]: {core}, relevant result만."
    ]
  },
  "routedCategories": [
    "indirect",
    "elliptical",
    "noisy",
    "contrastive",
    "mixed_context"
  ],
  "routes": [
    {
      "route": "weather.current",
      "values": [
        "Incheon",
        "Jeju",
        "London",
        "Rome",
        "Singapore"
      ],
      "cores": {
        "en": "check what the weather is like right now in {v}",
        "ko": "{v}의 현재 날씨 상태를 확인해줘",
        "es": "comprueba cómo está el clima ahora mismo en {v}",
        "ja": "{v}の今の天気を確認して",
        "de": "prüfe, wie das Wetter gerade in {v} ist",
        "mixed": "{v}의 right-now weather 상태를 check해"
      }
    },
    {
      "route": "weather.forecast",
      "values": [
        "Incheon Friday evening",
        "Jeju next weekend",
        "London tomorrow morning",
        "Rome next Wednesday",
        "Singapore next week"
      ],
      "cores": {
        "en": "show the upcoming weather outlook for {v}",
        "ko": "{v}의 앞으로 날씨 전망을 보여줘",
        "es": "muestra la previsión meteorológica para {v}",
        "ja": "{v}のこれからの天気予報を見せて",
        "de": "zeige die kommende Wettervorhersage für {v}",
        "mixed": "{v} upcoming weather outlook을 보여줘"
      }
    },
    {
      "route": "materials.search",
      "values": [
        "MoS2",
        "h-BN",
        "ZnO",
        "SrTiO3",
        "NiO"
      ],
      "cores": {
        "en": "look up physical material properties such as band gap for {v}",
        "ko": "{v}의 밴드갭 같은 물성 데이터를 조회해줘",
        "es": "consulta propiedades físicas como la banda prohibida de {v}",
        "ja": "{v}のバンドギャップなどの物性を調べて",
        "de": "schlage Materialeigenschaften wie die Bandlücke von {v} nach",
        "mixed": "{v}의 band gap 같은 material property를 lookup해"
      }
    },
    {
      "route": "materials.structure",
      "values": [
        "MoS2",
        "h-BN",
        "ZnO",
        "SrTiO3",
        "NiO"
      ],
      "cores": {
        "en": "retrieve the atomic crystal structure and lattice information for {v}",
        "ko": "{v}의 원자 결정구조와 격자 정보를 가져와",
        "es": "recupera la estructura cristalina atómica y la red de {v}",
        "ja": "{v}の原子結晶構造と格子情報を取得して",
        "de": "hole atomare Kristallstruktur und Gitterinformationen für {v}",
        "mixed": "{v} atomic crystal structure랑 lattice info를 가져와"
      }
    },
    {
      "route": "papers.search",
      "values": [
        "sparse mixture of experts",
        "sodium ion batteries",
        "tool use evaluation",
        "polymer electrolytes",
        "diffusion models"
      ],
      "cores": {
        "en": "find scholarly papers on {v}",
        "ko": "{v} 주제의 학술 논문을 찾아줘",
        "es": "encuentra artículos académicos sobre {v}",
        "ja": "{v}についての学術論文を探して",
        "de": "finde wissenschaftliche Arbeiten zu {v}",
        "mixed": "{v} 주제 scholarly papers를 찾아줘"
      }
    },
    {
      "route": "papers.citations",
      "values": [
        "10.5555/2026.001",
        "10.5555/2026.002",
        "10.5555/2026.003",
        "10.5555/2026.004",
        "10.5555/2026.005"
      ],
      "cores": {
        "en": "retrieve works that cite the paper identified by {v}",
        "ko": "{v} 논문을 인용한 후속 논문을 찾아줘",
        "es": "recupera trabajos que citan el artículo identificado por {v}",
        "ja": "{v}の論文を引用している文献を取得して",
        "de": "hole Arbeiten, die den durch {v} bezeichneten Artikel zitieren",
        "mixed": "{v} paper를 cite한 follow-up works를 찾아줘"
      }
    },
    {
      "route": "finance.quote",
      "values": [
        "NFLX",
        "ORCL",
        "IBM",
        "QCOM",
        "DIS"
      ],
      "cores": {
        "en": "return the latest market price quote for {v}",
        "ko": "{v}의 최신 시장 가격을 조회해줘",
        "es": "devuelve la cotización de mercado más reciente de {v}",
        "ja": "{v}の最新市場価格を取得して",
        "de": "gib den neuesten Marktpreis für {v} zurück",
        "mixed": "{v} latest market quote를 return해"
      }
    },
    {
      "route": "finance.history",
      "values": [
        "NFLX over 18 months",
        "ORCL since last summer",
        "IBM for the previous quarter",
        "QCOM over 3 years",
        "DIS since 2022"
      ],
      "cores": {
        "en": "retrieve the historical price series for {v}",
        "ko": "{v}의 과거 가격 시계열을 가져와",
        "es": "recupera la serie histórica de precios de {v}",
        "ja": "{v}の過去価格の時系列を取得して",
        "de": "hole die historische Kursreihe für {v}",
        "mixed": "{v} historical price series를 가져와"
      }
    },
    {
      "route": "calendar.list",
      "values": [
        "Wednesday morning",
        "next Thursday afternoon",
        "October 12",
        "the end of this month",
        "the next two days"
      ],
      "cores": {
        "en": "show the events already on my calendar for {v}",
        "ko": "{v}에 이미 잡힌 캘린더 일정을 보여줘",
        "es": "muestra los eventos que ya están en mi calendario para {v}",
        "ja": "{v}に入っている予定を表示して",
        "de": "zeige die bereits eingetragenen Termine für {v}",
        "mixed": "{v}에 already scheduled calendar events를 보여줘"
      }
    },
    {
      "route": "calendar.create",
      "values": [
        "architecture review Wednesday at 10:30",
        "coffee with Mina Friday at 8",
        "security review Monday at 14:00",
        "roadmap sync Tuesday at 16:30",
        "focus block Thursday at 9"
      ],
      "cores": {
        "en": "add a new calendar event for {v}",
        "ko": "{v} 일정을 새 캘린더 이벤트로 추가해줘",
        "es": "añade un nuevo evento de calendario para {v}",
        "ja": "{v}を新しいカレンダー予定として追加して",
        "de": "füge einen neuen Kalendereintrag für {v} hinzu",
        "mixed": "{v}를 new calendar event로 add해"
      }
    },
    {
      "route": "support.search",
      "values": [
        "SSO configuration",
        "invoice VAT handling",
        "API rate limits",
        "workspace deletion",
        "webhook retry policy"
      ],
      "cores": {
        "en": "look up the support documentation for {v}",
        "ko": "{v} 관련 지원 문서를 찾아줘",
        "es": "busca la documentación de soporte para {v}",
        "ja": "{v}に関するサポート文書を探して",
        "de": "suche die Support-Dokumentation für {v}",
        "mixed": "{v} 관련 support docs를 lookup해"
      }
    },
    {
      "route": "support.create_ticket",
      "values": [
        "SSO redirect loop",
        "duplicated invoice",
        "webhook returns 401",
        "workspace cannot be deleted",
        "API keeps timing out"
      ],
      "cores": {
        "en": "open a support ticket for this problem: {v}",
        "ko": "{v} 문제로 지원 티켓을 접수해줘",
        "es": "abre un ticket de soporte por este problema: {v}",
        "ja": "{v}の問題でサポートチケットを作成して",
        "de": "eröffne ein Support-Ticket für dieses Problem: {v}",
        "mixed": "{v} 문제로 support ticket을 open해"
      }
    },
    {
      "route": "inventory.search",
      "values": [
        "ITEM-X17",
        "ITEM-Y28",
        "ITEM-Z39",
        "ITEM-K41",
        "ITEM-M52"
      ],
      "cores": {
        "en": "read the current stock quantity for {v}",
        "ko": "{v}의 현재 재고 수량을 조회해줘",
        "es": "consulta la cantidad actual de existencias de {v}",
        "ja": "{v}の現在庫数を取得して",
        "de": "lies den aktuellen Lagerbestand für {v}",
        "mixed": "{v} current stock quantity를 read해"
      }
    },
    {
      "route": "inventory.update",
      "values": [
        "ITEM-X17 to 18",
        "ITEM-Y28 to 0",
        "ITEM-Z39 to 44",
        "ITEM-K41 to 6",
        "ITEM-M52 to 71"
      ],
      "cores": {
        "en": "change the stored inventory quantity for {v}",
        "ko": "{v}로 저장된 재고 수량을 변경해줘",
        "es": "cambia la cantidad de inventario almacenada de {v}",
        "ja": "在庫数量を{v}に変更して",
        "de": "ändere den gespeicherten Lagerbestand für {v}",
        "mixed": "stored inventory quantity를 {v}로 change해"
      }
    },
    {
      "route": "users.lookup",
      "values": [
        "user 314",
        "dev@example.org",
        "Mina Park",
        "account 808",
        "Luca Rossi"
      ],
      "cores": {
        "en": "retrieve the existing user profile for {v}",
        "ko": "{v}의 기존 사용자 프로필을 조회해줘",
        "es": "recupera el perfil de usuario existente de {v}",
        "ja": "{v}の既存ユーザープロフィールを取得して",
        "de": "hole das vorhandene Benutzerprofil für {v}",
        "mixed": "{v} existing user profile을 retrieve해"
      }
    },
    {
      "route": "users.update",
      "values": [
        "user 314 locale to ko-KR",
        "dev@example.org timezone",
        "Mina Park job title",
        "account 808 display name",
        "Luca Rossi department"
      ],
      "cores": {
        "en": "modify the stored user profile for {v}",
        "ko": "{v} 사용자 프로필 정보를 수정해줘",
        "es": "modifica el perfil de usuario almacenado de {v}",
        "ja": "{v}の保存済みユーザープロフィールを変更して",
        "de": "ändere das gespeicherte Benutzerprofil für {v}",
        "mixed": "{v} stored user profile을 modify해"
      }
    }
  ],
  "ood": {
    "en": [
      "explain how weather fronts form",
      "write a literature review about battery research",
      "calculate compound interest for my savings",
      "design a calendar icon for a mobile app",
      "draft a new customer support FAQ article",
      "design an inventory database schema",
      "write onboarding copy for new users",
      "translate this sentence into French"
    ],
    "ko": [
      "기상 전선이 어떻게 형성되는지 설명해줘",
      "배터리 연구에 대한 문헌 리뷰를 써줘",
      "내 저축의 복리 이자를 계산해줘",
      "모바일 앱용 캘린더 아이콘을 디자인해줘",
      "새 고객지원 FAQ 문서를 작성해줘",
      "재고 관리용 데이터베이스 스키마를 설계해줘",
      "신규 사용자 온보딩 문구를 써줘",
      "이 문장을 프랑스어로 번역해줘"
    ],
    "es": [
      "explica cómo se forman los frentes meteorológicos",
      "escribe una revisión bibliográfica sobre investigación de baterías",
      "calcula el interés compuesto de mis ahorros",
      "diseña un icono de calendario para una aplicación móvil",
      "redacta un nuevo artículo de preguntas frecuentes de soporte",
      "diseña un esquema de base de datos de inventario",
      "escribe texto de bienvenida para nuevos usuarios",
      "traduce esta frase al francés"
    ],
    "ja": [
      "気象前線がどのように形成されるか説明して",
      "電池研究について文献レビューを書いて",
      "貯蓄の複利を計算して",
      "モバイルアプリ用のカレンダーアイコンをデザインして",
      "新しいサポートFAQ記事を書いて",
      "在庫管理データベースのスキーマを設計して",
      "新規ユーザー向けオンボーディング文を書いて",
      "この文をフランス語に翻訳して"
    ],
    "de": [
      "erkläre, wie Wetterfronten entstehen",
      "schreibe einen Literaturüberblick zur Batterieforschung",
      "berechne den Zinseszins für meine Ersparnisse",
      "entwirf ein Kalender-Icon für eine mobile App",
      "verfasse einen neuen Support-FAQ-Artikel",
      "entwirf ein Datenbankschema für Inventar",
      "schreibe Onboarding-Texte für neue Benutzer",
      "übersetze diesen Satz ins Französische"
    ],
    "mixed": [
      "weather front가 어떻게 formed 되는지 explain해",
      "battery research literature review를 write해",
      "내 savings compound interest를 calculate해",
      "mobile app calendar icon을 design해",
      "새 support FAQ article을 draft해",
      "inventory database schema를 design해",
      "new users onboarding copy를 write해",
      "이 sentence를 French로 translate해"
    ]
  }
}''')

def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for route in CONFIG["routes"]:
        route_id = route["route"].replace(".", "-").replace("_", "-")
        for language in CONFIG["languages"]:
            for index in range(5):
                core = route["cores"][language].replace("{v}", route["values"][index])
                cases.append({
                    "id": f"v3-{route_id}-{language}-{index + 1}",
                    "query": CONFIG["wrappers"][language][index].replace("{core}", core),
                    "expected": route["route"],
                    "category": CONFIG["routedCategories"][index],
                    "expect_abstain": False,
                    "split": "fresh_holdout",
                    "language": language,
                })
    for language in CONFIG["languages"]:
        for core_index, core in enumerate(CONFIG["ood"][language]):
            for index in range(5):
                cases.append({
                    "id": f"v3-no-route-{language}-{core_index + 1}-{index + 1}",
                    "query": CONFIG["wrappers"][language][index].replace("{core}", core),
                    "expected": None,
                    "category": "near_domain_ood" if core_index < 7 else "general_ood",
                    "expect_abstain": True,
                    "split": "fresh_holdout",
                    "language": language,
                })
    return cases

def validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 720:
        raise ValueError(f"expected 720 cases, got {len(cases)}")
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
    destination = Path("benchmarks/decision-routing-v3-holdout.json")
    destination.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} cases to {destination}")

if __name__ == "__main__":
    main()
