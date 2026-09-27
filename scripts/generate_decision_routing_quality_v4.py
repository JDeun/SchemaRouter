# ruff: noqa: E501 -- multilingual corpus fixtures are intentionally kept verbatim.\n"""Generate fresh natural development data for operation-routing quality v4.

This corpus is tuning-eligible for v4 only.  All predecessor calibration/blind
corpora remain forbidden for tuning and are used here only for overlap guards.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
from pathlib import Path
from typing import Any

_V2 = Path(__file__).with_name("generate_decision_routing_v2.py")
_GRAPH_DEV = Path(__file__).with_name("generate_decision_routing_graph_v1.py")
_GRAPH_CAL = Path(__file__).with_name(
    "generate_decision_routing_graph_calibration_v1.py"
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_v2 = _load(_V2, "routing_v2_for_quality_v4")
_graph_dev = _load(_GRAPH_DEV, "graph_dev_for_quality_v4")
_graph_cal = _load(_GRAPH_CAL, "graph_cal_for_quality_v4")

CONFIG: dict[str, Any] = _v2.CONFIG
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
PREDECESSOR_DEV_SEED = "graph-v1-development-2026-09-26"
PREDECESSOR_CAL_SEED = "graph-v1-calibration-2026-09-27"

SUPPORTED_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "{core}.",
        "Could you {core}?",
        "I need you to {core}.",
        "For this task, {core}.",
        "Please {core} and give me the result.",
        "Can you quickly {core}?",
    ),
    "ko": (
        "{core}.",
        "{core} 줄래?",
        "지금 {core}.",
        "이 작업에서는 {core}.",
        "부탁인데 {core}.",
        "빠르게 {core}.",
    ),
    "es": (
        "{core}.",
        "¿Puedes {core}?",
        "Necesito que {core}.",
        "Para esta tarea, {core}.",
        "Por favor, {core}.",
        "Hazlo rápido: {core}.",
    ),
    "ja": (
        "{core}。",
        "{core}くれる？",
        "今、{core}。",
        "この作業では{core}。",
        "お願い、{core}。",
        "手早く{core}。",
    ),
    "de": (
        "{core}.",
        "Kannst du {core}?",
        "Ich brauche Folgendes: {core}.",
        "Für diese Aufgabe: {core}.",
        "Bitte {core}.",
        "Mach kurz Folgendes: {core}.",
    ),
    "mixed": (
        "{core}.",
        "지금 {core} 가능해?",
        "이 task에서 {core}.",
        "next step으로 {core}.",
        "please {core}.",
        "빠르게 {core}.",
    ),
}

