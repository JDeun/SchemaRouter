"""Generate the fresh v4 operation-routing development corpus.

This corpus is independent of the consumed 0.10 development/calibration rows.
Threshold fitting is allowed only on the tune split. The dev_holdout split is
a one-shot development confirmation split and must not be used for retuning.
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


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_v2 = _load_module(_V2, "operation_routing_v2")
_graph_dev = _load_module(_GRAPH_DEV, "operation_routing_graph_dev")
_graph_cal = _load_module(_GRAPH_CAL, "operation_routing_graph_cal")
CONFIG: dict[str, Any] = _v2.CONFIG
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
GRAPH_DEV_SEED = "graph-v1-development-2026-09-26"
GRAPH_CAL_SEED = "graph-v1-calibration-2026-09-27"

SUPPORTED_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Could you {core}?",
        "I need you to {core}.",
        "Please {core} for me.",
        "For my next step, {core}.",
        "Can you quickly {core}?",
        "Help me {core}.",
        "I'd like to {core}.",
        "Right now, {core}.",
        "When you have a moment, {core}.",
        "My current task needs this: {core}.",
    ),
    "ko": (
        "{core} 줄래?",
        "지금 {core}.",
        "부탁인데 {core}.",
        "다음 작업으로 {core}.",
        "간단히 {core}.",
        "내가 하던 일에 필요하니 {core}.",
        "{core} 줬으면 해.",
        "우선 {core}.",
        "시간 될 때 {core}.",
        "현재 작업에 필요해. {core}.",
    ),
    "es": (
        "¿Puedes {core}?",
        "Necesito que {core}.",
        "Por favor, {core}.",
        "Para mi siguiente paso, {core}.",
        "¿Podrías {core} rápidamente?",
        "Ayúdame a {core}.",
        "Quiero que {core}.",
        "Ahora mismo, {core}.",
        "Cuando puedas, {core}.",
        "Mi tarea actual necesita esto: {core}.",
    ),
    "ja": (
        "{core}くれる？",
        "今、{core}。",
        "お願いだから{core}。",
        "次の作業として{core}。",
        "手早く{core}。",
        "作業に必要なので{core}。",
        "{core}ほしい。",
        "まず{core}。",
        "時間があるときに{core}。",
        "今のタスクに必要です。{core}。",
    ),
    "de": (
        "Kannst du {core}?",
        "Ich brauche Folgendes: {core}.",
        "Bitte {core}.",
        "Als nächsten Schritt: {core}.",
        "Kannst du kurz {core}?",
        "Hilf mir dabei: {core}.",
        "Ich möchte, dass du {core}.",
        "Jetzt bitte {core}.",
        "Wenn du kannst, {core}.",
        "Für meine aktuelle Aufgabe brauche ich: {core}.",
    ),
    "mixed": (
        "{core} 해줄래?",
        "지금 {core}.",
        "please {core}.",
        "next step으로 {core}.",
        "quick하게 {core}.",
        "내 task에 필요해서 {core}.",
        "{core} 해줘.",
        "우선 {core}.",
        "when possible, {core}.",
        "current task에 필요해: {core}.",
    ),
}


def _family(
    family_id: str,
    en: str,
    ko: str,
    es: str,
    ja: str,
    de: str,
    mixed: str,
) -> dict[str, str]:
    return {
        "family_id": family_id,
        "en": en,
        "ko": ko,
        "es": es,
        "ja": ja,
        "de": de,
        "mixed": mixed,
    }


UNSUPPORTED_FAMILIES: dict[str, tuple[dict[str, str], ...]] = {
    "weather": (
        _family("sunrise-sunset","tell me tomorrow's sunrise and sunset times in Seoul","서울의 내일 일출과 일몰 시간을 알려줘","dime las horas de salida y puesta del sol de mañana en Seúl","ソウルの明日の日の出と日の入りの時刻を教えて","nenne mir für morgen Sonnenaufgang und Sonnenuntergang in Seoul","서울 tomorrow sunrise와 sunset time을 알려줘"),
        _family("pollen","show the pollen level in Seoul this afternoon","오늘 오후 서울의 꽃가루 농도를 알려줘","muestra el nivel de polen de Seúl esta tarde","今日の午後のソウルの花粉レベルを教えて","zeige heute Nachmittag die Pollenbelastung in Seoul","오늘 오후 서울 pollen level을 알려줘"),
        _family("tides","give me the next high and low tides near Busan","부산 근처의 다음 만조와 간조 시간을 알려줘","dime las próximas mareas alta y baja cerca de Busan","釜山付近の次の満潮と干潮の時刻を教えて","nenne die nächsten Hoch- und Niedrigwasserzeiten bei Busan","부산 근처 next high tide와 low tide를 알려줘"),
        _family("lightning-map","show recent lightning strikes around Seoul on a map","서울 주변의 최근 낙뢰 위치를 지도에 보여줘","muestra en un mapa los rayos recientes alrededor de Seúl","ソウル周辺の最近の落雷地点を地図で見せて","zeige aktuelle Blitzeinschläge rund um Seoul auf einer Karte","서울 주변 recent lightning strikes를 map으로 보여줘"),
        _family("satellite-clouds","show the latest satellite cloud image over Korea","한반도 상공의 최신 위성 구름 영상을 보여줘","muestra la imagen satelital más reciente de nubes sobre Corea","韓国上空の最新の衛星雲画像を見せて","zeige das neueste Satellitenbild der Bewölkung über Korea","Korea latest satellite cloud image를 보여줘"),
        _family("storm-tracks","list historical typhoon tracks that crossed Jeju","제주를 통과한 과거 태풍 경로를 보여줘","enumera trayectorias históricas de tifones que cruzaron Jeju","済州島を通過した過去の台風経路を一覧にして","liste historische Taifunbahnen auf, die Jeju überquert haben","Jeju를 지난 historical typhoon tracks를 보여줘"),
        _family("station-metadata","find the elevation and sensor model of Seoul weather station 108","서울 기상관측소 108의 고도와 센서 모델을 찾아줘","busca la elevación y el modelo de sensor de la estación meteorológica 108 de Seúl","ソウル気象観測所108の標高とセンサーモデルを調べて","finde Höhe und Sensormodell der Wetterstation Seoul 108","Seoul weather station 108의 elevation과 sensor model을 찾아줘"),
        _family("climate-projection","estimate Seoul's average summer temperature in 2050 under a climate scenario","기후 시나리오에서 2050년 서울의 여름 평균기온을 추정해줘","estima la temperatura media de verano de Seúl en 2050 bajo un escenario climático","気候シナリオ下で2050年のソウルの夏季平均気温を推定して","schätze Seouls mittlere Sommertemperatur im Jahr 2050 unter einem Klimaszenario","climate scenario 기준 2050 Seoul summer average temperature를 estimate해줘"),
    ),
    "materials": (
        _family("xrd-pattern","calculate the powder XRD pattern for silicon","실리콘의 분말 XRD 패턴을 계산해줘","calcula el patrón XRD de polvo del silicio","シリコンの粉末XRDパターンを計算して","berechne das Pulver-XRD-Muster von Silizium","silicon powder XRD pattern을 calculate해줘"),
        _family("defect-energy","compute the oxygen-vacancy formation energy in TiO2","TiO2의 산소 공공 형성 에너지를 계산해줘","calcula la energía de formación de una vacante de oxígeno en TiO2","TiO2の酸素空孔形成エネルギーを計算して","berechne die Bildungsenergie einer Sauerstoffleerstelle in TiO2","TiO2 oxygen-vacancy formation energy를 compute해줘"),
        _family("molecular-dynamics","run a molecular dynamics simulation of liquid lithium","액체 리튬의 분자동역학 시뮬레이션을 실행해줘","ejecuta una simulación de dinámica molecular de litio líquido","液体リチウムの分子動力学シミュレーションを実行して","führe eine Molekulardynamiksimulation von flüssigem Lithium aus","liquid lithium molecular dynamics simulation을 run해줘"),
        _family("hypothetical-crystal","generate a hypothetical stable crystal structure for Li3PS4","Li3PS4의 가상 안정 결정구조를 생성해줘","genera una estructura cristalina estable hipotética para Li3PS4","Li3PS4の仮想的な安定結晶構造を生成して","erzeuge eine hypothetische stabile Kristallstruktur für Li3PS4","Li3PS4 hypothetical stable crystal structure를 generate해줘"),
        _family("elastic-tensor","calculate the full elastic tensor of silicon from first principles","제일원리 계산으로 실리콘의 전체 탄성 텐서를 구해줘","calcula el tensor elástico completo del silicio desde primeros principios","第一原理からシリコンの完全な弾性テンソルを計算して","berechne den vollständigen Elastizitätstensor von Silizium aus ersten Prinzipien","first-principles로 silicon full elastic tensor를 calculate해줘"),
        _family("surface-energy","compute the surface energy of the MgO 100 facet","MgO 100 면의 표면 에너지를 계산해줘","calcula la energía superficial de la faceta 100 de MgO","MgOの100面の表面エネルギーを計算して","berechne die Oberflächenenergie der MgO-100-Facette","MgO 100 facet surface energy를 compute해줘"),
        _family("microscopy-simulation","simulate a TEM image for a silicon crystal","실리콘 결정의 TEM 이미지를 시뮬레이션해줘","simula una imagen TEM de un cristal de silicio","シリコン結晶のTEM画像をシミュレーションして","simuliere ein TEM-Bild eines Siliziumkristalls","silicon crystal TEM image를 simulate해줘"),
        _family("reaction-path","find the minimum-energy diffusion pathway for lithium in LiFePO4","LiFePO4에서 리튬의 최소 에너지 확산 경로를 찾아줘","encuentra la ruta de difusión de mínima energía del litio en LiFePO4","LiFePO4中のリチウムの最小エネルギー拡散経路を求めて","finde den Diffusionspfad minimaler Energie für Lithium in LiFePO4","LiFePO4 lithium minimum-energy diffusion pathway를 찾아줘"),
    ),
    "papers": (
        _family("author-h-index","calculate the h-index of researcher Jane Kim","연구자 Jane Kim의 h-index를 계산해줘","calcula el índice h de la investigadora Jane Kim","研究者Jane Kimのh指数を計算して","berechne den h-Index der Forscherin Jane Kim","researcher Jane Kim의 h-index를 calculate해줘"),
        _family("plagiarism-check","check this manuscript for plagiarism against published literature","이 원고가 기존 논문을 표절했는지 검사해줘","comprueba este manuscrito por plagio frente a literatura publicada","この原稿を既発表文献と照合して盗用を確認して","prüfe dieses Manuskript auf Plagiate gegenüber veröffentlichter Literatur","이 manuscript를 published literature와 plagiarism check해줘"),
        _family("journal-recommendation","recommend journals for a manuscript about solid-state batteries","전고체 배터리 원고를 투고할 학술지를 추천해줘","recomienda revistas para un manuscrito sobre baterías de estado sólido","全固体電池の原稿に合う投稿先ジャーナルを推薦して","empfiehl Zeitschriften für ein Manuskript über Festkörperbatterien","solid-state battery manuscript에 맞는 journal을 recommend해줘"),
        _family("peer-review","write a formal peer review for this manuscript","이 원고에 대한 정식 동료평가 의견을 작성해줘","redacta una revisión por pares formal de este manuscrito","この原稿の正式な査読コメントを書いて","verfasse ein formelles Peer-Review für dieses Manuskript","이 manuscript의 formal peer review를 작성해줘"),
        _family("author-contact","find the current email address of the corresponding author of DOI 10.5555/v4-a","DOI 10.5555/v4-a 교신저자의 현재 이메일 주소를 찾아줘","busca el correo actual del autor de correspondencia del DOI 10.5555/v4-a","DOI 10.5555/v4-a の責任著者の現在のメールアドレスを探して","finde die aktuelle E-Mail des korrespondierenden Autors von DOI 10.5555/v4-a","DOI 10.5555/v4-a corresponding author의 current email을 찾아줘"),
        _family("citation-visualization","build an interactive citation-network visualization for DOI 10.5555/v4-b","DOI 10.5555/v4-b의 대화형 인용 네트워크 시각화를 만들어줘","crea una visualización interactiva de la red de citas del DOI 10.5555/v4-b","DOI 10.5555/v4-b のインタラクティブな引用ネットワーク可視化を作って","erstelle eine interaktive Zitationsnetzwerk-Visualisierung für DOI 10.5555/v4-b","DOI 10.5555/v4-b interactive citation-network visualization을 만들어줘"),
        _family("fulltext-translation","translate the full text of DOI 10.5555/v4-c into Korean","DOI 10.5555/v4-c 논문 전문을 한국어로 번역해줘","traduce al coreano el texto completo del DOI 10.5555/v4-c","DOI 10.5555/v4-c の全文を韓国語に翻訳して","übersetze den Volltext von DOI 10.5555/v4-c ins Koreanische","DOI 10.5555/v4-c full text를 Korean으로 translate해줘"),
        _family("funding-extraction","extract every grant number and funder from DOI 10.5555/v4-d","DOI 10.5555/v4-d에서 모든 과제번호와 연구비 지원기관을 추출해줘","extrae todos los números de subvención y financiadores del DOI 10.5555/v4-d","DOI 10.5555/v4-d から全ての助成番号と資金提供者を抽出して","extrahiere alle Fördernummern und Geldgeber aus DOI 10.5555/v4-d","DOI 10.5555/v4-d에서 all grant numbers와 funders를 extract해줘"),
    ),
    "finance": (
        _family("portfolio-optimization","optimize a five-stock portfolio for minimum volatility","5개 종목 포트폴리오의 변동성이 최소가 되도록 최적화해줘","optimiza una cartera de cinco acciones para mínima volatilidad","5銘柄のポートフォリオを最小ボラティリティになるよう最適化して","optimiere ein Fünf-Aktien-Portfolio auf minimale Volatilität","five-stock portfolio를 minimum volatility로 optimize해줘"),
        _family("tax-lot","calculate the taxable gain for my FIFO AAPL lots","FIFO 기준 AAPL 보유분의 과세 대상 이익을 계산해줘","calcula la ganancia imponible de mis lotes AAPL usando FIFO","FIFO方式で保有しているAAPLの課税対象利益を計算して","berechne den steuerpflichtigen Gewinn meiner AAPL-Lose nach FIFO","FIFO AAPL lots의 taxable gain을 calculate해줘"),
        _family("analyst-consensus","show the current analyst rating consensus for NVDA","NVDA의 현재 애널리스트 투자의견 컨센서스를 보여줘","muestra el consenso actual de analistas para NVDA","NVDAの現在のアナリスト評価コンセンサスを表示して","zeige den aktuellen Analystenkonsens für NVDA","NVDA current analyst rating consensus를 보여줘"),
        _family("earnings-transcript","summarize the latest earnings-call transcript for MSFT","MSFT의 최신 실적발표 컨퍼런스콜 전문을 요약해줘","resume la última transcripción de resultados de MSFT","MSFTの最新決算説明会の書き起こしを要約して","fasse das neueste Earnings-Call-Transkript von MSFT zusammen","MSFT latest earnings-call transcript를 summarize해줘"),
        _family("options-chain","show the complete options chain for AAPL expiring next month","다음 달 만기 AAPL 전체 옵션 체인을 보여줘","muestra la cadena completa de opciones de AAPL que vence el próximo mes","来月満期のAAPLオプションチェーン全体を表示して","zeige die vollständige AAPL-Optionskette mit Verfall nächsten Monat","next month expiry AAPL complete options chain을 보여줘"),
        _family("yield-curve","build today's US Treasury yield curve","오늘 미국 국채 수익률 곡선을 만들어줘","construye la curva de rendimiento del Tesoro de EE. UU. de hoy","今日の米国債イールドカーブを作って","erstelle die heutige US-Treasury-Zinskurve","today US Treasury yield curve를 build해줘"),
        _family("loan-amortization","make an amortization schedule for a thirty-year mortgage","30년 주택담보대출 상환 스케줄을 만들어줘","crea un cuadro de amortización para una hipoteca a treinta años","30年住宅ローンの返済予定表を作って","erstelle einen Tilgungsplan für eine 30-jährige Hypothek","30-year mortgage amortization schedule을 만들어줘"),
        _family("value-at-risk","estimate one-day 99 percent value at risk for this portfolio","이 포트폴리오의 1일 99퍼센트 VaR를 추정해줘","estima el valor en riesgo diario al 99 por ciento de esta cartera","このポートフォリオの1日99パーセントVaRを推定して","schätze den eintägigen 99-Prozent-Value-at-Risk dieses Portfolios","이 portfolio의 one-day 99 percent VaR를 estimate해줘"),
    ),
    "calendar": (
        _family("room-booking","find and book an available conference room for Friday at 2 PM","금요일 오후 2시에 비어 있는 회의실을 찾아 예약해줘","busca y reserva una sala de reuniones disponible el viernes a las 2","金曜14時に空いている会議室を探して予約して","finde und buche am Freitag um 14 Uhr einen freien Konferenzraum","Friday 2 PM available conference room을 찾아 book해줘"),
        _family("sharing-permission","give Mina read access to my work calendar","Mina에게 내 업무 캘린더 읽기 권한을 줘","da a Mina acceso de lectura a mi calendario de trabajo","Minaに私の仕事用カレンダーの閲覧権限を付与して","gib Mina Lesezugriff auf meinen Arbeitskalender","Mina에게 work calendar read access를 줘"),
        _family("timezone-conversion","convert my 3 PM Seoul meeting time to London time","서울 오후 3시 회의 시간을 런던 시간으로 변환해줘","convierte mi reunión de las 3 PM en Seúl a la hora de Londres","ソウル15時の会議時刻をロンドン時間に変換して","rechne meinen Termin um 15 Uhr in Seoul in Londoner Zeit um","Seoul 3 PM meeting time을 London time으로 convert해줘"),
        _family("event-attachment","attach the roadmap PDF to Friday's planning event","금요일 기획 일정에 로드맵 PDF를 첨부해줘","adjunta el PDF de la hoja de ruta al evento de planificación del viernes","金曜の計画イベントにロードマップPDFを添付して","hänge die Roadmap-PDF an den Planungstermin am Freitag","Friday planning event에 roadmap PDF를 attach해줘"),
        _family("event-color","change all interview events this week to the blue calendar color","이번 주 면접 일정의 캘린더 색상을 모두 파란색으로 바꿔줘","cambia todos los eventos de entrevistas de esta semana al color azul","今週の面接イベントをすべて青色に変更して","ändere alle Bewerbungsgespräche dieser Woche auf die Kalenderfarbe Blau","this week interview events를 blue calendar color로 change해줘"),
        _family("out-of-office","set an out-of-office block for next Monday afternoon","다음 주 월요일 오후를 부재중으로 설정해줘","configura un bloque fuera de oficina para el próximo lunes por la tarde","来週月曜の午後を不在予定に設定して","setze für nächsten Montag Nachmittag einen Abwesenheitsblock","next Monday afternoon을 out-of-office block으로 set해줘"),
        _family("working-hours","change my calendar working hours to 9 AM through 5 PM","캘린더 근무 시간을 오전 9시부터 오후 5시로 바꿔줘","cambia mi horario laboral del calendario de 9 a 17","カレンダーの勤務時間を9時から17時に変更して","ändere meine Kalender-Arbeitszeit auf 9 bis 17 Uhr","calendar working hours를 9 AM to 5 PM으로 change해줘"),
        _family("calendar-duplication","duplicate my project calendar into a new calendar","내 프로젝트 캘린더를 새 캘린더로 복제해줘","duplica mi calendario de proyecto en un calendario nuevo","プロジェクトカレンダーを新しいカレンダーに複製して","dupliziere meinen Projektkalender in einen neuen Kalender","project calendar를 new calendar로 duplicate해줘"),
    ),
    "support": (
        _family("priority-change","change support ticket 8101 to urgent priority","고객지원 티켓 8101의 우선순위를 긴급으로 바꿔줘","cambia el ticket de soporte 8101 a prioridad urgente","サポートチケット8101の優先度を緊急に変更して","setze Support-Ticket 8101 auf dringende Priorität","support ticket 8101 priority를 urgent로 change해줘"),
        _family("internal-note","add an internal note to support ticket 8102","고객지원 티켓 8102에 내부 메모를 추가해줘","añade una nota interna al ticket de soporte 8102","サポートチケット8102に内部メモを追加して","füge Support-Ticket 8102 eine interne Notiz hinzu","support ticket 8102에 internal note를 add해줘"),
        _family("customer-reply","send a reply to the customer on support ticket 8103","고객지원 티켓 8103의 고객에게 답변을 보내줘","envía una respuesta al cliente del ticket de soporte 8103","サポートチケット8103の顧客に返信して","sende dem Kunden in Support-Ticket 8103 eine Antwort","support ticket 8103 customer에게 reply를 send해줘"),
        _family("reopen-ticket","reopen support ticket 8104","고객지원 티켓 8104를 다시 열어줘","vuelve a abrir el ticket de soporte 8104","サポートチケット8104を再開して","öffne Support-Ticket 8104 erneut","support ticket 8104를 reopen해줘"),
        _family("escalate-ticket","escalate support ticket 8105 to the engineering team","고객지원 티켓 8105를 엔지니어링 팀으로 에스컬레이션해줘","escala el ticket de soporte 8105 al equipo de ingeniería","サポートチケット8105をエンジニアリングチームにエスカレーションして","eskaliere Support-Ticket 8105 an das Engineering-Team","support ticket 8105를 engineering team으로 escalate해줘"),
        _family("sla-prediction","predict whether support ticket 8106 will breach its SLA","고객지원 티켓 8106이 SLA를 위반할지 예측해줘","predice si el ticket de soporte 8106 incumplirá su SLA","サポートチケット8106がSLA違反になるか予測して","sage voraus ob Support-Ticket 8106 seine SLA verletzt","support ticket 8106이 SLA breach할지 predict해줘"),
        _family("ticket-export","export this month's support tickets as a CSV report","이번 달 고객지원 티켓을 CSV 보고서로 내보내줘","exporta los tickets de soporte de este mes como informe CSV","今月のサポートチケットをCSVレポートとして出力して","exportiere die Support-Tickets dieses Monats als CSV-Bericht","this month support tickets를 CSV report로 export해줘"),
        _family("sentiment-analysis","analyze customer sentiment across open support tickets","열려 있는 고객지원 티켓의 고객 감정을 분석해줘","analiza el sentimiento de clientes en los tickets de soporte abiertos","未解決サポートチケット全体の顧客感情を分析して","analysiere die Kundenstimmung in offenen Support-Tickets","open support tickets의 customer sentiment를 analyze해줘"),
    ),
    "inventory": (
        _family("inventory-valuation","calculate the FIFO inventory valuation for warehouse A","A창고의 FIFO 재고 평가액을 계산해줘","calcula la valoración FIFO del inventario del almacén A","倉庫AのFIFO在庫評価額を計算して","berechne die FIFO-Bestandsbewertung für Lager A","warehouse A FIFO inventory valuation을 calculate해줘"),
        _family("demand-forecast","forecast next month's demand for SKU-901","SKU-901의 다음 달 수요를 예측해줘","pronostica la demanda del próximo mes para SKU-901","SKU-901の来月の需要を予測して","prognostiziere die Nachfrage für SKU-901 im nächsten Monat","SKU-901 next-month demand를 forecast해줘"),
        _family("cycle-count","reconcile the cycle count for SKU-902 against the ledger","SKU-902의 순환 실사 수량과 장부 수량을 대조해줘","concilia el conteo cíclico de SKU-902 con el registro","SKU-902の循環棚卸数と台帳を照合して","gleiche die Zykluszählung von SKU-902 mit dem Bestandbuch ab","SKU-902 cycle count를 ledger와 reconcile해줘"),
        _family("create-sku","create a new SKU-903 product record","새 SKU-903 상품 레코드를 만들어줘","crea un nuevo registro de producto SKU-903","新しいSKU-903の商品レコードを作成して","erstelle einen neuen Produktdatensatz für SKU-903","new SKU-903 product record를 create해줘"),
        _family("barcode-generation","generate a printable barcode label for SKU-904","SKU-904용 인쇄 가능한 바코드 라벨을 생성해줘","genera una etiqueta de código de barras imprimible para SKU-904","SKU-904用の印刷可能なバーコードラベルを生成して","erzeuge ein druckbares Barcode-Etikett für SKU-904","SKU-904 printable barcode label을 generate해줘"),
        _family("lot-expiry","list lots of SKU-905 that expire within thirty days","30일 이내 만료되는 SKU-905 로트를 보여줘","lista los lotes de SKU-905 que vencen en treinta días","30日以内に期限切れになるSKU-905のロットを一覧にして","liste Chargen von SKU-905 auf, die innerhalb von 30 Tagen ablaufen","30 days 안에 expire하는 SKU-905 lots를 list해줘"),
        _family("supplier-lead-time","estimate the supplier lead time for SKU-906","SKU-906의 공급업체 리드타임을 추정해줘","estima el plazo de entrega del proveedor para SKU-906","SKU-906の仕入先リードタイムを推定して","schätze die Lieferzeit des Lieferanten für SKU-906","SKU-906 supplier lead time을 estimate해줘"),
        _family("backorder-allocation","allocate incoming SKU-907 units across backorders","입고되는 SKU-907 수량을 미출고 주문에 배분해줘","asigna las unidades entrantes de SKU-907 entre pedidos pendientes","入荷するSKU-907をバックオーダーに割り当てて","verteile eingehende SKU-907-Einheiten auf Rückstände","incoming SKU-907 units를 backorders에 allocate해줘"),
    ),
    "users": (
        _family("role-assignment","assign the editor role to user 901","사용자 901에게 편집자 역할을 부여해줘","asigna el rol de editor al usuario 901","ユーザー901に編集者ロールを割り当てて","weise Benutzer 901 die Editor-Rolle zu","user 901에게 editor role을 assign해줘"),
        _family("group-membership","add user 902 to the research group","사용자 902를 연구 그룹에 추가해줘","añade al usuario 902 al grupo de investigación","ユーザー902を研究グループに追加して","füge Benutzer 902 der Forschungsgruppe hinzu","user 902를 research group에 add해줘"),
        _family("list-sessions","list all active login sessions for user 903","사용자 903의 활성 로그인 세션을 모두 보여줘","lista todas las sesiones activas del usuario 903","ユーザー903のアクティブなログインセッションを一覧にして","liste alle aktiven Anmeldesitzungen von Benutzer 903 auf","user 903 active login sessions를 list해줘"),
        _family("revoke-session","revoke every active session for user 904","사용자 904의 모든 활성 세션을 해제해줘","revoca todas las sesiones activas del usuario 904","ユーザー904の全アクティブセッションを無効化して","widerrufe alle aktiven Sitzungen von Benutzer 904","user 904의 all active sessions를 revoke해줘"),
        _family("invite-user","invite mina@example.com to the workspace","mina@example.com을 워크스페이스에 초대해줘","invita a mina@example.com al espacio de trabajo","mina@example.com をワークスペースに招待して","lade mina@example.com in den Workspace ein","mina@example.com을 workspace에 invite해줘"),
        _family("email-verification","mark user 905's email address as verified","사용자 905의 이메일 주소를 인증된 상태로 바꿔줘","marca como verificado el correo del usuario 905","ユーザー905のメールアドレスを確認済みにして","markiere die E-Mail-Adresse von Benutzer 905 als verifiziert","user 905 email address를 verified로 mark해줘"),
        _family("data-export","export all personal data for user 906","사용자 906의 개인 데이터를 모두 내보내줘","exporta todos los datos personales del usuario 906","ユーザー906の個人データをすべてエクスポートして","exportiere alle personenbezogenen Daten von Benutzer 906","user 906의 all personal data를 export해줘"),
        _family("suspend-account","suspend user 907's account for seven days","사용자 907의 계정을 7일 동안 정지해줘","suspende la cuenta del usuario 907 durante siete días","ユーザー907のアカウントを7日間停止して","sperre das Konto von Benutzer 907 für sieben Tage","user 907 account를 seven days 동안 suspend해줘"),
    ),
}

OOD_BASE: dict[str, tuple[str, ...]] = {
    "en": ("give me a sourdough starter recipe","write a limerick about a lighthouse","explain the Sicilian Defense in chess","prove there are infinitely many prime numbers","suggest a beginner swimming workout","make a packing list for a weekend hike","translate hello into Icelandic","tell me how to prune a rose bush","recommend three courtroom dramas","explain how a transistor works","help me fix a dripping kitchen faucet","suggest a bedtime story for a six-year-old","name the brightest stars visible from Earth","give me a five-minute breathing exercise","show me how to sketch a human hand","explain why leaves change color in autumn"),
    "ko": ("사워도우 스타터 레시피를 알려줘","등대를 소재로 리머릭 시를 써줘","체스의 시실리안 디펜스를 설명해줘","소수가 무한히 많다는 것을 증명해줘","초보자 수영 운동 루틴을 추천해줘","주말 하이킹 짐 목록을 만들어줘","hello를 아이슬란드어로 번역해줘","장미 가지치기 방법을 알려줘","법정 드라마 영화 세 편을 추천해줘","트랜지스터가 어떻게 작동하는지 설명해줘","주방 수도꼭지 누수를 고치는 방법을 알려줘","여섯 살 아이를 위한 잠자리 이야기를 추천해줘","지구에서 보이는 가장 밝은 별들을 알려줘","5분 호흡 운동을 알려줘","사람 손을 스케치하는 방법을 알려줘","가을에 잎 색이 변하는 이유를 설명해줘"),
    "es": ("dame una receta de masa madre","escribe un limerick sobre un faro","explica la Defensa Siciliana en ajedrez","demuestra que existen infinitos números primos","sugiere un entrenamiento de natación para principiantes","haz una lista para una caminata de fin de semana","traduce hello al islandés","dime cómo podar un rosal","recomienda tres dramas judiciales","explica cómo funciona un transistor","ayúdame a arreglar un grifo de cocina que gotea","sugiere un cuento para dormir para un niño de seis años","nombra las estrellas más brillantes visibles desde la Tierra","dame un ejercicio de respiración de cinco minutos","enséñame a dibujar una mano humana","explica por qué las hojas cambian de color en otoño"),
    "ja": ("サワードウ種のレシピを教えて","灯台についてのリメリックを書いて","チェスのシシリアンディフェンスを説明して","素数が無限に存在することを証明して","初心者向けの水泳トレーニングを提案して","週末ハイキングの持ち物リストを作って","helloをアイスランド語に翻訳して","バラの剪定方法を教えて","法廷ドラマ映画を3本すすめて","トランジスタの仕組みを説明して","台所の蛇口の水漏れの直し方を教えて","6歳向けの寝る前のお話を提案して","地球から見える最も明るい星を教えて","5分間の呼吸エクササイズを教えて","人の手をスケッチする方法を教えて","秋に葉の色が変わる理由を説明して"),
    "de": ("gib mir ein Rezept für Sauerteigstarter","schreibe einen Limerick über einen Leuchtturm","erkläre die Sizilianische Verteidigung im Schach","beweise dass es unendlich viele Primzahlen gibt","schlage ein Schwimmtraining für Anfänger vor","erstelle eine Packliste für eine Wochenendwanderung","übersetze hello ins Isländische","erkläre wie man einen Rosenstrauch schneidet","empfiehl drei Gerichtsdramen","erkläre wie ein Transistor funktioniert","hilf mir einen tropfenden Küchenhahn zu reparieren","schlage eine Gute-Nacht-Geschichte für ein sechsjähriges Kind vor","nenne die hellsten Sterne die von der Erde sichtbar sind","gib mir eine fünfminütige Atemübung","zeige mir wie man eine menschliche Hand skizziert","erkläre warum Blätter im Herbst ihre Farbe ändern"),
    "mixed": ("sourdough starter recipe를 알려줘","lighthouse에 대한 limerick을 써줘","chess Sicilian Defense를 설명해줘","infinitely many primes임을 prove해줘","beginner swimming workout을 추천해줘","weekend hike packing list를 만들어줘","hello를 Icelandic으로 translate해줘","rose bush pruning 방법을 알려줘","courtroom drama 세 편을 recommend해줘","transistor가 어떻게 works하는지 설명해줘","dripping kitchen faucet을 fix하는 법을 알려줘","six-year-old bedtime story를 추천해줘","Earth에서 visible한 brightest stars를 알려줘","five-minute breathing exercise를 알려줘","human hand sketch 방법을 알려줘","autumn에 leaves color가 변하는 이유를 설명해줘"),
}

LABEL_REVEALING_CUES = (
    "unsupported","not supported","reject","schema","endpoint","capability graph",
    "미지원","거절","스키마","엔드포인트","no soportad","rechaza","esquema",
    "未対応","拒否","スキーマ","エンドポイント","nicht unterstützt","lehne",
)


def _normalize(query: str) -> str:
    return re.sub(r"[^\w]+", "", query.casefold())


def _route_map() -> dict[str, dict[str, Any]]:
    return {str(route["route"]): route for route in CONFIG["routes"]}


def _prior_normalized_queries() -> set[str]:
    seen = set(_graph_dev._prior_normalized_queries())
    seen.update(
        _normalize(str(case["query"]))
        for case in _graph_dev._build(GRAPH_DEV_SEED)
    )
    seen.update(
        _normalize(str(case["query"]))
        for case in _graph_cal._build(GRAPH_CAL_SEED)
    )
    return seen


def _build(seed: str) -> list[dict[str, object]]:
    rng = random.Random(seed)
    routes = _route_map()
    route_names = [name for pair in _graph_dev.ROUTE_PAIRS for name in pair]
    cases: list[dict[str, object]] = []

    for route_index, route_name in enumerate(route_names):
        route = routes[route_name]
        values = list(route["values"])
        if not values:
            raise ValueError(f"route {route_name} has no value variants")
        route_id = route_name.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            wrappers = SUPPORTED_WRAPPERS[language]
            if len(wrappers) != 10:
                raise ValueError(f"supported wrapper count mismatch: {language}")
            for family_index, wrapper in enumerate(wrappers):
                value = values[(route_index + family_index) % len(values)]
                core = str(route["cores"][language]).replace("{v}", value)
                split = "tune" if family_index < 6 else "dev_holdout"
                cases.append(
                    {
                        "id": f"v4-supported-{route_id}-{language}-{family_index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": "v4_supported_natural",
                        "expect_abstain": False,
                        "split": split,
                        "language": language,
                        "family_id": f"supported-style-{family_index + 1:02d}",
                    }
                )

    for domain, families in UNSUPPORTED_FAMILIES.items():
        if len(families) != 8:
            raise ValueError(f"unsupported family count mismatch: {domain}")
        for family_index, family in enumerate(families):
            split = "tune" if family_index < 4 else "dev_holdout"
            family_id = str(family["family_id"])
            for language in LANGUAGES:
                cases.append(
                    {
                        "id": f"v4-near-{domain}-{family_id}-{language}",
                        "query": family[language],
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "expect_abstain": True,
                        "split": split,
                        "language": language,
                        "family_id": f"{domain}:{family_id}",
                    }
                )

    for language in LANGUAGES:
        if len(OOD_BASE[language]) != 16:
            raise ValueError(f"OOD family count mismatch: {language}")
        for index, query in enumerate(OOD_BASE[language]):
            split = "tune" if index < 8 else "dev_holdout"
            cases.append(
                {
                    "id": f"v4-ood-{language}-{index + 1:02d}",
                    "query": query,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": split,
                    "language": language,
                    "family_id": f"ood-{index + 1:02d}",
                }
            )

    rng.shuffle(cases)
    return cases


def _validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 1440:
        raise ValueError(f"expected 1440 v4 development cases, got {len(cases)}")
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate v4 development case IDs")
    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized v4 development query")
    overlap = set(normalized).intersection(_prior_normalized_queries())
    if overlap:
        raise ValueError(
            "v4 development exact normalized overlap with consumed/prior corpora: "
            f"{len(overlap)}"
        )

    supported = [case for case in cases if case["expected"] is not None]
    near = [
        case for case in cases
        if case["category"] == "near_domain_unsupported_operation"
    ]
    ood = [case for case in cases if case["category"] == "out_of_domain"]
    if len(supported) != 960 or len(near) != 384 or len(ood) != 96:
        raise ValueError("v4 development class-shape mismatch")

    expected_split = {
        "tune": {"supported": 576, "near": 192, "ood": 48, "total": 816},
        "dev_holdout": {"supported": 384, "near": 192, "ood": 48, "total": 624},
    }
    for split, expected in expected_split.items():
        rows = [case for case in cases if case["split"] == split]
        actual = {
            "supported": sum(case["expected"] is not None for case in rows),
            "near": sum(
                case["category"] == "near_domain_unsupported_operation"
                for case in rows
            ),
            "ood": sum(case["category"] == "out_of_domain" for case in rows),
            "total": len(rows),
        }
        if actual != expected:
            raise ValueError(f"v4 development split mismatch for {split}: {actual!r}")

    for language in LANGUAGES:
        if sum(case["language"] == language for case in cases) != 240:
            raise ValueError(f"v4 language balance mismatch: {language}")

    route_counts: dict[str, int] = {}
    for case in supported:
        route = str(case["expected"])
        route_counts[route] = route_counts.get(route, 0) + 1
    if len(route_counts) != 16 or set(route_counts.values()) != {60}:
        raise ValueError("v4 supported-route balance mismatch")

    near_family_split: dict[str, set[str]] = {"tune": set(), "dev_holdout": set()}
    for case in near:
        near_family_split[str(case["split"])].add(str(case["family_id"]))
    if near_family_split["tune"] & near_family_split["dev_holdout"]:
        raise ValueError("near-domain semantic family leaked across dev splits")
    if len(near_family_split["tune"]) != 32:
        raise ValueError("expected 32 tune unsupported semantic families")
    if len(near_family_split["dev_holdout"]) != 32:
        raise ValueError("expected 32 holdout unsupported semantic families")

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
        "role": "fresh_development",
        "tuning_eligible_split": "tune",
        "one_shot_holdout_split": "dev_holdout",
        "seed": args.seed,
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "case_count": 1440,
        "supported_cases": 960,
        "near_domain_unsupported_cases": 384,
        "out_of_domain_cases": 96,
        "languages": {language: 240 for language in LANGUAGES},
        "supported_routes": 16,
        "supported_cases_per_route": 60,
        "unsupported_domains": 8,
        "unsupported_families_per_domain": 8,
        "tune": {
            "cases": 816,
            "supported": 576,
            "near_domain_unsupported": 192,
            "out_of_domain": 48,
        },
        "dev_holdout": {
            "cases": 624,
            "supported": 384,
            "near_domain_unsupported": 192,
            "out_of_domain": 48,
        },
        "normalized_exact_overlap_with_prior_consumed_corpora": 0,
        "label_revealing_routing_cues": 0,
        "threshold_retuning_from_dev_holdout_forbidden": True,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"case_count": len(cases), "corpus_sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
