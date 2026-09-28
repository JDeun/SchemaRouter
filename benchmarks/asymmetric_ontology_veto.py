# ruff: noqa: E501
"""Asymmetric ontology veto for experiment #358.

The raw frozen BGE-M3 route is the sole positive selector. Generic ontology evidence may only
abstain; it can never select, rerank, or switch to another endpoint.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

BGE_MODEL = "BAAI/bge-m3"
BGE_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
AUX_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
AUX_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45

NON_TOOL_LEAVES = {"compose", "explain", "calculate", "chat"}

_ACTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "read": (
        "search",
        "find",
        "look up",
        "lookup",
        "retrieve",
        "get",
        "show",
        "list",
        "browse",
        "검색",
        "찾아",
        "찾아줘",
        "조회",
        "보여",
        "목록",
        "불러",
        "가져",
        "buscar",
        "busca",
        "encontrar",
        "encuentra",
        "obtener",
        "muestra",
        "mostrar",
        "lista",
        "検索",
        "探して",
        "取得",
        "表示",
        "一覧",
        "suche",
        "suchen",
        "finde",
        "finden",
        "hole",
        "zeige",
        "anzeigen",
        "liste",
        "auflisten",
    ),
    "create": (
        "create",
        "add",
        "register",
        "schedule",
        "make a new",
        "새로 만들어",
        "만들어",
        "생성",
        "추가",
        "등록",
        "예약",
        "crear",
        "crea",
        "agregar",
        "añadir",
        "registrar",
        "programar",
        "作成",
        "追加",
        "登録",
        "予約",
        "erstellen",
        "erstelle",
        "hinzufügen",
        "registrieren",
        "planen",
    ),
    "update": (
        "update",
        "edit",
        "change",
        "modify",
        "rename",
        "set",
        "수정",
        "변경",
        "바꿔",
        "업데이트",
        "설정",
        "이름을",
        "actualizar",
        "actualiza",
        "cambiar",
        "cambia",
        "editar",
        "modificar",
        "renombrar",
        "更新",
        "変更",
        "編集",
        "設定",
        "名前を",
        "aktualisieren",
        "aktualisiere",
        "ändern",
        "ändere",
        "bearbeiten",
        "umbenennen",
    ),
    "delete": (
        "delete",
        "remove",
        "purge",
        "erase",
        "permanently remove",
        "삭제",
        "제거",
        "지워",
        "eliminar",
        "elimina",
        "borrar",
        "borra",
        "削除",
        "消して",
        "löschen",
        "lösche",
        "entfernen",
        "entferne",
    ),
    "cancel": (
        "cancel",
        "revoke",
        "abort",
        "취소",
        "철회",
        "cancelar",
        "cancela",
        "revocar",
        "キャンセル",
        "取消",
        "stornieren",
        "storniere",
        "abbrechen",
    ),
    "refund": (
        "refund",
        "reimburse",
        "환불",
        "reembolso",
        "reembolsar",
        "返金",
        "erstatten",
        "rückerstatten",
    ),
    "send": (
        "send",
        "dispatch",
        "deliver",
        "보내",
        "전송",
        "envía",
        "enviar",
        "送って",
        "送信",
        "sende",
        "senden",
    ),
    "share": (
        "share",
        "공유",
        "comparte",
        "compartir",
        "共有",
        "teile",
        "teilen",
    ),
    "export": (
        "export",
        "download",
        "내보내",
        "다운로드",
        "exporta",
        "exportar",
        "descargar",
        "エクスポート",
        "ダウンロード",
        "exportiere",
        "exportieren",
        "herunterladen",
    ),
    "translate": (
        "translate",
        "translated",
        "translation",
        "번역",
        "traduce",
        "traducir",
        "翻訳",
        "übersetze",
        "übersetzen",
    ),
    "summarize": (
        "summarize",
        "summary of",
        "요약",
        "resume",
        "resumir",
        "要約",
        "fasse",
        "zusammenfassen",
    ),
    "compare": (
        "compare",
        "contrast",
        "diff",
        "비교",
        "compara",
        "comparar",
        "比較",
        "vergleiche",
        "vergleichen",
    ),
    "merge": (
        "merge",
        "combine",
        "병합",
        "합쳐",
        "fusionar",
        "combinar",
        "統合",
        "結合",
        "zusammenführen",
        "kombinieren",
    ),
    "restart": (
        "restart",
        "reboot",
        "재시작",
        "재부팅",
        "reiniciar",
        "再起動",
        "neustarten",
    ),
    "execute": (
        "execute",
        "run",
        "trigger",
        "invoke",
        "실행",
        "ejecuta",
        "ejecutar",
        "実行",
        "ausführen",
        "starte",
    ),
    "forecast": (
        "forecast",
        "predict",
        "prediction",
        "예측",
        "전망",
        "pronostica",
        "predecir",
        "予測",
        "prognostiziere",
        "vorhersagen",
    ),
    "compose": (
        "write a poem",
        "write a story",
        "compose a poem",
        "compose music",
        "시를 써",
        "이야기를 써",
        "작곡",
        "escribe un poema",
        "escribe una historia",
        "compón",
        "詩を書いて",
        "物語を書いて",
        "作曲",
        "schreibe ein gedicht",
        "schreibe eine geschichte",
        "komponiere",
    ),
    "explain": (
        "explain",
        "why is",
        "why does",
        "설명",
        "왜 ",
        "explica",
        "por qué",
        "説明",
        "なぜ",
        "erkläre",
        "warum",
    ),
    "calculate": (
        "calculate",
        "compute",
        "square root",
        "계산",
        "제곱근",
        "calcula",
        "raíz cuadrada",
        "計算",
        "平方根",
        "berechne",
        "quadratwurzel",
    ),
    "chat": (
        "tell me a joke",
        "joke",
        "농담",
        "cuéntame un chiste",
        "chiste",
        "冗談",
        "erzähl mir einen witz",
        "witz",
    ),
}

LEAF_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "search": (
        "find one or more unknown matching items by criteria; not fetch one already identified item",
        "조건에 맞는 미지의 항목을 검색한다; 이미 식별된 하나를 가져오는 것이 아니다",
        "buscar elementos desconocidos que coincidan con criterios; no recuperar uno ya identificado",
        "条件で未知の項目を検索する。既に特定された一件を取得する操作ではない",
        "unbekannte passende Elemente nach Kriterien suchen; nicht ein bereits identifiziertes Element abrufen",
        "criteria로 unknown items를 search; known id 하나 retrieve 아님",
    ),
    "retrieve": (
        "fetch one already identified existing item or its details; not search a collection",
        "이미 식별된 기존 항목 하나나 상세정보를 가져온다; 컬렉션 검색이 아니다",
        "recuperar un elemento existente ya identificado; no buscar en una colección",
        "既に特定された既存項目一件を取得する。コレクション検索ではない",
        "ein bereits identifiziertes vorhandenes Element abrufen; keine Sammlung durchsuchen",
        "known existing item 하나를 retrieve; collection search 아님",
    ),
    "list": (
        "enumerate a collection of existing items without search criteria or a known item id",
        "검색조건이나 특정 ID 없이 기존 항목 컬렉션을 목록으로 열거한다",
        "enumerar una colección de elementos existentes sin criterios de búsqueda ni id conocido",
        "検索条件や既知IDなしで既存項目の集合を一覧表示する",
        "eine Sammlung vorhandener Elemente ohne Suchkriterien oder bekannte ID auflisten",
        "criteria 없이 collection을 list",
    ),
    "create": (
        "create or register a brand-new resource; not modify an existing one",
        "새 리소스를 생성하거나 등록한다; 기존 항목 수정이 아니다",
        "crear o registrar un recurso nuevo; no modificar uno existente",
        "新しいリソースを作成または登録する。既存項目の変更ではない",
        "eine neue Ressource erstellen oder registrieren; keine bestehende ändern",
        "brand-new resource create; existing update 아님",
    ),
    "update": (
        "change fields or settings of an existing resource while keeping the resource",
        "기존 리소스를 유지하면서 필드나 설정을 변경한다",
        "cambiar campos o ajustes de un recurso existente manteniéndolo",
        "既存リソースを残したまま項目や設定を変更する",
        "Felder oder Einstellungen einer bestehenden Ressource ändern und sie beibehalten",
        "existing resource 유지하며 fields settings update",
    ),
    "delete": (
        "permanently remove an existing resource; not cancel its process or refund money",
        "기존 리소스를 영구 삭제한다; 프로세스 취소나 환불이 아니다",
        "eliminar permanentemente un recurso existente; no cancelar un proceso ni reembolsar",
        "既存リソースを永久削除する。処理の取消や返金ではない",
        "eine bestehende Ressource dauerhaft löschen; nicht Prozess stornieren oder Geld erstatten",
        "existing resource permanently delete; cancel/refund 아님",
    ),
    "cancel": (
        "stop, revoke, or abort an active request, booking, order, subscription, or process without deleting the underlying record",
        "활성 요청, 예약, 주문, 구독, 프로세스를 중단하거나 취소한다; 기록 삭제가 아니다",
        "cancelar o detener una solicitud, reserva, pedido, suscripción o proceso activo sin borrar su registro",
        "進行中の依頼、予約、注文、購読、処理を中止する。記録削除ではない",
        "eine aktive Anfrage, Buchung, Bestellung, ein Abo oder einen Prozess stornieren ohne Datensatz zu löschen",
        "active process를 cancel; record delete 아님",
    ),
    "refund": (
        "return money for a payment, invoice, or completed order; not delete or cancel the record",
        "결제, 청구서, 완료 주문의 돈을 돌려준다; 기록 삭제나 단순 취소가 아니다",
        "devolver dinero por un pago, factura o pedido completado; no borrar ni cancelar el registro",
        "支払い、請求書、完了注文の金銭を返す。記録の削除や単なる取消ではない",
        "Geld für Zahlung, Rechnung oder abgeschlossene Bestellung zurückgeben; Datensatz nicht löschen",
        "payment money를 refund; record delete/cancel 아님",
    ),
    "send": (
        "transmit or deliver an item or message to a destination; not merely grant shared access",
        "항목이나 메시지를 목적지로 전송하거나 전달한다; 단순 접근권 공유가 아니다",
        "enviar o entregar un elemento o mensaje a un destino; no solo conceder acceso compartido",
        "項目やメッセージを宛先へ送信する。共有アクセス付与だけではない",
        "ein Element oder eine Nachricht an ein Ziel senden; nicht nur gemeinsamen Zugriff gewähren",
        "item/message를 destination에 send; access share만 하는 것 아님",
    ),
    "share": (
        "grant another person access to an existing resource; not transmit a separate delivered copy",
        "다른 사람에게 기존 리소스 접근권을 공유한다; 별도 사본 전송이 아니다",
        "conceder a otra persona acceso a un recurso existente; no enviar una copia separada",
        "他者に既存リソースへのアクセスを共有する。別コピーの送信ではない",
        "einer anderen Person Zugriff auf eine bestehende Ressource geben; keine separate Kopie senden",
        "existing resource access를 share; separate copy send 아님",
    ),
    "export": (
        "produce or download an external file representation of existing data; not translate or summarize it",
        "기존 데이터를 외부 파일로 내보내거나 다운로드한다; 번역이나 요약이 아니다",
        "producir o descargar un archivo externo de datos existentes; no traducir ni resumir",
        "既存データを外部ファイルとして出力またはダウンロードする。翻訳や要約ではない",
        "bestehende Daten als externe Datei exportieren oder herunterladen; nicht übersetzen oder zusammenfassen",
        "existing data를 file로 export/download; translate/summarize 아님",
    ),
    "translate": (
        "convert content from one human language to another while preserving meaning",
        "의미를 유지하면서 콘텐츠를 다른 사람 언어로 번역한다",
        "convertir contenido de un idioma humano a otro conservando el significado",
        "意味を保ちながら内容を別の人間言語へ翻訳する",
        "Inhalt unter Erhalt der Bedeutung in eine andere menschliche Sprache übersetzen",
        "content language를 translate; meaning preserve",
    ),
    "summarize": (
        "condense content into a shorter representation of its main points",
        "콘텐츠의 핵심을 더 짧게 요약한다",
        "condensar contenido en una versión más corta de sus puntos principales",
        "内容の要点をより短い形に要約する",
        "Inhalt auf eine kürzere Darstellung der Hauptpunkte verdichten",
        "content main points를 shorter summary로",
    ),
    "compare": (
        "compare multiple items and identify similarities or differences without merging them",
        "여러 항목의 공통점이나 차이점을 비교한다; 하나로 병합하지 않는다",
        "comparar varios elementos e identificar similitudes o diferencias sin fusionarlos",
        "複数項目を比較し共通点や違いを調べる。統合はしない",
        "mehrere Elemente vergleichen und Gemeinsamkeiten oder Unterschiede finden ohne sie zusammenzuführen",
        "multiple items differences compare; merge 아님",
    ),
    "merge": (
        "combine multiple resources into one resulting resource; not just compare them",
        "여러 리소스를 하나의 결과 리소스로 병합한다; 단순 비교가 아니다",
        "combinar varios recursos en uno resultante; no solo compararlos",
        "複数リソースを一つの結果へ統合する。比較だけではない",
        "mehrere Ressourcen zu einer resultierenden Ressource zusammenführen; nicht nur vergleichen",
        "multiple resources를 one result로 merge; compare 아님",
    ),
    "restart": (
        "restart or reboot an already running machine, service, deployment, or job",
        "실행 중인 장비, 서비스, 배포, 작업을 재시작하거나 재부팅한다",
        "reiniciar una máquina, servicio, despliegue o trabajo ya existente",
        "既存の機器、サービス、デプロイ、ジョブを再起動する",
        "eine vorhandene Maschine, einen Dienst, ein Deployment oder einen Job neu starten",
        "existing machine/service/job을 restart",
    ),
    "execute": (
        "run, invoke, trigger, or launch an executable workflow or operation; not reboot an existing runtime",
        "실행 가능한 워크플로나 작업을 호출하거나 시작한다; 기존 런타임 재부팅이 아니다",
        "ejecutar, invocar o lanzar un flujo u operación; no reiniciar un runtime existente",
        "実行可能なワークフローや操作を起動する。既存ランタイムの再起動ではない",
        "einen ausführbaren Workflow oder eine Operation starten; keinen bestehenden Laufzeitprozess neu starten",
        "workflow/operation을 execute; runtime restart 아님",
    ),
    "forecast": (
        "predict a future value, arrival, state, trend, or outcome from present or historical information",
        "현재나 과거 정보로 미래 값, 도착, 상태, 추세, 결과를 예측한다",
        "predecir un valor, llegada, estado, tendencia o resultado futuro usando información actual o histórica",
        "現在または過去情報から将来の値、到着、状態、傾向、結果を予測する",
        "einen zukünftigen Wert, eine Ankunft, einen Zustand, Trend oder Ausgang aus aktuellen oder historischen Daten vorhersagen",
        "present/historical info로 future value/state forecast",
    ),
    "compose": (
        "create new artistic or creative writing, poetry, story, lyrics, or music",
        "새로운 창작 글, 시, 이야기, 가사, 음악을 만든다",
        "crear escritura artística, poesía, historias, letras o música nuevas",
        "新しい創作文、詩、物語、歌詞、音楽を作る",
        "neue kreative Texte, Gedichte, Geschichten, Liedtexte oder Musik schaffen",
        "creative content compose",
    ),
    "explain": (
        "explain a concept, reason, cause, mechanism, or general knowledge topic",
        "개념, 이유, 원인, 원리 또는 일반 지식을 설명한다",
        "explicar un concepto, razón, causa, mecanismo o tema de conocimiento general",
        "概念、理由、原因、仕組み、一般知識を説明する",
        "ein Konzept, einen Grund, eine Ursache, einen Mechanismus oder allgemeines Wissen erklären",
        "concept/reason/general knowledge explain",
    ),
    "calculate": (
        "perform arithmetic, mathematical calculation, equation solving, or numeric evaluation",
        "산술, 수학 계산, 방정식 풀이 또는 수치 연산을 한다",
        "realizar aritmética, cálculo matemático, resolver ecuaciones o evaluar números",
        "算術、数学計算、方程式の解法、数値評価を行う",
        "Arithmetik, mathematische Berechnung, Gleichungslösung oder numerische Auswertung durchführen",
        "math/numeric calculate",
    ),
    "chat": (
        "casual conversation, greeting, joke, riddle, or social small talk",
        "일상 대화, 인사, 농담, 수수께끼 또는 잡담을 한다",
        "conversación casual, saludo, broma, adivinanza o charla social",
        "雑談、挨拶、冗談、なぞなぞ、日常会話をする",
        "lockeres Gespräch, Begrüßung, Witz, Rätsel oder Smalltalk",
        "casual chat joke greeting",
    ),
}

CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "search": ("search", "find", "query", "검색", "찾기", "buscar", "検索", "suchen"),
    "retrieve": ("retrieve", "get one", "lookup", "details", "조회", "불러", "obtener", "取得", "abrufen"),
    "list": ("list", "enumerate", "all ", "목록", "listar", "一覧", "auflisten"),
    "create": ("create", "register", "add new", "schedule", "생성", "등록", "crear", "作成", "erstellen"),
    "update": ("update", "edit", "change", "modify", "수정", "변경", "actualizar", "更新", "ändern"),
    "delete": ("delete", "remove", "erase", "purge", "삭제", "제거", "eliminar", "削除", "löschen"),
    "cancel": ("cancel", "revoke", "abort", "취소", "철회", "cancelar", "キャンセル", "stornieren"),
    "refund": ("refund", "reimburse", "환불", "reembolso", "返金", "erstatten"),
    "send": ("send", "dispatch", "deliver", "forward", "전송", "보내", "enviar", "送信", "senden"),
    "share": ("share", "grant access", "공유", "compartir", "共有", "teilen"),
    "export": ("export", "download", "내보내", "다운로드", "exportar", "エクスポート", "exportieren"),
    "translate": ("translate", "번역", "traducir", "翻訳", "übersetzen"),
    "summarize": ("summarize", "summary", "요약", "resumir", "要約", "zusammenfassen"),
    "compare": ("compare", "contrast", "비교", "comparar", "比較", "vergleichen"),
    "merge": ("merge", "combine", "consolidate", "병합", "fusionar", "統合", "zusammenführen"),
    "restart": ("restart", "reboot", "재시작", "reiniciar", "再起動", "neustarten"),
    "execute": ("execute", "run workflow", "trigger", "invoke", "실행", "ejecutar", "実行", "ausführen"),
    "forecast": ("forecast", "predict", "future", "예측", "pronóstico", "予測", "prognose"),
}

METHOD_LEAF = {
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    leaf: str | None
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]


def _normalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _pattern_present(normalized: str, pattern: str) -> bool:
    pattern_n = _normalize(pattern)
    if not pattern_n:
        return False
    if any(ord(ch) > 127 for ch in pattern_n) or pattern.endswith(" "):
        return pattern_n in normalized
    if " " in pattern_n:
        return pattern_n in normalized
    return f" {pattern_n} " in f" {normalized} "


def explicit_leaf(query: str) -> str | None:
    """Reuse #347 generic parser semantics; generic read is UNKNOWN for leaf veto."""
    normalized = _normalize(query)
    hits = [
        action
        for action, patterns in _ACTION_PATTERNS.items()
        if action != "read"
        and any(_pattern_present(normalized, pattern) for pattern in patterns)
    ]
    unique = tuple(dict.fromkeys(hits))
    return unique[0] if len(unique) == 1 else None