SUPPORTED_VARIANTS: dict[str, dict[str, tuple[str, str]]] = {
    "weather.current": {
        "en": ("tell me what the weather is like right now in {v}", "show current conditions for {v}"),
        "ko": ("{v} 지금 날씨가 어떤지 알려줘", "{v} 현재 기상 상태를 보여줘"),
        "es": ("dime cómo está el tiempo ahora mismo en {v}", "muestra las condiciones actuales de {v}"),
        "ja": ("{v}の今の天気を教えて", "{v}の現在の気象状況を見せて"),
        "de": ("sag mir wie das Wetter gerade in {v} ist", "zeige die aktuellen Bedingungen für {v}"),
        "mixed": ("{v} 지금 weather가 어떤지 알려줘", "{v} current conditions 보여줘"),
    },
    "weather.forecast": {
        "en": ("tell me what weather to expect for {v}", "show the forecast for {v}"),
        "ko": ("{v} 날씨가 어떻게 될지 알려줘", "{v} 예보를 보여줘"),
        "es": ("dime qué tiempo se espera para {v}", "muestra el pronóstico para {v}"),
        "ja": ("{v}の天気がどうなるか教えて", "{v}の予報を見せて"),
        "de": ("sag mir welches Wetter für {v} erwartet wird", "zeige die Vorhersage für {v}"),
        "mixed": ("{v} 날씨가 어떻게 될지 tell me", "{v} forecast 보여줘"),
    },
    "materials.search": {
        "en": ("look up physical properties for {v}", "find material-property data on {v}"),
        "ko": ("{v}의 물성 데이터를 조회해줘", "{v} 재료 특성 정보를 찾아줘"),
        "es": ("consulta propiedades físicas de {v}", "busca datos de propiedades del material {v}"),
        "ja": ("{v}の物性データを調べて", "{v}の材料特性情報を探して"),
        "de": ("schlage physikalische Eigenschaften von {v} nach", "finde Materialeigenschaftsdaten zu {v}"),
        "mixed": ("{v} physical property 데이터를 lookup해줘", "{v} material-property data를 찾아줘"),
    },
    "materials.structure": {
        "en": ("show the crystal structure details for {v}", "retrieve lattice and structure data for {v}"),
        "ko": ("{v}의 결정 구조 상세 정보를 보여줘", "{v}의 격자와 구조 데이터를 가져와"),
        "es": ("muestra los detalles de la estructura cristalina de {v}", "recupera datos de red y estructura de {v}"),
        "ja": ("{v}の結晶構造の詳細を見せて", "{v}の格子と構造データを取得して"),
        "de": ("zeige Details der Kristallstruktur von {v}", "hole Gitter- und Strukturdaten für {v}"),
        "mixed": ("{v} crystal structure details 보여줘", "{v} lattice와 structure data 가져와"),
    },
    "papers.search": {
        "en": ("find academic literature on {v}", "look for research articles about {v}"),
        "ko": ("{v}에 관한 학술 문헌을 찾아줘", "{v} 주제의 연구 논문을 찾아줘"),
        "es": ("encuentra literatura académica sobre {v}", "busca artículos de investigación acerca de {v}"),
        "ja": ("{v}に関する学術文献を探して", "{v}についての研究記事を探して"),
        "de": ("finde wissenschaftliche Literatur zu {v}", "suche Forschungsartikel über {v}"),
        "mixed": ("{v} academic literature 찾아줘", "{v} research articles 찾아줘"),
    },
    "papers.citations": {
        "en": ("show publications that reference {v}", "find the citing papers for {v}"),
        "ko": ("{v}를 참고문헌으로 인용한 출판물을 보여줘", "{v}의 인용 논문을 찾아줘"),
        "es": ("muestra publicaciones que referencian {v}", "encuentra los artículos que citan {v}"),
        "ja": ("{v}を参照している出版物を見せて", "{v}の被引用論文を探して"),
        "de": ("zeige Veröffentlichungen die {v} referenzieren", "finde zitierende Arbeiten für {v}"),
        "mixed": ("{v}를 reference한 publications 보여줘", "{v} citing papers 찾아줘"),
    },
    "finance.quote": {
        "en": ("show the current market price for {v}", "what is {v} trading at now"),
        "ko": ("{v}의 현재 시장 가격을 보여줘", "{v}가 지금 얼마에 거래되는지 알려줘"),
        "es": ("muestra el precio de mercado actual de {v}", "a qué precio cotiza {v} ahora"),
        "ja": ("{v}の現在の市場価格を見せて", "{v}が今いくらで取引されているか教えて"),
        "de": ("zeige den aktuellen Marktpreis von {v}", "zu welchem Kurs wird {v} gerade gehandelt"),
        "mixed": ("{v} current market price 보여줘", "{v}가 지금 얼마에 trading 되는지 알려줘"),
    },
    "finance.history": {
        "en": ("show historical price data for {v}", "retrieve the past market series for {v}"),
        "ko": ("{v}의 과거 가격 데이터를 보여줘", "{v}의 이전 시장 시계열을 가져와"),
        "es": ("muestra datos históricos de precio para {v}", "recupera la serie histórica de mercado de {v}"),
        "ja": ("{v}の過去の価格データを見せて", "{v}の過去の市場系列を取得して"),
        "de": ("zeige historische Kursdaten für {v}", "hole die frühere Marktzeitreihe für {v}"),
        "mixed": ("{v} historical price data 보여줘", "{v} past market series 가져와"),
    },
    "calendar.list_events": {
        "en": ("show the events on my calendar for {v}", "list my scheduled items for {v}"),
        "ko": ("{v}의 내 캘린더 일정을 보여줘", "{v}에 잡힌 일정을 목록으로 보여줘"),
        "es": ("muestra los eventos de mi calendario para {v}", "enumera mis citas programadas para {v}"),
        "ja": ("{v}のカレンダー予定を見せて", "{v}に入っている予定を一覧にして"),
        "de": ("zeige meine Kalendereinträge für {v}", "liste meine geplanten Termine für {v}"),
        "mixed": ("{v} calendar events 보여줘", "{v} scheduled items list해줘"),
    },
    "calendar.create_event": {
        "en": ("put {v} on my calendar", "add a calendar event for {v}"),
        "ko": ("{v} 일정을 내 캘린더에 넣어줘", "{v} 캘린더 이벤트를 추가해줘"),
        "es": ("añade {v} a mi calendario", "crea un evento de calendario para {v}"),
        "ja": ("{v}をカレンダーに入れて", "{v}のカレンダーイベントを追加して"),
        "de": ("trage {v} in meinen Kalender ein", "füge einen Kalendereintrag für {v} hinzu"),
        "mixed": ("{v}를 calendar에 넣어줘", "{v} calendar event 추가해줘"),
    },
    "support.search_kb": {
        "en": ("find help documentation for {v}", "search the support knowledge base for {v}"),
        "ko": ("{v} 관련 도움말 문서를 찾아줘", "{v}를 고객지원 지식베이스에서 검색해줘"),
        "es": ("encuentra documentación de ayuda para {v}", "busca {v} en la base de conocimiento de soporte"),
        "ja": ("{v}のヘルプ文書を探して", "{v}をサポート知識ベースで検索して"),
        "de": ("finde Hilfedokumentation zu {v}", "suche in der Support-Wissensdatenbank nach {v}"),
        "mixed": ("{v} help documentation 찾아줘", "{v}를 support knowledge base에서 search해줘"),
    },
    "support.create_ticket": {
        "en": ("open a support case because {v}", "file a help request about {v}"),
        "ko": ("{v} 때문에 고객지원 문의를 열어줘", "{v} 문제로 도움 요청을 접수해줘"),
        "es": ("abre un caso de soporte porque {v}", "registra una solicitud de ayuda sobre {v}"),
        "ja": ("{v}の件でサポート案件を作って", "{v}についてヘルプ依頼を登録して"),
        "de": ("eröffne einen Support-Fall weil {v}", "reiche eine Hilfeanfrage zu {v} ein"),
        "mixed": ("{v} 때문에 support case 열어줘", "{v} 관련 help request 접수해줘"),
    },
    "inventory.search": {
        "en": ("tell me how many units are on hand for {v}", "look up stock availability for {v}"),
        "ko": ("{v}가 몇 개 남아 있는지 알려줘", "{v} 재고 보유량을 조회해줘"),
        "es": ("dime cuántas unidades hay disponibles de {v}", "consulta la disponibilidad de stock de {v}"),
        "ja": ("{v}が在庫に何個あるか教えて", "{v}の在庫状況を調べて"),
        "de": ("sag mir wie viele Einheiten von {v} verfügbar sind", "prüfe die Lagerverfügbarkeit von {v}"),
        "mixed": ("{v}가 몇 units 남았는지 알려줘", "{v} stock availability 조회해줘"),
    },
    "inventory.update": {
        "en": ("set the on-hand inventory to {v}", "change the stock count to {v}"),
        "ko": ("보유 재고 수량을 {v}로 맞춰줘", "재고 카운트를 {v}로 변경해줘"),
        "es": ("establece el inventario disponible en {v}", "cambia el conteo de stock a {v}"),
        "ja": ("手持ち在庫数を{v}に設定して", "在庫カウントを{v}に変更して"),
        "de": ("setze den verfügbaren Bestand auf {v}", "ändere den Lagerbestand auf {v}"),
        "mixed": ("on-hand inventory를 {v}로 맞춰줘", "stock count를 {v}로 change해줘"),
    },
    "users.lookup": {
        "en": ("show me the account profile for {v}", "find the user record for {v}"),
        "ko": ("{v}의 계정 프로필을 보여줘", "{v} 사용자 레코드를 찾아줘"),
        "es": ("muestra el perfil de cuenta de {v}", "encuentra el registro de usuario de {v}"),
        "ja": ("{v}のアカウントプロフィールを見せて", "{v}のユーザーレコードを探して"),
        "de": ("zeige das Kontoprofil für {v}", "finde den Benutzerdatensatz für {v}"),
        "mixed": ("{v} account profile 보여줘", "{v} user record 찾아줘"),
    },
    "users.update": {
        "en": ("change the profile details for {v}", "edit the user record for {v}"),
        "ko": ("{v}의 프로필 정보를 변경해줘", "{v} 사용자 레코드를 수정해줘"),
        "es": ("cambia los datos del perfil de {v}", "edita el registro de usuario de {v}"),
        "ja": ("{v}のプロフィール情報を変更して", "{v}のユーザーレコードを編集して"),
        "de": ("ändere die Profildaten für {v}", "bearbeite den Benutzerdatensatz für {v}"),
        "mixed": ("{v} profile details 변경해줘", "{v} user record edit해줘"),
    },
}

