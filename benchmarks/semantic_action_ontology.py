# ruff: noqa: E501 -- multilingual ontology literals are intentionally explicit.
"""Registry-independent semantic action ontology for experiment #349.

Research-only. One frozen BGE-M3 query embedding is reused for action classification and route
ranking. Action classification is a closed generic ontology argmax with no threshold or learned
head. Registered schemas remain the only execution authority.
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

NON_TOOL_ACTIONS = {"compose", "explain", "calculate", "chat"}

ACTION_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "read": (
        "retrieve, search, list, inspect, or show existing information without changing it",
        "기존 정보를 변경하지 않고 조회, 검색, 목록 확인 또는 가져오기",
        "consultar, buscar, listar u obtener información existente sin modificarla",
        "既存の情報を変更せずに検索、取得、一覧表示、確認する",
        "vorhandene Informationen suchen, abrufen, auflisten oder anzeigen ohne sie zu ändern",
        "existing 정보를 search 또는 retrieve해서 보여주기",
    ),
    "create": (
        "create, register, add, schedule, or make a new resource",
        "새 항목을 만들고 등록하거나 추가 또는 예약하기",
        "crear, registrar, añadir o programar un recurso nuevo",
        "新しい項目を作成、登録、追加、予約する",
        "eine neue Ressource erstellen, registrieren, hinzufügen oder planen",
        "new resource를 생성하거나 register하기",
    ),
    "update": (
        "update, edit, rename, set, or change an existing resource",
        "기존 항목을 수정, 변경, 편집하거나 값을 설정하기",
        "actualizar, editar o cambiar un recurso existente",
        "既存の項目を更新、編集、変更、設定する",
        "eine bestehende Ressource aktualisieren, bearbeiten oder ändern",
        "existing resource를 update하거나 변경하기",
    ),
    "delete": (
        "delete, erase, purge, or permanently remove an existing resource",
        "기존 항목을 삭제, 제거 또는 영구적으로 지우기",
        "eliminar, borrar o quitar permanentemente un recurso existente",
        "既存の項目を削除、消去、永久に除去する",
        "eine bestehende Ressource löschen oder dauerhaft entfernen",
        "existing resource를 delete하거나 영구 제거하기",
    ),
    "cancel": (
        "cancel, revoke, stop, or abort an existing active or scheduled operation",
        "기존의 활성 또는 예정된 작업을 취소, 철회, 중단하기",
        "cancelar, revocar o detener una operación activa o programada",
        "既存の実行中または予定された処理をキャンセル、中止、取消する",
        "eine bestehende aktive oder geplante Operation stornieren oder abbrechen",
        "existing operation을 cancel하기",
    ),
    "refund": (
        "refund, reimburse, or return previously transferred money to its source",
        "이전에 전달된 금액을 환불하거나 원래 출처로 돌려주기",
        "reembolsar o devolver dinero previamente transferido a su origen",
        "以前に移動した金額を返金して元に戻す",
        "zuvor übertragenes Geld erstatten oder an die Quelle zurückzahlen",
        "transferred money를 refund하기",
    ),
    "send": (
        "send, dispatch, deliver, forward, or transmit content to another party",
        "내용을 다른 대상에게 보내거나 전송, 전달하기",
        "enviar, despachar, entregar o transmitir contenido a otra parte",
        "内容を別の相手へ送信、配送、転送する",
        "Inhalt an eine andere Partei senden, zustellen oder übertragen",
        "content를 다른 대상으로 send 또는 transmit하기",
    ),
    "share": (
        "share a resource or grant another person access to it",
        "항목을 다른 사람과 공유하거나 접근 권한을 주기",
        "compartir un recurso o conceder acceso a otra persona",
        "リソースを共有したり他の人にアクセスを与える",
        "eine Ressource teilen oder einer anderen Person Zugriff geben",
        "resource를 다른 사람과 share하기",
    ),
    "export": (
        "export, download, extract, or save a resource into an external file",
        "데이터나 항목을 파일로 내보내거나 다운로드하기",
        "exportar, descargar o guardar un recurso en un archivo externo",
        "データや項目を外部ファイルへエクスポート、ダウンロード、保存する",
        "eine Ressource exportieren, herunterladen oder in einer externen Datei speichern",
        "resource를 file로 export하거나 download하기",
    ),
    "translate": (
        "translate content from one human language into another",
        "내용을 한 언어에서 다른 언어로 번역하기",
        "traducir contenido de un idioma humano a otro",
        "内容をある言語から別の言語へ翻訳する",
        "Inhalte von einer menschlichen Sprache in eine andere übersetzen",
        "content를 다른 language로 translate하기",
    ),
    "summarize": (
        "summarize content into a shorter description of its important points",
        "내용의 핵심을 더 짧게 요약하기",
        "resumir contenido en una descripción más corta de sus puntos principales",
        "内容の重要点を短く要約する",
        "Inhalte zu einer kürzeren Darstellung der wichtigsten Punkte zusammenfassen",
        "content의 핵심을 summarize하기",
    ),
    "compare": (
        "compare multiple items and identify similarities or differences",
        "여러 항목을 비교하여 공통점이나 차이점을 찾기",
        "comparar varios elementos e identificar similitudes o diferencias",
        "複数の項目を比較し共通点や違いを確認する",
        "mehrere Elemente vergleichen und Gemeinsamkeiten oder Unterschiede feststellen",
        "multiple items를 compare하기",
    ),
    "merge": (
        "merge, combine, join, or consolidate multiple resources into one",
        "여러 항목을 하나로 병합하거나 합치기",
        "fusionar, combinar o consolidar varios recursos en uno",
        "複数の項目を一つに統合、結合する",
        "mehrere Ressourcen zu einer zusammenführen oder kombinieren",
        "multiple resources를 merge하기",
    ),
    "restart": (
        "restart, reboot, or start an existing running unit or process again",
        "실행 중인 단위나 프로세스를 재시작하거나 재부팅하기",
        "reiniciar una unidad o proceso existente",
        "既存の実行単位や処理を再起動する",
        "eine bestehende laufende Einheit oder einen Prozess neu starten",
        "running unit이나 process를 restart하기",
    ),
    "execute": (
        "execute, run, trigger, invoke, or start an executable operation or process",
        "실행 가능한 작업이나 프로세스를 실행, 호출 또는 시작하기",
        "ejecutar, activar o iniciar una operación o proceso ejecutable",
        "実行可能な操作や処理を実行、起動、呼び出す",
        "eine ausführbare Operation oder einen Prozess ausführen, auslösen oder starten",
        "executable operation을 execute하기",
    ),
    "forecast": (
        "forecast or predict a future value, state, trend, arrival, or outcome",
        "미래의 값, 상태, 추세, 도착 또는 결과를 예측하기",
        "pronosticar o predecir un valor, estado, tendencia o resultado futuro",
        "将来の値、状態、傾向、到着、結果を予測する",
        "einen zukünftigen Wert, Zustand, Trend oder Ausgang prognostizieren",
        "future value나 state를 forecast하기",
    ),
    "compose": (
        "write or compose new creative prose, poetry, story, lyrics, or music",
        "새로운 시, 이야기, 글, 가사 또는 음악을 창작하기",
        "escribir o componer poesía, historias, texto creativo o música nueva",
        "新しい詩、物語、創作文、歌詞、音楽を作る",
        "neue kreative Texte, Gedichte, Geschichten oder Musik verfassen",
        "creative 글이나 music을 compose하기",
    ),
    "explain": (
        "explain a concept, reason, cause, mechanism, or general knowledge question",
        "개념, 이유, 원인, 원리 또는 일반 지식을 설명하기",
        "explicar un concepto, razón, causa, mecanismo o conocimiento general",
        "概念、理由、原因、仕組み、一般知識を説明する",
        "ein Konzept, einen Grund, eine Ursache oder allgemeines Wissen erklären",
        "concept나 reason을 explain하기",
    ),
    "calculate": (
        "calculate, compute, solve, or evaluate a mathematical expression or number",
        "수학식이나 숫자를 계산, 연산 또는 풀이하기",
        "calcular, resolver o evaluar una expresión matemática o un número",
        "数式や数値を計算、演算、解く",
        "einen mathematischen Ausdruck oder eine Zahl berechnen oder lösen",
        "math expression을 calculate하기",
    ),
    "chat": (
        "casual conversation, joke, greeting, small talk, or social response",
        "일상 대화, 농담, 인사 또는 잡담을 하기",
        "conversación casual, saludo, broma o charla social",
        "雑談、挨拶、冗談、日常会話をする",
        "lockeres Gespräch, Begrüßung, Witz oder Smalltalk",
        "casual chat이나 joke를 하기",
    ),
}

_TEMPORAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "current": ("current", "latest", "right now", "현재", "지금", "actual", "ahora", "現在", "今", "aktuell", "jetzt"),
    "future": ("future", "upcoming", "next", "앞으로", "향후", "futuro", "próximo", "将来", "今後", "zukünftig", "kommend"),
    "historical": ("historical", "history", "past", "과거", "이전", "histórico", "pasado", "過去", "履歴", "historisch", "vergangen"),
}

_CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "read": ("search", "find", "lookup", "look up", "retrieve", "get", "show", "list", "검색", "조회", "찾기", "buscar", "obtener", "取得", "検索", "suche", "abrufen"),
    "create": ("create", "add", "register", "schedule", "생성", "추가", "등록", "crear", "añadir", "作成", "追加", "erstellen", "hinzufügen"),
    "update": ("update", "edit", "change", "modify", "rename", "수정", "변경", "actualizar", "editar", "更新", "変更", "aktualisieren", "ändern"),
    "delete": ("delete", "remove", "purge", "erase", "삭제", "제거", "eliminar", "borrar", "削除", "löschen", "entfernen"),
    "cancel": ("cancel", "revoke", "abort", "취소", "철회", "cancelar", "revocar", "キャンセル", "stornieren", "abbrechen"),
    "refund": ("refund", "reimburse", "환불", "reembolso", "返金", "erstatten"),
    "send": ("send", "dispatch", "deliver", "forward", "transmit", "보내", "전송", "enviar", "envía", "送信", "senden"),
    "share": ("share", "공유", "compartir", "共有", "teilen"),
    "export": ("export", "download", "내보내", "다운로드", "exportar", "descargar", "エクスポート", "exportieren", "herunterladen"),
    "translate": ("translate", "번역", "traducir", "翻訳", "übersetzen"),
    "summarize": ("summarize", "summary", "요약", "resumir", "要約", "zusammenfassen"),
    "compare": ("compare", "contrast", "비교", "comparar", "比較", "vergleichen"),
    "merge": ("merge", "combine", "병합", "합쳐", "fusionar", "統合", "zusammenführen"),
    "restart": ("restart", "reboot", "재시작", "재부팅", "reiniciar", "再起動", "neustarten"),
    "execute": ("execute", "run", "trigger", "invoke", "실행", "ejecutar", "実行", "ausführen"),
    "forecast": ("forecast", "predict", "prediction", "예측", "전망", "pronóstico", "予測", "prognose"),
}

_METHOD_ACTION = {
    "GET": "read",
    "HEAD": "read",
    "OPTIONS": "read",
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


@dataclass(frozen=True)
class RequestFrame:
    action: str
    temporal_scope: str | None
    action_score: float


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    action: str | None
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
    normalized = _normalize(text)
    target = _normalize(phrase)
    if not target:
        return False
    if any(ord(ch) > 127 for ch in target):
        return target in normalized
    return f" {target} " in f" {normalized} " if " " not in target else target in normalized


def _endpoint_text(endpoint: Any) -> str:
    return "\n".join(
        str(part)
        for part in [
            endpoint.name,
            *endpoint.operation_aliases,
            endpoint.description,
            endpoint.path or "",
        ]
        if str(part).strip()
    )


def infer_endpoint_action(endpoint: Any) -> str | None:
    method = str(endpoint.method).upper() if endpoint.method else None
    if endpoint.destructive is True or method == "DELETE":
        return "delete"

    text = _endpoint_text(endpoint)
    for action, hints in _CONTRACT_HINTS.items():
        if any(_contains(text, hint) for hint in hints):
            return action

    if method in _METHOD_ACTION:
        return _METHOD_ACTION[method]
    if endpoint.read_only is True:
        return "read"
    return None


def infer_endpoint_temporal(endpoint: Any) -> str | None:
    text = _endpoint_text(endpoint)
    hits = [
        scope
        for scope, hints in _TEMPORAL_PATTERNS.items()
        if any(_contains(text, hint) for hint in hints)
    ]
    unique = list(dict.fromkeys(hits))
    return unique[0] if len(unique) == 1 else None


def parse_temporal_scope(query: str) -> str | None:
    hits = [
        scope
        for scope, hints in _TEMPORAL_PATTERNS.items()
        if any(_contains(query, hint) for hint in hints)
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
                    normalization.canonical_unit if normalization is not None else None
                ),
                "dimension": (
                    normalization.dimension if normalization is not None else None
                ),
                "scale": normalization.scale if normalization is not None else None,
                "offset": normalization.offset if normalization is not None else None,
                "qualifiers": dict(field.qualifiers),
                "identifier": bool(field.identifier),
            }
        )
    return tuple(rows)


def compile_registry_contracts(registry: Any) -> dict[str, RouteContract]:
    result: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            result[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                action=infer_endpoint_action(endpoint),
                temporal_scope=infer_endpoint_temporal(endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return result


def contract_compatible(frame: RequestFrame, contract: RouteContract) -> bool:
    if frame.action in NON_TOOL_ACTIONS:
        return False
    if contract.action is not None and frame.action != contract.action:
        return False
    if frame.action != "read" and contract.read_only is True:
        return False
    if frame.action == "read" and contract.destructive is True:
        return False
    if (
        frame.temporal_scope is not None
        and contract.temporal_scope is not None
        and frame.temporal_scope != contract.temporal_scope
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


class SemanticActionOntologyRouter:
    """Frozen BGE tool anchor plus generic semantic action ontology."""

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
        self.route_specs = route_specs

        self.prototype_index: list[tuple[str, str]] = [
            (action, prototype)
            for action, prototypes in ACTION_PROTOTYPES.items()
            for prototype in prototypes
        ]
        static_texts = [
            *(route_specs[route][0] for route in self.route_ids),
            *(route_specs[route][1] for route in self.route_ids),
            *(prototype for _, prototype in self.prototype_index),
        ]
        vectors = _to_vectors(embedder(static_texts))
        if len(vectors) != len(static_texts):
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
        prototype_vectors = vectors[route_count * 2 :]
        self.prototype_vectors: dict[str, list[list[float]]] = {
            action: [] for action in ACTION_PROTOTYPES
        }
        for (action, _), vector in zip(
            self.prototype_index,
            prototype_vectors,
            strict=True,
        ):
            self.prototype_vectors[action].append(vector)

    def _rank_routes(
        self,
        query_vector: list[float],
        routes: Iterable[str],
    ) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        for route_id in routes:
            score = (
                SCHEMA_WEIGHT * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT * _cosine(query_vector, self.action_vectors[route_id])
            )
            scored.append((route_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored

    def _classify_action(
        self,
        query_vector: list[float],
    ) -> tuple[str, float, dict[str, float]]:
        scores = {
            action: max(
                _cosine(query_vector, vector)
                for vector in vectors
            )
            for action, vectors in self.prototype_vectors.items()
        }
        action, score = min(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        return action, score, scores

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_routes(query_vector, self.route_ids)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        action, action_score, action_scores = self._classify_action(query_vector)
        frame = RequestFrame(
            action=action,
            temporal_scope=parse_temporal_scope(query),
            action_score=action_score,
        )

        tool_routes = [
            route
            for route in self.route_ids
            if self.contracts[route].tool_key == raw_tool
        ]
        compatible = [
            route
            for route in tool_routes
            if contract_compatible(frame, self.contracts[route])
        ]

        if not compatible:
            predicted = None
            compatible_ranked: list[tuple[str, float]] = []
            reason = "empty_semantic_capability_set"
        else:
            compatible_ranked = self._rank_routes(query_vector, compatible)
            predicted = compatible_ranked[0][0]
            reason = "semantic_action_then_typed_filter"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "frame": asdict(frame),
            "action_scores": action_scores,
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