def _endpoint_text(endpoint: Any) -> str:
    return "\n".join(
        str(value)
        for value in [
            endpoint.name,
            *endpoint.operation_aliases,
            endpoint.description,
            endpoint.path or "",
        ]
        if str(value).strip()
    )


def _contains(text: str, phrase: str) -> bool:
    haystack = _normalize(text)
    needle = _normalize(phrase)
    if not needle:
        return False
    if any(ord(char) > 127 for char in needle) or " " in needle:
        return needle in haystack
    return f" {needle} " in f" {haystack} "


def infer_endpoint_leaf(endpoint: Any) -> str | None:
    method = str(endpoint.method).upper() if endpoint.method else None
    if endpoint.destructive is True or method == "DELETE":
        return "delete"
    if method in METHOD_LEAF:
        return METHOD_LEAF[method]

    text = _endpoint_text(endpoint)
    for leaf, hints in CONTRACT_HINTS.items():
        if any(_contains(text, hint) for hint in hints):
            return leaf
    return None


def _schema_type(schema: dict[str, Any]) -> str:
    raw = schema.get("type")
    if isinstance(raw, str):
        base = raw
    elif isinstance(raw, list):
        base = "|".join(str(value) for value in raw)
    elif isinstance(schema.get("properties"), dict):
        base = "object"
    else:
        base = "unknown"
    if base == "array" and isinstance(schema.get("items"), dict):
        return f"array<{_schema_type(schema['items'])}>"
    return base