NEAR_DOMAIN_FAMILIES: dict[str, tuple[dict[str, Any], ...]] = {
    "weather": (
        {
            "values": ("Seoul", "Busan", "Tokyo"),
            "templates": {
                "en": "show a satellite cloud image over {v}",
                "ko": "{v} 상공의 위성 구름 영상을 보여줘",
                "es": "muestra una imagen satelital de nubes sobre {v}",
                "ja": "{v}上空の衛星雲画像を見せて",
                "de": "zeige ein Satelliten-Wolkenbild über {v}",
                "mixed": "{v} 위 satellite cloud image 보여줘",
            },
        },
        {
            "values": ("RKSI", "RJTT", "EDDF"),
            "templates": {
                "en": "retrieve the latest METAR and TAF for {v}",
                "ko": "{v}의 최신 METAR와 TAF를 가져와",
                "es": "recupera el METAR y TAF más recientes de {v}",
                "ja": "{v}の最新METARとTAFを取得して",
                "de": "hole den neuesten METAR und TAF für {v}",
                "mixed": "{v} latest METAR와 TAF 가져와",
            },
        },
        {
            "values": ("Seoul", "Madrid", "Hamburg"),
            "templates": {
                "en": "display a live lightning-strike map around {v}",
                "ko": "{v} 주변의 실시간 낙뢰 지도를 보여줘",
                "es": "muestra un mapa en vivo de rayos alrededor de {v}",
                "ja": "{v}周辺のリアルタイム落雷マップを表示して",
                "de": "zeige eine Live-Blitzkarte rund um {v}",
                "mixed": "{v} 주변 live lightning map 보여줘",
            },
        },
        {
            "values": ("Seoul", "Paris", "New York"),
            "templates": {
                "en": "give me the pollen allergy outlook for {v}",
                "ko": "{v}의 꽃가루 알레르기 전망을 알려줘",
                "es": "dame la previsión de polen y alergias para {v}",
                "ja": "{v}の花粉アレルギー予測を教えて",
                "de": "gib mir die Pollen- und Allergieprognose für {v}",
                "mixed": "{v} pollen allergy outlook 알려줘",
            },
        },
    ),
    "materials": (
        {
            "values": ("silicon", "LiFePO4", "GaN"),
            "templates": {
                "en": "simulate an XRD pattern for {v}",
                "ko": "{v}의 XRD 패턴을 시뮬레이션해줘",
                "es": "simula un patrón XRD para {v}",
                "ja": "{v}のXRDパターンをシミュレーションして",
                "de": "simuliere ein XRD-Muster für {v}",
                "mixed": "{v} XRD pattern을 simulate해줘",
            },
        },
        {
            "values": ("silicon vacancy", "oxygen vacancy in TiO2", "Ga vacancy in GaN"),
            "templates": {
                "en": "calculate the defect formation energy for {v}",
                "ko": "{v}의 결함 형성 에너지를 계산해줘",
                "es": "calcula la energía de formación del defecto para {v}",
                "ja": "{v}の欠陥形成エネルギーを計算して",
                "de": "berechne die Defektbildungsenergie für {v}",
                "mixed": "{v} defect formation energy 계산해줘",
            },
        },
        {
            "values": ("LiFePO4", "perovskite oxide", "graphene oxide"),
            "templates": {
                "en": "design a laboratory synthesis recipe for {v}",
                "ko": "{v}의 실험실 합성 레시피를 설계해줘",
                "es": "diseña una receta de síntesis de laboratorio para {v}",
                "ja": "{v}の実験室合成レシピを設計して",
                "de": "entwirf ein Laborsynthese-Rezept für {v}",
                "mixed": "{v} lab synthesis recipe 설계해줘",
            },
        },
        {
            "values": ("liquid water", "silicon", "LiFePO4"),
            "templates": {
                "en": "run a molecular dynamics simulation for {v}",
                "ko": "{v}에 대한 분자동역학 시뮬레이션을 실행해줘",
                "es": "ejecuta una simulación de dinámica molecular para {v}",
                "ja": "{v}の分子動力学シミュレーションを実行して",
                "de": "führe eine Molekulardynamik-Simulation für {v} aus",
                "mixed": "{v} molecular dynamics simulation 실행해줘",
            },
        },
    ),
    "papers": (
        {
            "values": ("10.2000/a1", "10.2000/a2", "10.2000/a3"),
            "templates": {
                "en": "translate the full paper at {v} into Korean",
                "ko": "{v} 논문 전문을 한국어로 번역해줘",
                "es": "traduce al coreano el artículo completo de {v}",
                "ja": "{v}の論文全文を韓国語に翻訳して",
                "de": "übersetze den vollständigen Artikel {v} ins Koreanische",
                "mixed": "{v} full paper를 Korean으로 translate해줘",
            },
        },
        {
            "values": ("10.2000/b1", "10.2000/b2", "10.2000/b3"),
            "templates": {
                "en": "build a citation-network visualization for {v}",
                "ko": "{v}의 인용 네트워크 시각화를 만들어줘",
                "es": "crea una visualización de red de citas para {v}",
                "ja": "{v}の引用ネットワーク可視化を作って",
                "de": "erstelle eine Zitationsnetzwerk-Visualisierung für {v}",
                "mixed": "{v} citation-network visualization 만들어줘",
            },
        },
        {
            "values": ("10.2000/c1", "10.2000/c2", "10.2000/c3"),
            "templates": {
                "en": "check the manuscript at {v} for plagiarism",
                "ko": "{v} 원고의 표절 여부를 검사해줘",
                "es": "comprueba si el manuscrito de {v} tiene plagio",
                "ja": "{v}の原稿を盗用チェックして",
                "de": "prüfe das Manuskript {v} auf Plagiate",
                "mixed": "{v} manuscript plagiarism check해줘",
            },
        },
        {
            "values": ("10.2000/d1", "10.2000/d2", "10.2000/d3"),
            "templates": {
                "en": "send the corresponding author of {v} an email",
                "ko": "{v}의 교신저자에게 이메일을 보내줘",
                "es": "envía un correo al autor de correspondencia de {v}",
                "ja": "{v}の責任著者にメールを送って",
                "de": "sende dem korrespondierenden Autor von {v} eine E-Mail",
                "mixed": "{v} corresponding author에게 email 보내줘",
            },
        },
    ),
    "finance": (
        {
            "values": ("AAPL", "NVDA", "MSFT"),
            "templates": {
                "en": "sell five shares of {v} at market",
                "ko": "{v} 주식 5주를 시장가로 매도해줘",
                "es": "vende cinco acciones de {v} a mercado",
                "ja": "{v}株を成行で5株売って",
                "de": "verkaufe fünf Aktien von {v} zum Marktpreis",
                "mixed": "{v} 5 shares를 market으로 sell해줘",
            },
        },
        {
            "values": ("portfolio A", "portfolio B", "retirement account"),
            "templates": {
                "en": "rebalance {v} to sixty-forty stocks and bonds",
                "ko": "{v}를 주식 60 채권 40으로 리밸런싱해줘",
                "es": "rebalancea {v} a sesenta-cuarenta entre acciones y bonos",
                "ja": "{v}を株式60債券40にリバランスして",
                "de": "balanciere {v} auf sechzig-vierzig Aktien und Anleihen um",
                "mixed": "{v}를 60/40 stocks-bonds로 rebalance해줘",
            },
        },
        {
            "values": ("AAPL", "NVDA", "TSLA"),
            "templates": {
                "en": "show the live option chain for {v}",
                "ko": "{v}의 실시간 옵션 체인을 보여줘",
                "es": "muestra la cadena de opciones en vivo de {v}",
                "ja": "{v}のライブオプションチェーンを見せて",
                "de": "zeige die Live-Optionskette für {v}",
                "mixed": "{v} live option chain 보여줘",
            },
        },
        {
            "values": ("2025", "2026", "last tax year"),
            "templates": {
                "en": "prepare my capital-gains tax report for {v}",
                "ko": "{v}의 양도소득세 보고서를 준비해줘",
                "es": "prepara mi informe fiscal de ganancias de capital para {v}",
                "ja": "{v}のキャピタルゲイン税レポートを作成して",
                "de": "erstelle meinen Kapitalertragsteuerbericht für {v}",
                "mixed": "{v} capital-gains tax report 준비해줘",
            },
        },
    ),
    "calendar": (
        {
            "values": ("Monday planning", "Friday review", "design sync"),
            "templates": {
                "en": "decline the invitation for {v}",
                "ko": "{v} 초대를 거절해줘",
                "es": "rechaza la invitación de {v}",
                "ja": "{v}の招待を辞退して",
                "de": "lehne die Einladung für {v} ab",
                "mixed": "{v} invitation decline해줘",
            },
        },
        {
            "values": ("Monday planning", "dentist appointment", "Friday review"),
            "templates": {
                "en": "set a reminder thirty minutes before {v}",
                "ko": "{v} 30분 전에 알림을 설정해줘",
                "es": "pon un recordatorio treinta minutos antes de {v}",
                "ja": "{v}の30分前にリマインダーを設定して",
                "de": "setze eine Erinnerung dreißig Minuten vor {v}",
                "mixed": "{v} 30 minutes before reminder 설정해줘",
            },
        },
        {
            "values": ("project calendar", "family calendar", "team calendar"),
            "templates": {
                "en": "share my {v} with Mina",
                "ko": "내 {v}를 Mina와 공유해줘",
                "es": "comparte mi {v} con Mina",
                "ja": "私の{v}をMinaと共有して",
                "de": "teile meinen {v} mit Mina",
                "mixed": "내 {v}를 Mina와 share해줘",
            },
        },
        {
            "values": ("room 301", "conference room A", "focus room 2"),
            "templates": {
                "en": "book {v} for tomorrow afternoon",
                "ko": "{v}를 내일 오후에 예약해줘",
                "es": "reserva {v} para mañana por la tarde",
                "ja": "{v}を明日の午後に予約して",
                "de": "buche {v} für morgen Nachmittag",
                "mixed": "{v}를 tomorrow afternoon에 book해줘",
            },
        },
    ),
    "support": (
        {
            "values": ("ticket 8101", "ticket 8102", "ticket 8103"),
            "templates": {
                "en": "reopen {v}",
                "ko": "{v}을 다시 열어줘",
                "es": "reabre {v}",
                "ja": "{v}を再開して",
                "de": "öffne {v} erneut",
                "mixed": "{v} reopen해줘",
            },
        },
        {
            "values": ("ticket 8201", "ticket 8202", "ticket 8203"),
            "templates": {
                "en": "set {v} to urgent priority",
                "ko": "{v}의 우선순위를 긴급으로 바꿔줘",
                "es": "establece {v} con prioridad urgente",
                "ja": "{v}の優先度を緊急に設定して",
                "de": "setze {v} auf dringende Priorität",
                "mixed": "{v} priority를 urgent로 바꿔줘",
            },
        },
        {
            "values": ("ticket 8301", "ticket 8302", "ticket 8303"),
            "templates": {
                "en": "delete {v} permanently",
                "ko": "{v}을 영구 삭제해줘",
                "es": "elimina {v} de forma permanente",
                "ja": "{v}を完全に削除して",
                "de": "lösche {v} dauerhaft",
                "mixed": "{v} permanently delete해줘",
            },
        },
        {
            "values": ("ticket 8401", "ticket 8402", "ticket 8403"),
            "templates": {
                "en": "escalate {v} to tier-two support",
                "ko": "{v}을 2차 지원팀으로 에스컬레이션해줘",
                "es": "escala {v} al soporte de nivel dos",
                "ja": "{v}を二次サポートへエスカレーションして",
                "de": "eskaliere {v} an den Support der zweiten Stufe",
                "mixed": "{v}를 tier-two support로 escalate해줘",
            },
        },
    ),
    "inventory": (
        {
            "values": ("SKU-711", "SKU-722", "SKU-733"),
            "templates": {
                "en": "print a warehouse barcode label for {v}",
                "ko": "{v}의 창고 바코드 라벨을 출력해줘",
                "es": "imprime una etiqueta de código de barras de almacén para {v}",
                "ja": "{v}の倉庫バーコードラベルを印刷して",
                "de": "drucke ein Lager-Barcodeetikett für {v}",
                "mixed": "{v} warehouse barcode label print해줘",
            },
        },
        {
            "values": ("SKU-744", "SKU-755", "SKU-766"),
            "templates": {
                "en": "change the retail price of {v} to 19.99",
                "ko": "{v}의 판매 가격을 19.99로 바꿔줘",
                "es": "cambia el precio minorista de {v} a 19.99",
                "ja": "{v}の販売価格を19.99に変更して",
                "de": "ändere den Verkaufspreis von {v} auf 19.99",
                "mixed": "{v} retail price를 19.99로 change해줘",
            },
        },
        {
            "values": ("SKU-777", "SKU-788", "SKU-799"),
            "templates": {
                "en": "create a new catalog item for {v}",
                "ko": "{v}의 새 카탈로그 상품을 만들어줘",
                "es": "crea un nuevo artículo de catálogo para {v}",
                "ja": "{v}の新しいカタログ商品を作成して",
                "de": "erstelle einen neuen Katalogartikel für {v}",
                "mixed": "{v} new catalog item create해줘",
            },
        },
        {
            "values": ("warehouse A", "warehouse B", "all warehouses"),
            "templates": {
                "en": "export the full inventory list for {v} as CSV",
                "ko": "{v}의 전체 재고 목록을 CSV로 내보내줘",
                "es": "exporta como CSV la lista completa de inventario de {v}",
                "ja": "{v}の全在庫一覧をCSVで出力して",
                "de": "exportiere die vollständige Bestandsliste für {v} als CSV",
                "mixed": "{v} full inventory list를 CSV로 export해줘",
            },
        },
    ),
    "users": (
        {
            "values": ("user 501", "user 502", "user 503"),
            "templates": {
                "en": "assign the administrator role to {v}",
                "ko": "{v}에게 관리자 역할을 부여해줘",
                "es": "asigna el rol de administrador a {v}",
                "ja": "{v}に管理者ロールを付与して",
                "de": "weise {v} die Administratorrolle zu",
                "mixed": "{v}에게 administrator role assign해줘",
            },
        },
        {
            "values": ("user 511", "user 512", "user 513"),
            "templates": {
                "en": "suspend the account for {v}",
                "ko": "{v}의 계정을 정지해줘",
                "es": "suspende la cuenta de {v}",
                "ja": "{v}のアカウントを停止して",
                "de": "sperre das Konto von {v}",
                "mixed": "{v} account suspend해줘",
            },
        },
        {
            "values": ("user 521", "user 522", "user 523"),
            "templates": {
                "en": "mark the email address of {v} as verified",
                "ko": "{v}의 이메일 주소를 인증 완료로 표시해줘",
                "es": "marca como verificado el correo de {v}",
                "ja": "{v}のメールアドレスを認証済みにして",
                "de": "markiere die E-Mail-Adresse von {v} als verifiziert",
                "mixed": "{v} email address를 verified로 mark해줘",
            },
        },
        {
            "values": ("user 531", "user 532", "user 533"),
            "templates": {
                "en": "list all active login sessions for {v}",
                "ko": "{v}의 활성 로그인 세션을 모두 보여줘",
                "es": "enumera todas las sesiones de inicio activas de {v}",
                "ja": "{v}のアクティブなログインセッションを全部表示して",
                "de": "liste alle aktiven Anmeldesitzungen für {v}",
                "mixed": "{v} active login sessions 전부 list해줘",
            },
        },
    ),
}

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "write a haiku about a winter train",
        "give me a recipe for mushroom risotto",
        "explain why the sky looks blue",
        "plan a three-day museum trip in Rome",
        "translate good morning into Icelandic",
        "suggest a beginner strength workout",
        "fix a squeaky wooden door",
        "teach me the Sicilian Defense in chess",
        "compare espresso and pour-over coffee",
        "write a bedtime story about a fox",
        "explain the derivative of sine",
        "suggest vegetables for a balcony garden",
    ),
    "ko": (
        "겨울 기차를 주제로 하이쿠를 써줘",
        "버섯 리조또 레시피를 알려줘",
        "하늘이 파랗게 보이는 이유를 설명해줘",
        "로마 박물관 3일 여행 일정을 짜줘",
        "좋은 아침을 아이슬란드어로 번역해줘",
        "초보자 근력 운동을 추천해줘",
        "삐걱거리는 나무문 고치는 법을 알려줘",
        "체스 시실리안 디펜스를 가르쳐줘",
        "에스프레소와 핸드드립 커피를 비교해줘",
        "여우가 나오는 잠자리 이야기를 써줘",
        "사인의 미분을 설명해줘",
        "베란다 텃밭에 심을 채소를 추천해줘",
    ),
    "es": (
        "escribe un haiku sobre un tren de invierno",
        "dame una receta de risotto de setas",
        "explica por qué el cielo se ve azul",
        "planea un viaje de tres días por museos de Roma",
        "traduce buenos días al islandés",
        "sugiere un entrenamiento de fuerza para principiantes",
        "explica cómo arreglar una puerta de madera que chirría",
        "enséñame la defensa siciliana en ajedrez",
        "compara espresso y café filtrado",
        "escribe un cuento para dormir sobre un zorro",
        "explica la derivada del seno",
        "sugiere verduras para un huerto de balcón",
    ),
    "ja": (
        "冬の列車について俳句を書いて",
        "きのこリゾットのレシピを教えて",
        "空が青く見える理由を説明して",
        "ローマの美術館を巡る3日旅行を計画して",
        "おはようをアイスランド語に訳して",
        "初心者向け筋力トレーニングを提案して",
        "きしむ木のドアの直し方を教えて",
        "チェスのシシリアン・ディフェンスを教えて",
        "エスプレッソとハンドドリップを比較して",
        "キツネの寝る前のお話を書いて",
        "サインの微分を説明して",
        "ベランダ菜園向けの野菜を提案して",
    ),
    "de": (
        "schreibe ein Haiku über einen Winterzug",
        "gib mir ein Rezept für Pilzrisotto",
        "erkläre warum der Himmel blau aussieht",
        "plane eine dreitägige Museumstour in Rom",
        "übersetze guten Morgen ins Isländische",
        "schlage ein Krafttraining für Anfänger vor",
        "erkläre wie man eine quietschende Holztür repariert",
        "bring mir die Sizilianische Verteidigung im Schach bei",
        "vergleiche Espresso und Filterkaffee",
        "schreibe eine Gute-Nacht-Geschichte über einen Fuchs",
        "erkläre die Ableitung des Sinus",
        "empfiehl Gemüse für einen Balkongarten",
    ),
    "mixed": (
        "winter train 주제로 haiku 써줘",
        "mushroom risotto recipe 알려줘",
        "sky가 blue로 보이는 이유 설명해줘",
        "Rome museum 3-day trip 계획 짜줘",
        "good morning을 Icelandic으로 translate해줘",
        "beginner strength workout 추천해줘",
        "squeaky wooden door 고치는 법 알려줘",
        "chess Sicilian Defense 가르쳐줘",
        "espresso와 pour-over coffee 비교해줘",
        "fox bedtime story 써줘",
        "sine derivative 설명해줘",
        "balcony garden vegetables 추천해줘",
    ),
}

