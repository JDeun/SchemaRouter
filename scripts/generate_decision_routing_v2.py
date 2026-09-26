"""Generate the deterministic 1,200-case decision-routing v2 stress corpus."""

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
      "{core}",
      "please {core}",
      "can you {core}",
      "I need this: {core}",
      "for this task, {core}",
      "quick request — {core}",
      "the result I need is: {core}",
      "help me with the following: {core}",
      "ignore unrelated details and {core}",
      "return only what is needed to {core}"
    ],
    "ko": [
      "{core}",
      "부탁인데 {core}",
      "{core} 가능해?",
      "필요한 건 이거야: {core}",
      "이 작업에서는 {core}",
      "빠르게 {core}",
      "내가 원하는 결과는 {core}",
      "다음 요청을 처리해줘: {core}",
      "다른 얘기는 무시하고 {core}",
      "필요한 정보만 기준으로 {core}"
    ],
    "es": [
      "{core}",
      "por favor, {core}",
      "¿puedes {core}?",
      "necesito esto: {core}",
      "para esta tarea, {core}",
      "solicitud rápida: {core}",
      "el resultado que necesito es: {core}",
      "ayúdame con esto: {core}",
      "ignora lo demás y {core}",
      "devuelve solo lo necesario para {core}"
    ],
    "ja": [
      "{core}",
      "お願いします、{core}",
      "{core}できますか",
      "必要なのはこれです: {core}",
      "この作業では{core}",
      "簡単に{core}",
      "欲しい結果は{core}",
      "次の依頼です: {core}",
      "他の内容は無視して{core}",
      "必要な情報だけで{core}"
    ],
    "de": [
      "{core}",
      "bitte {core}",
      "kannst du {core}",
      "ich brauche Folgendes: {core}",
      "für diese Aufgabe: {core}",
      "kurze Anfrage: {core}",
      "das gewünschte Ergebnis: {core}",
      "hilf mir dabei: {core}",
      "ignoriere Nebensachen und {core}",
      "liefere nur das Nötige, um {core}"
    ],
    "mixed": [
      "{core}",
      "please {core} 해줘",
      "{core} 가능?",
      "I need this 결과: {core}",
      "이 task에서는 {core}",
      "quick하게 {core}",
      "원하는 result는 {core}",
      "help me: {core}",
      "다른 내용 ignore하고 {core}",
      "only 필요한 정보로 {core}"
    ]
  },
  "routes": [
    {
      "route": "weather.current",
      "values": [
        "Seoul",
        "Busan",
        "Tokyo",
        "Madrid",
        "Berlin",
        "Osaka",
        "New York",
        "Paris",
        "Daejeon",
        "Hamburg"
      ],
      "cores": {
        "en": "get the current weather in {v}",
        "ko": "{v}의 지금 날씨를 알려줘",
        "es": "obtén el clima actual en {v}",
        "ja": "{v}の現在の天気を調べて",
        "de": "ermittle das aktuelle Wetter in {v}",
        "mixed": "{v} 지금 weather를 확인해"
      }
    },
    {
      "route": "weather.forecast",
      "values": [
        "Seoul tomorrow",
        "Busan this weekend",
        "Tokyo next Monday",
        "Madrid tomorrow",
        "Berlin next week",
        "Osaka tonight",
        "New York this weekend",
        "Paris next Tuesday",
        "Daejeon tomorrow",
        "Hamburg next week"
      ],
      "cores": {
        "en": "get the weather forecast for {v}",
        "ko": "{v} 날씨 예보를 알려줘",
        "es": "obtén el pronóstico del tiempo para {v}",
        "ja": "{v}の天気予報を調べて",
        "de": "hole die Wettervorhersage für {v}",
        "mixed": "{v} weather forecast를 보여줘"
      }
    },
    {
      "route": "materials.search",
      "values": [
        "silicon",
        "LiFePO4",
        "GaN",
        "diamond",
        "graphene",
        "Al2O3",
        "SiC",
        "TiO2",
        "perovskite",
        "copper"
      ],
      "cores": {
        "en": "find the band gap or material properties of {v}",
        "ko": "{v}의 밴드갭이나 물성을 찾아줘",
        "es": "busca la banda prohibida o propiedades de {v}",
        "ja": "{v}のバンドギャップや物性を探して",
        "de": "suche Bandlücke oder Materialeigenschaften von {v}",
        "mixed": "{v} band gap이나 material property를 찾아줘"
      }
    },
    {
      "route": "materials.structure",
      "values": [
        "silicon",
        "LiFePO4",
        "GaN",
        "diamond",
        "graphene",
        "Al2O3",
        "SiC",
        "TiO2",
        "perovskite",
        "copper"
      ],
      "cores": {
        "en": "retrieve the crystal structure and lattice for {v}",
        "ko": "{v}의 결정구조와 격자 정보를 가져와",
        "es": "obtén la estructura cristalina y red de {v}",
        "ja": "{v}の結晶構造と格子情報を取得して",
        "de": "hole Kristallstruktur und Gitter von {v}",
        "mixed": "{v} crystal structure와 lattice를 가져와"
      }
    },
    {
      "route": "papers.search",
      "values": [
        "retrieval augmented generation",
        "small language models",
        "battery materials",
        "agentic RAG",
        "graph neural networks",
        "solid electrolytes",
        "tool routing",
        "multimodal models",
        "perovskite solar cells",
        "quantum materials"
      ],
      "cores": {
        "en": "search research papers about {v}",
        "ko": "{v} 관련 논문을 검색해줘",
        "es": "busca artículos de investigación sobre {v}",
        "ja": "{v}に関する研究論文を検索して",
        "de": "suche Forschungsarbeiten zu {v}",
        "mixed": "{v} 관련 research paper를 search해"
      }
    },
    {
      "route": "papers.citations",
      "values": [
        "10.1000/alpha",
        "10.1000/beta",
        "10.1000/gamma",
        "10.1000/delta",
        "10.1000/epsilon",
        "10.1000/zeta",
        "10.1000/eta",
        "10.1000/theta",
        "10.1000/iota",
        "10.1000/kappa"
      ],
      "cores": {
        "en": "find papers that cite {v}",
        "ko": "{v}를 인용한 논문을 찾아줘",
        "es": "encuentra artículos que citan {v}",
        "ja": "{v}を引用している論文を探して",
        "de": "finde Arbeiten, die {v} zitieren",
        "mixed": "{v}를 cite한 papers를 찾아줘"
      }
    },
    {
      "route": "finance.quote",
      "values": [
        "AAPL",
        "NVDA",
        "MSFT",
        "TSLA",
        "GOOGL",
        "AMZN",
        "META",
        "AMD",
        "INTC",
        "KO"
      ],
      "cores": {
        "en": "get the latest stock quote for {v}",
        "ko": "{v}의 현재 주가를 알려줘",
        "es": "obtén la cotización actual de {v}",
        "ja": "{v}の最新株価を取得して",
        "de": "hole den aktuellen Aktienkurs von {v}",
        "mixed": "{v} current stock quote를 알려줘"
      }
    },
    {
      "route": "finance.history",
      "values": [
        "AAPL over the last year",
        "NVDA for six months",
        "MSFT since January",
        "TSLA for 30 days",
        "GOOGL over five years",
        "AMZN this quarter",
        "META for two years",
        "AMD since 2024",
        "INTC for 90 days",
        "KO over the last decade"
      ],
      "cores": {
        "en": "retrieve historical prices for {v}",
        "ko": "{v}의 과거 주가 기록을 가져와",
        "es": "obtén precios históricos de {v}",
        "ja": "{v}の過去の株価履歴を取得して",
        "de": "hole historische Kurse für {v}",
        "mixed": "{v} historical price history를 보여줘"
      }
    },
    {
      "route": "calendar.list",
      "values": [
        "today",
        "tomorrow",
        "Friday",
        "this afternoon",
        "next Monday",
        "this week",
        "September 30",
        "the morning",
        "next weekend",
        "October 1"
      ],
      "cores": {
        "en": "list my calendar events for {v}",
        "ko": "{v} 일정 목록을 보여줘",
        "es": "muestra mis eventos del calendario para {v}",
        "ja": "{v}の予定一覧を表示して",
        "de": "zeige meine Kalendertermine für {v}",
        "mixed": "{v} calendar events를 list해"
      }
    },
    {
      "route": "calendar.create",
      "values": [
        "team sync at 3 PM",
        "dentist tomorrow at 10",
        "project review Friday at 2",
        "lunch with Alex at noon",
        "demo next Monday at 4",
        "focus time at 9 AM",
        "parent meeting Thursday at 5",
        "release review at 11",
        "design sync Tuesday at 1",
        "weekly planning Monday at 9"
      ],
      "cores": {
        "en": "create a calendar event for {v}",
        "ko": "{v} 일정을 캘린더에 만들어줘",
        "es": "crea un evento de calendario para {v}",
        "ja": "{v}の予定をカレンダーに作成して",
        "de": "erstelle einen Kalendereintrag für {v}",
        "mixed": "{v} calendar event를 create해"
      }
    },
    {
      "route": "support.search",
      "values": [
        "password reset",
        "billing FAQ",
        "login failure",
        "refund policy",
        "account verification",
        "API timeout",
        "subscription change",
        "two-factor setup",
        "data export",
        "notification settings"
      ],
      "cores": {
        "en": "search the support knowledge base for {v}",
        "ko": "{v} 관련 고객지원 문서를 검색해줘",
        "es": "busca en la base de soporte información sobre {v}",
        "ja": "{v}についてサポート記事を検索して",
        "de": "suche in der Support-Wissensbasis nach {v}",
        "mixed": "{v} 관련 support KB를 search해"
      }
    },
    {
      "route": "support.create_ticket",
      "values": [
        "login keeps failing",
        "invoice is wrong",
        "API returns 500",
        "account is locked",
        "refund has not arrived",
        "subscription was duplicated",
        "verification email missing",
        "export failed",
        "notification bug",
        "mobile app crashes"
      ],
      "cores": {
        "en": "create a support ticket because {v}",
        "ko": "{v} 문제로 고객지원 티켓을 만들어줘",
        "es": "crea un ticket de soporte porque {v}",
        "ja": "{v}の問題でサポートチケットを作成して",
        "de": "erstelle ein Support-Ticket, weil {v}",
        "mixed": "{v} 문제로 support ticket을 create해"
      }
    },
    {
      "route": "inventory.search",
      "values": [
        "SKU-101",
        "SKU-202",
        "SKU-303",
        "SKU-404",
        "SKU-505",
        "SKU-A12",
        "SKU-B24",
        "SKU-C36",
        "SKU-D48",
        "SKU-E60"
      ],
      "cores": {
        "en": "check current inventory quantity for {v}",
        "ko": "{v}의 현재 재고 수량을 확인해줘",
        "es": "consulta la cantidad actual en inventario de {v}",
        "ja": "{v}の現在庫数を確認して",
        "de": "prüfe den aktuellen Bestand von {v}",
        "mixed": "{v} current inventory quantity를 확인해"
      }
    },
    {
      "route": "inventory.update",
      "values": [
        "SKU-101 to 12",
        "SKU-202 to 4",
        "SKU-303 to 30",
        "SKU-404 to 0",
        "SKU-505 to 55",
        "SKU-A12 to 7",
        "SKU-B24 to 19",
        "SKU-C36 to 2",
        "SKU-D48 to 81",
        "SKU-E60 to 15"
      ],
      "cores": {
        "en": "update inventory quantity for {v}",
        "ko": "재고를 {v}로 업데이트해줘",
        "es": "actualiza la cantidad de inventario de {v}",
        "ja": "在庫数量を{v}に更新して",
        "de": "aktualisiere den Lagerbestand für {v}",
        "mixed": "inventory를 {v}로 update해"
      }
    },
    {
      "route": "users.lookup",
      "values": [
        "user 42",
        "alice@example.com",
        "Kevin Cho",
        "account 1007",
        "Bob Kim",
        "user 9001",
        "maria@example.com",
        "Hans Müller",
        "Yuki Sato",
        "account 73"
      ],
      "cores": {
        "en": "look up the user profile for {v}",
        "ko": "{v} 사용자 프로필을 조회해줘",
        "es": "busca el perfil de usuario de {v}",
        "ja": "{v}のユーザープロフィールを検索して",
        "de": "suche das Benutzerprofil für {v}",
        "mixed": "{v} user profile을 lookup해"
      }
    },
    {
      "route": "users.update",
      "values": [
        "user 42 name to Alice",
        "alice@example.com phone number",
        "Kevin Cho display name",
        "account 1007 department",
        "Bob Kim title",
        "user 9001 timezone",
        "maria@example.com locale",
        "Hans Müller nickname",
        "Yuki Sato department",
        "account 73 display name"
      ],
      "cores": {
        "en": "update the user profile for {v}",
        "ko": "{v} 사용자 프로필을 수정해줘",
        "es": "actualiza el perfil de usuario de {v}",
        "ja": "{v}のユーザープロフィールを更新して",
        "de": "aktualisiere das Benutzerprofil für {v}",
        "mixed": "{v} user profile을 update해"
      }
    }
  ],
  "unsupported": {
    "en": [
      "write a short poem about autumn",
      "diagnose my chest pain",
      "turn on the living room lights",
      "book a flight to Paris"
    ],
    "ko": [
      "가을에 대한 짧은 시를 써줘",
      "내 가슴 통증을 진단해줘",
      "거실 조명을 켜줘",
      "파리행 항공편을 예약해줘"
    ],
    "es": [
      "escribe un poema corto sobre el otoño",
      "diagnostica mi dolor de pecho",
      "enciende las luces del salón",
      "reserva un vuelo a París"
    ],
    "ja": [
      "秋について短い詩を書いて",
      "胸の痛みを診断して",
      "リビングの照明をつけて",
      "パリ行きの航空券を予約して"
    ],
    "de": [
      "schreibe ein kurzes Gedicht über den Herbst",
      "diagnostiziere meine Brustschmerzen",
      "schalte das Wohnzimmerlicht ein",
      "buche einen Flug nach Paris"
    ],
    "mixed": [
      "가을 poem을 써줘",
      "my chest pain을 diagnose해",
      "living room lights를 켜줘",
      "Paris flight를 book해줘"
    ]
  }
}''')

def _split(index: int) -> str:
    return "dev" if index < 6 else "calibration" if index < 8 else "test"

def _category(index: int) -> str:
    if index < 2:
        return "normal"
    if index == 2:
        return "colloquial"
    if index == 3:
        return "long_tail"
    if index == 4:
        return "near_duplicate"
    if index == 5:
        return "distractor"
    if index < 8:
        return "calibration_paraphrase"
    return "held_out_paraphrase"

def _fill(wrapper: str, core: str) -> str:
    return wrapper.replace("{core}", core)

def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    languages = CONFIG["languages"]
    wrappers = CONFIG["wrappers"]
    for route in CONFIG["routes"]:
        route_id = route["route"].replace(".", "-").replace("_", "-")
        for language_index, language in enumerate(languages):
            for index in range(10):
                values = route["values"]
                value = values[(index + language_index) % len(values)]
                core = route["cores"][language].replace("{v}", value)
                cases.append({
                    "id": f"v2-{route_id}-{language}-{index + 1:02d}",
                    "query": _fill(wrappers[language][index], core),
                    "expected": route["route"],
                    "category": _category(index),
                    "expect_abstain": False,
                    "split": _split(index),
                    "language": language,
                })
    for language in languages:
        for core_index, core in enumerate(CONFIG["unsupported"][language]):
            for index in range(10):
                cases.append({
                    "id": f"v2-no-route-{language}-{core_index + 1}-{index + 1:02d}",
                    "query": _fill(wrappers[language][index], core),
                    "expected": None,
                    "category": (
                        "adversarial_or_out_of_domain"
                        if index >= 8
                        else "out_of_domain"
                    ),
                    "expect_abstain": True,
                    "split": _split(index),
                    "language": language,
                })
    return cases

def validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 1200:
        raise ValueError(f"expected 1200 cases, got {len(cases)}")
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
    destination = Path("benchmarks/decision-routing-v2.json")
    destination.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} cases to {destination}")

if __name__ == "__main__":
    main()