def _data_contract(endpoint: Any) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for parameter in endpoint.parameters:
        rows.append(
            {
                "role": "input",
                "name": str(parameter.name),
                "type": _schema_type(parameter.json_schema),
                "required": bool(parameter.required),
            }
        )
    for field in endpoint.output_fields:
        normalization = field.unit_normalization
        rows.append(
            {
                "role": "output",
                "name": str(field.name),
                "semantic_id": field.semantic_id,
                "type": _schema_type(field.json_schema),
                "source_unit": field.unit,
                "canonical_unit": normalization.canonical_unit if normalization is not None else None,
                "dimension": normalization.dimension if normalization is not None else None,
                "scale": normalization.scale if normalization is not None else None,
                "offset": normalization.offset if normalization is not None else None,
                "qualifiers": dict(field.qualifiers),
                "identifier": bool(field.identifier),
            }
        )
    return tuple(rows)


def compile_registry_contracts(registry: Any) -> dict[str, RouteContract]:
    contracts: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            contracts[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                leaf=infer_endpoint_leaf(endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return contracts


def decide_veto(
    *,
    explicit: str | None,
    bge_leaf: str,
    aux_leaf: str,
    supported_leaves: set[str],
    tool_has_unknown: bool,
) -> tuple[str | None, str | None]:
    """Apply the exact preregistered asymmetric veto rule."""
    if tool_has_unknown:
        return None, None

    if (
        explicit is not None
        and explicit not in supported_leaves
        and (bge_leaf == explicit or aux_leaf == explicit)
    ):
        return explicit, "explicit_plus_semantic_agreement"

    if (
        explicit is None
        and bge_leaf == aux_leaf
        and bge_leaf not in supported_leaves
    ):
        return bge_leaf, "dual_semantic_agreement"

    return None, None


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must align")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vectors must have non-zero norm")
    return max(
        -1.0,
        min(
            1.0,
            sum(a * b for a, b in zip(left, right, strict=True))
            / (left_norm * right_norm),
        ),
    )


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [[float(value) for value in vector] for vector in raw]
    if not vectors or any(not vector for vector in vectors):
        raise ValueError("embedder returned empty vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("embedder returned non-finite values")
    return vectors


def _schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [route_id, tool.description.strip(), endpoint.description.strip()]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    aliases = list(endpoint.operation_aliases)
    fallback = endpoint.description.strip() if not aliases else ""
    return "\n".join(
        dict.fromkeys(part for part in [operation_name, *aliases, fallback] if part)
    )


class AsymmetricOntologyVetoRouter:
    """Preserve raw BGE route unless independent ontology evidence proves unsupported."""

    def __init__(
        self,
        registry: Any,
        bge_embedder: Any,
        aux_embedder: Any,
    ) -> None:
        self.registry = registry
        self.bge_embedder = bge_embedder
        self.aux_embedder = aux_embedder
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        prototypes = [
            prototype
            for leaf in LEAF_PROTOTYPES
            for prototype in LEAF_PROTOTYPES[leaf]
        ]
        self.prototype_index = [
            leaf
            for leaf in LEAF_PROTOTYPES
            for _ in LEAF_PROTOTYPES[leaf]
        ]

        bge_static = _to_vectors(
            bge_embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                    *prototypes,
                ]
            )
        )
        route_count = len(self.route_ids)
        self.schema_vectors = dict(
            zip(self.route_ids, bge_static[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(
                self.route_ids,
                bge_static[route_count : route_count * 2],
                strict=True,
            )
        )
        self.bge_prototype_vectors = self._group_prototypes(
            bge_static[route_count * 2 :]
        )
        self.aux_prototype_vectors = self._group_prototypes(
            _to_vectors(aux_embedder(prototypes))
        )

    def _group_prototypes(
        self,
        vectors: list[list[float]],
    ) -> dict[str, list[list[float]]]:
        grouped = {leaf: [] for leaf in LEAF_PROTOTYPES}
        for leaf, vector in zip(self.prototype_index, vectors, strict=True):
            grouped[leaf].append(vector)
        return grouped

    @staticmethod
    def _semantic_vote(
        query_vector: list[float],
        prototype_vectors: dict[str, list[list[float]]],
    ) -> tuple[str, dict[str, float]]:
        scores = {
            leaf: max(_cosine(query_vector, vector) for vector in vectors)
            for leaf, vectors in prototype_vectors.items()
        }
        leaf, _ = min(scores.items(), key=lambda item: (-item[1], item[0]))
        return leaf, scores

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT * _cosine(query_vector, self.action_vectors[route_id])
            )
            rows.append((route_id, score))
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows

    def route(self, query: str) -> dict[str, Any]:
        bge_query = _to_vectors(self.bge_embedder([query]))[0]
        raw_ranked = self._rank_raw(bge_query)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_contracts = [
            contract
            for contract in self.contracts.values()
            if contract.tool_key == raw_tool
        ]
        known_supported = {
            contract.leaf
            for contract in tool_contracts
            if contract.leaf is not None
        }
        tool_has_unknown = any(contract.leaf is None for contract in tool_contracts)

        explicit = explicit_leaf(query)
        bge_leaf, bge_scores = self._semantic_vote(
            bge_query,
            self.bge_prototype_vectors,
        )
        aux_query = _to_vectors(self.aux_embedder([query]))[0]
        aux_leaf, aux_scores = self._semantic_vote(
            aux_query,
            self.aux_prototype_vectors,
        )

        veto_leaf, veto_rule = decide_veto(
            explicit=explicit,
            bge_leaf=bge_leaf,
            aux_leaf=aux_leaf,
            supported_leaves=known_supported,
            tool_has_unknown=tool_has_unknown,
        )

        predicted = None if veto_leaf is not None else raw_top_route
        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_supported_leaves": sorted(known_supported),
            "tool_has_unknown_leaf": tool_has_unknown,
            "explicit_leaf": explicit,
            "bge_leaf": bge_leaf,
            "aux_leaf": aux_leaf,
            "veto_leaf": veto_leaf,
            "veto_rule": veto_rule,
            "bge_leaf_scores": bge_scores,
            "aux_leaf_scores": aux_scores,
            "raw_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in raw_ranked
            ],
        }