LABEL_REVEALING_CUES = (
    "unsupported",
    "not supported",
    "reject",
    "schema",
    "endpoint",
    "capability graph",
    "미지원",
    "거절",
    "스키마",
    "엔드포인트",
    "no soportad",
    "esquema",
    "未対応",
    "拒否",
    "スキーマ",
    "エンドポイント",
    "nicht unterstützt",
)


def _normalize(query: str) -> str:
    return re.sub(r"[^\w]+", "", query.casefold())


def _route_map() -> dict[str, dict[str, Any]]:
    return {str(route["route"]): route for route in CONFIG["routes"]}


def _prior_normalized_queries() -> set[str]:
    seen = set(_graph_dev._prior_normalized_queries())
    seen.update(
        _normalize(str(case["query"]))
        for case in _graph_dev._build(PREDECESSOR_DEV_SEED)
    )
    seen.update(
        _normalize(str(case["query"]))
        for case in _graph_cal._build(PREDECESSOR_CAL_SEED)
    )
    return seen


def _build(seed: str) -> list[dict[str, object]]:
    rng = random.Random(seed)
    routes = _route_map()
    cases: list[dict[str, object]] = []

    for route_name in SUPPORTED_VARIANTS:
        route = routes[route_name]
        values = list(route["values"])
        for language in LANGUAGES:
            variants = SUPPORTED_VARIANTS[route_name][language]
            wrappers = SUPPORTED_WRAPPERS[language]
            pairings = [
                (variant, wrapper)
                for variant in variants
                for wrapper in wrappers
            ]
            rng.shuffle(pairings)
            language_values = values * 2
            rng.shuffle(language_values)
            route_id = route_name.replace(".", "-").replace("_", "-")
            for index, ((variant, wrapper), value) in enumerate(
                zip(pairings, language_values[:12], strict=True)
            ):
                core = variant.replace("{v}", value)
                cases.append(
                    {
                        "id": f"v4-dev-{route_id}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": "v4_supported_natural",
                        "expect_abstain": False,
                        "split": "development",
                        "language": language,
                    }
                )

    for domain, families in NEAR_DOMAIN_FAMILIES.items():
        for language in LANGUAGES:
            case_index = 0
            for family_index, family in enumerate(families):
                template = str(family["templates"][language])
                for value in family["values"]:
                    case_index += 1
                    cases.append(
                        {
                            "id": (
                                f"v4-dev-near-{domain}-{language}-"
                                f"{family_index + 1:02d}-{case_index:02d}"
                            ),
                            "query": template.replace("{v}", str(value)),
                            "expected": None,
                            "category": "near_domain_unsupported_operation",
                            "expect_abstain": True,
                            "split": "development",
                            "language": language,
                            "unsupported_family": (
                                f"{domain}.family_{family_index + 1}"
                            ),
                        }
                    )

    for language in LANGUAGES:
        for index, query in enumerate(OOD[language]):
            cases.append(
                {
                    "id": f"v4-dev-ood-{language}-{index + 1:02d}",
                    "query": query,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": "development",
                    "language": language,
                }
            )

    rng.shuffle(cases)
    return cases


