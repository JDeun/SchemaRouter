# ruff: noqa: E501
"""Hierarchical executable-capability ontology for experiment #354.

Research-only.  A frozen BGE-M3 embedding projects the request onto a registry-independent
operation ontology.  Registered schemas remain the only execution authority.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45

ONTOLOGY: dict[str, tuple[str, ...]] = {
    "read": ("search", "retrieve", "list"),
    "mutate": ("create", "update", "delete", "cancel", "refund"),
    "transfer": ("send", "share"),
    "transform": ("export", "translate", "summarize", "compare", "merge"),
    "control": ("restart", "execute"),
    "predict": ("forecast",),
    "non_tool": ("compose", "explain", "calculate", "chat"),
}

LEAF_TO_ROOT = {
    leaf: root
    for root, leaves in ONTOLOGY.items()
    for leaf in leaves
}

ROOT_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "read": (
        "read existing information without changing external state",
        "기존 정보를 변경하지 않고 읽거나 조회하는 작업",
        "leer o consultar información existente sin cambiar el estado externo",
        "外部状態を変更せず既存情報を読む、検索、取得する操作",
        "vorhandene Informationen lesen oder abrufen ohne externen Zustand zu ändern",
        "existing 정보를 변경 없이 read하는 작업",
    ),
    "mutate": (
        "change the lifecycle or stored state of an existing or new resource",
        "리소스를 생성, 수정, 삭제, 취소, 환불하여 저장 상태를 변경하는 작업",
        "cambiar el estado almacenado o el ciclo de vida de un recurso",
        "リソースの作成、更新、削除、取消など保存状態を変更する操作",
        "den gespeicherten Zustand oder Lebenszyklus einer Ressource ändern",
        "resource state를 create update delete 등으로 변경하는 작업",
    ),
    "transfer": (
        "send or share an existing resource with another destination or person",
        "기존 리소스를 다른 대상에게 보내거나 공유하는 작업",
        "enviar o compartir un recurso existente con otro destino o persona",
        "既存リソースを別の相手へ送信または共有する操作",
        "eine bestehende Ressource an ein anderes Ziel senden oder teilen",
        "existing resource를 send 또는 share하는 작업",
    ),
    "transform": (
        "transform, export, translate, summarize, compare, or merge existing content",
        "기존 콘텐츠를 내보내기, 번역, 요약, 비교, 병합 등으로 변환하는 작업",
        "transformar, exportar, traducir, resumir, comparar o fusionar contenido existente",
        "既存内容をエクスポート、翻訳、要約、比較、統合などで変換する操作",
        "bestehende Inhalte exportieren, übersetzen, zusammenfassen, vergleichen oder zusammenführen",
        "existing content를 transform export translate summarize compare merge하는 작업",
    ),
    "control": (
        "control an executable system by restarting or executing a job, service, or workflow",
        "작업, 서비스, 워크플로를 재시작하거나 실행하여 제어하는 작업",
        "controlar un sistema ejecutable reiniciando o ejecutando un trabajo o flujo",
        "ジョブ、サービス、ワークフローを再起動または実行して制御する操作",
        "ein ausführbares System durch Neustart oder Ausführung eines Jobs steuern",
        "job service workflow를 restart 또는 execute하는 제어 작업",
    ),
    "predict": (
        "predict or forecast a future value, state, arrival, trend, or outcome",
        "미래의 값, 상태, 도착, 추세 또는 결과를 예측하는 작업",
        "predecir o pronosticar un valor, estado, llegada, tendencia o resultado futuro",
        "将来の値、状態、到着、傾向、結果を予測する操作",
        "einen zukünftigen Wert, Zustand, Trend oder Ausgang vorhersagen",
        "future value state trend를 forecast하는 작업",
    ),
    "non_tool": (
        "general conversation, creative writing, explanation, or arithmetic not requesting an external registered capability",
        "외부 등록 capability가 아니라 일반 대화, 창작, 설명, 계산을 요청하는 질문",
        "conversación, escritura creativa, explicación o cálculo sin pedir una capacidad externa registrada",
        "外部登録機能を求めず会話、創作、説明、計算を行う要求",
        "allgemeine Unterhaltung, kreatives Schreiben, Erklärung oder Rechnen ohne externe registrierte Fähigkeit",
        "external tool이 아닌 chat creative explain calculate 요청",
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

TEMPORAL_HINTS: dict[str, tuple[str, ...]] = {
    "current": ("current", "now", "latest", "현재", "지금", "actual", "現在", "aktuell"),
    "future": ("future", "upcoming", "next", "향후", "앞으로", "futuro", "将来", "zukünftig"),
    "historical": ("historical", "history", "past", "과거", "이전", "histórico", "過去", "historisch"),
}

METHOD_LEAF = {
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


@dataclass(frozen=True)
class RequestConstraints:
    root: str
    leaf: str
    temporal_scope: str | None
    root_score: float
    leaf_score: float

    @property
    def facts(self) -> tuple[str, ...]:
        return (
            f"root:{self.root}",
            f"leaf:{self.leaf}",
            *(
                (f"temporal:{self.temporal_scope}",)
                if self.temporal_scope is not None
                else ()
            ),
        )


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    root: str | None
    leaf: str | None
    temporal_scope: str | None
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]


def _normalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _contains(text: str, phrase: str) -> bool:
    haystack = _normalize(text)
    needle = _normalize(phrase)
    if not needle:
        return False
    if any(ord(char) > 127 for char in needle) or " " in needle:
        return needle in haystack
    return f" {needle} " in f" {haystack} "


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

    if method in {"GET", "HEAD", "OPTIONS"} or endpoint.read_only is True:
        # Trusted metadata establishes read-root semantics but not a specific read leaf.
        return None
    return None


def infer_endpoint_root(endpoint: Any, leaf: str | None) -> str | None:
    if leaf is not None:
        return LEAF_TO_ROOT[leaf]
    method = str(endpoint.method).upper() if endpoint.method else None
    if endpoint.destructive is True or method in {"PATCH", "PUT", "DELETE"}:
        return "mutate"
    if method in {"GET", "HEAD", "OPTIONS"} or endpoint.read_only is True:
        return "read"
    return None


def _temporal_from_text(text: str) -> str | None:
    hits = [
        scope
        for scope, hints in TEMPORAL_HINTS.items()
        if any(_contains(text, hint) for hint in hints)
    ]
    unique = list(dict.fromkeys(hits))
    return unique[0] if len(unique) == 1 else None


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
                "canonical_unit": (
                    normalization.canonical_unit
                    if normalization is not None
                    else None
                ),
                "dimension": (
                    normalization.dimension
                    if normalization is not None
                    else None
                ),
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
            leaf = infer_endpoint_leaf(endpoint)
            contracts[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                root=infer_endpoint_root(endpoint, leaf),
                leaf=leaf,
                temporal_scope=_temporal_from_text(_endpoint_text(endpoint)),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return contracts


def contract_compatible(
    request: RequestConstraints,
    contract: RouteContract,
) -> bool:
    if request.root == "non_tool":
        return False
    if contract.root is not None and request.root != contract.root:
        return False
    if contract.leaf is not None and request.leaf != contract.leaf:
        return False
    if request.root != "read" and contract.read_only is True:
        return False
    if request.root == "read" and contract.destructive is True:
        return False
    if (
        request.temporal_scope is not None
        and contract.temporal_scope is not None
        and request.temporal_scope != contract.temporal_scope
    ):
        return False
    return True


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


class HierarchicalCapabilityOntologyRouter:
    """BGE tool anchor plus hierarchical generic capability constraints."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
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

        self.root_index = [
            (root, prototype)
            for root, prototypes in ROOT_PROTOTYPES.items()
            for prototype in prototypes
        ]
        self.leaf_index = [
            (leaf, prototype)
            for leaf, prototypes in LEAF_PROTOTYPES.items()
            for prototype in prototypes
        ]

        texts = [
            *(route_specs[route][0] for route in self.route_ids),
            *(route_specs[route][1] for route in self.route_ids),
            *(prototype for _, prototype in self.root_index),
            *(prototype for _, prototype in self.leaf_index),
        ]
        vectors = _to_vectors(embedder(texts))
        if len(vectors) != len(texts):
            raise ValueError("unexpected static embedding count")

        route_count = len(self.route_ids)
        self.schema_vectors = dict(
            zip(self.route_ids, vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(
                self.route_ids,
                vectors[route_count : route_count * 2],
                strict=True,
            )
        )
        cursor = route_count * 2
        root_vectors = vectors[cursor : cursor + len(self.root_index)]
        cursor += len(self.root_index)
        leaf_vectors = vectors[cursor:]

        self.root_vectors: dict[str, list[list[float]]] = {
            root: [] for root in ONTOLOGY
        }
        for (root, _), vector in zip(self.root_index, root_vectors, strict=True):
            self.root_vectors[root].append(vector)

        self.leaf_vectors: dict[str, list[list[float]]] = {
            leaf: [] for leaf in LEAF_TO_ROOT
        }
        for (leaf, _), vector in zip(self.leaf_index, leaf_vectors, strict=True):
            self.leaf_vectors[leaf].append(vector)

    def _rank_routes(
        self,
        query_vector: list[float],
        routes: Iterable[str],
    ) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in routes:
            score = (
                SCHEMA_WEIGHT * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT * _cosine(query_vector, self.action_vectors[route_id])
            )
            rows.append((route_id, score))
        rows.sort(key=lambda row: (-row[1], row[0]))
        return rows

    @staticmethod
    def _prototype_scores(
        query_vector: list[float],
        vectors: dict[str, list[list[float]]],
    ) -> dict[str, float]:
        return {
            key: max(_cosine(query_vector, vector) for vector in values)
            for key, values in vectors.items()
        }

    def _project_request(
        self,
        query: str,
        query_vector: list[float],
    ) -> tuple[RequestConstraints, dict[str, float], dict[str, float]]:
        root_scores = self._prototype_scores(query_vector, self.root_vectors)
        root, root_score = min(
            root_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        candidate_leaves = ONTOLOGY[root]
        leaf_scores_all = self._prototype_scores(query_vector, self.leaf_vectors)
        leaf, leaf_score = min(
            ((leaf, leaf_scores_all[leaf]) for leaf in candidate_leaves),
            key=lambda item: (-item[1], item[0]),
        )
        return (
            RequestConstraints(
                root=root,
                leaf=leaf,
                temporal_scope=_temporal_from_text(query),
                root_score=root_score,
                leaf_score=leaf_score,
            ),
            root_scores,
            leaf_scores_all,
        )

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_routes(query_vector, self.route_ids)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        request, root_scores, leaf_scores = self._project_request(
            query,
            query_vector,
        )
        tool_routes = [
            route
            for route in self.route_ids
            if self.contracts[route].tool_key == raw_tool
        ]
        compatible = [
            route
            for route in tool_routes
            if contract_compatible(request, self.contracts[route])
        ]

        if compatible:
            compatible_ranked = self._rank_routes(query_vector, compatible)
            predicted = compatible_ranked[0][0]
            reason = "hierarchical_constraints_then_rank"
        else:
            compatible_ranked = []
            predicted = None
            reason = "empty_ontology_capability_set"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "request": asdict(request),
            "request_facts": request.facts,
            "root_scores": root_scores,
            "leaf_scores": leaf_scores,
            "tool_routes": tool_routes,
            "compatible_routes": compatible,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in raw_ranked
            ],
            "compatible_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in compatible_ranked
            ],
        }