def _validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 1800:
        raise ValueError(f"expected 1800 v4 development cases, got {len(cases)}")

    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate v4 development case IDs")

    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized v4 development query")

    overlap = _prior_normalized_queries().intersection(normalized)
    if overlap:
        raise ValueError(
            "v4 development normalized exact-query overlap with consumed corpora: "
            f"{len(overlap)}"
        )

    supported = [case for case in cases if case["expected"] is not None]
    near = [
        case
        for case in cases
        if case["category"] == "near_domain_unsupported_operation"
    ]
    ood = [case for case in cases if case["category"] == "out_of_domain"]
    if len(supported) != 1152 or len(near) != 576 or len(ood) != 72:
        raise ValueError("v4 development class counts do not match preregistration")

    for language in LANGUAGES:
        language_cases = [case for case in cases if case["language"] == language]
        if len(language_cases) != 300:
            raise ValueError(f"v4 language balance mismatch: {language}")

    route_counts: dict[str, int] = {}
    for case in supported:
        route = str(case["expected"])
        route_counts[route] = route_counts.get(route, 0) + 1
    if len(route_counts) != 16 or set(route_counts.values()) != {72}:
        raise ValueError("v4 supported-route balance mismatch")

    family_counts: dict[str, int] = {}
    for case in near:
        family = str(case["unsupported_family"])
        family_counts[family] = family_counts.get(family, 0) + 1
    if len(family_counts) != 32 or set(family_counts.values()) != {18}:
        raise ValueError("v4 unsupported-family balance mismatch")

    leaks = [
        str(case["query"])
        for case in cases
        if any(cue in str(case["query"]).casefold() for cue in LABEL_REVEALING_CUES)
    ]
    if leaks:
        raise ValueError(
            f"v4 development contains label-revealing routing cues: {len(leaks)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    cases = _build(args.seed)
    _validate(cases)
    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    manifest = {
        "cycle": "0.11-operation-routing-quality-v4",
        "role": "fresh_tuning_eligible_development",
        "seed": args.seed,
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "case_count": 1800,
        "supported_operation_cases": 1152,
        "near_domain_unsupported_operation_cases": 576,
        "out_of_domain_cases": 72,
        "languages": {language: 300 for language in LANGUAGES},
        "supported_route_count": 16,
        "cases_per_supported_route": 72,
        "unsupported_family_count": 32,
        "cases_per_unsupported_family": 18,
        "normalized_exact_overlap_with_consumed_corpora": 0,
        "label_revealing_routing_cues": 0,
        "tuning_eligible": True,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": 1800,
                "corpus_sha256": digest,
                "tuning_eligible": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
