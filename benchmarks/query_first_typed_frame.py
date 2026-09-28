"""Query-first typed capability frame for experiment #347.

Research-only.  The parser is registry-independent.  Registered schemas remain authority.
No learned veto, route-local threshold, pseudo-route, or rank-2 fallthrough is used.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45

_READ_ACTION = "read"
_MUTATING_ACTIONS = {
    "create",
    "update",
    "delete",
    "cancel",
    "refund",
    "send",
    "share",
    "restart",
    "execute",
    "merge",
}
_TRANSFORM_ACTIONS = {
    "export",
    "translate",
    "summarize",
    "compare",
}
_NON_TOOL_ACTIONS = {
    "compose",
    "explain",
    "calculate",
    "chat",
}
_SPECIFIC_ACTIONS = (
    _MUTATING_ACTIONS
    | _TRANSFORM_ACTIONS
    | _NON_TOOL_ACTIONS
    | {"forecast"}
)

# Generic operation lexicon only.  It intentionally contains no benchmark tool, route,
# provider, domain, resource, field, or endpoint identities.
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
        "set ",
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
        "diff ",
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
        "run ",
        "trigger",
        "invoke",
        "실행",
        "ejecuta",
        "ejecutar",
        "実行",
        "ausführen",
        "starte ",
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

_TEMPORAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "current": (
        "current",
        "latest",
        "right now",
        "now",
        "live",
        "현재",
        "지금",
        "최신",
        "actual",
        "ahora",
        "último",
        "現在",
        "今",
        "最新",
        "aktuell",
        "jetzt",
        "neueste",
    ),
    "future": (
        "future",
        "upcoming",
        "forecast",
        "predicted",
        "next ",
        "앞으로",
        "예정",
        "예측",
        "향후",
        "futuro",
        "próximo",
        "pronóstico",
        "将来",
        "今後",
        "予測",
        "zukünftig",
        "kommend",
        "prognose",
    ),
    "historical": (
        "historical",
        "history",
        "past",
        "previous",
        "archive",
        "과거",
        "이전",
        "기록",
        "histórico",
        "historial",
        "pasado",
        "過去",
        "履歴",
        "以前",
        "historisch",
        "vergangen",
        "verlauf",
    ),
}

_METHOD_ACTION = {
    "GET": _READ_ACTION,
    "HEAD": _READ_ACTION,
    "OPTIONS": _READ_ACTION,
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


@dataclass(frozen=True)
class RequestFrame:
    actions: tuple[str, ...]
    temporal_scope: str | None
    evidence: tuple[str, ...]

    @property
    def has_structure(self) -> bool:
        return bool(self.actions or self.temporal_scope)


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    endpoint_name: str
    action: str | None
    temporal_scope: str | None
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _ascii_token_phrase_present(normalized: str, phrase: str) -> bool:
    padded = f" {normalized} "
    return f" {phrase} " in padded


def _pattern_present(normalized: str, pattern: str) -> bool:
    pattern_n = _normalize(pattern)
    if not pattern_n:
        return False
    # CJK/Korean and intentionally suffix-like stems are matched as substrings.
    if any(ord(ch) > 127 for ch in pattern_n) or pattern.endswith(" "):
        return pattern_n in normalized
    if " " in pattern_n:
        return pattern_n in normalized
    return _ascii_token_phrase_present(normalized, pattern_n)


def parse_request_frame(query: str) -> RequestFrame:
    normalized = _normalize(query)
    actions: list[str] = []
    evidence: list[str] = []

    # Specific actions dominate generic read verbs such as "show" or "find".
    for action, patterns in _ACTION_PATTERNS.items():
        if any(_pattern_present(normalized, pattern) for pattern in patterns):
            actions.append(action)
            evidence.append(f"action:{action}")

    # A transformation/mutation/non-tool action plus generic read wording is one specific request,
    # not a compound operation.  Example: "find and delete" remains compound, but
    # "show me a translated version" resolves to translate if translate is explicit.
    specific = [action for action in actions if action != _READ_ACTION]
    if specific:
        actions = specific

    actions = list(dict.fromkeys(actions))

    temporal_hits = [
        scope
        for scope, patterns in _TEMPORAL_PATTERNS.items()
        if any(_pattern_present(normalized, pattern) for pattern in patterns)
    ]
    temporal_scope = temporal_hits[0] if len(set(temporal_hits)) == 1 else None
    if temporal_scope:
        evidence.append(f"temporal:{temporal_scope}")

    return RequestFrame(
        actions=tuple(actions),
        temporal_scope=temporal_scope,
        evidence=tuple(evidence),
    )


def _endpoint_text(endpoint: Any) -> str:
    parts = [
        str(endpoint.name),
        *[str(value) for value in endpoint.operation_aliases],
        str(endpoint.description or ""),
    ]
    return "\n".join(part for part in parts if part.strip())


def infer_endpoint_action(endpoint: Any) -> str | None:
    method = str(endpoint.method).upper() if endpoint.method else None
    if endpoint.destructive is True or method == "DELETE":
        return "delete"

    normalized = _normalize(_endpoint_text(endpoint))
    # Specific semantic verbs beat HTTP GET/read-only defaults.
    for action, patterns in _ACTION_PATTERNS.items():
        if action in _NON_TOOL_ACTIONS:
            continue
        if any(_pattern_present(normalized, pattern) for pattern in patterns):
            return action

    if method in _METHOD_ACTION:
        return _METHOD_ACTION[method]
    if endpoint.read_only is True:
        return _READ_ACTION
    return None


def infer_endpoint_temporal(endpoint: Any) -> str | None:
    normalized = _normalize(
        "\n".join(
            [
                _endpoint_text(endpoint),
                str(endpoint.path or ""),
            ]
        )
    )
    hits = [
        scope
        for scope, patterns in _TEMPORAL_PATTERNS.items()
        if any(_pattern_present(normalized, pattern) for pattern in patterns)
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
                "unit": None,
                "semantic_id": None,
                "qualifiers": {},
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
                "unit": field.unit,
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
        metadata = tool.execution_metadata or {}
        adapter = metadata.get("adapter") if isinstance(metadata, dict) else None
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            if route_id in result:
                raise ValueError(f"duplicate route id: {route_id}")
            result[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                endpoint_name=str(endpoint.name),
                action=infer_endpoint_action(endpoint),
                temporal_scope=infer_endpoint_temporal(endpoint),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return result


def _action_contradiction(frame: RequestFrame, contract: RouteContract) -> bool:
    if not frame.actions:
        return False

    # More than one distinct specific action exceeds the experiment's single-call contract.
    if len(frame.actions) > 1:
        return True

    action = frame.actions[0]
    if action in _NON_TOOL_ACTIONS:
        return contract.action != action

    if action in _MUTATING_ACTIONS:
        if contract.read_only is True:
            return True
        if action == "delete" and contract.destructive is False:
            return True

    if action == _READ_ACTION and contract.destructive is True:
        return True

    # Unknown endpoint semantics do not create a contradiction unless trusted structural
    # metadata above proves one.
    if contract.action is None:
        return False

    return contract.action != action


def contract_contradicts(frame: RequestFrame, contract: RouteContract) -> bool:
    if _action_contradiction(frame, contract):
        return True
    if (
        frame.temporal_scope is not None
        and contract.temporal_scope is not None
        and frame.temporal_scope != contract.temporal_scope
    ):
        return True
    return False


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must be non-empty and dimensionally aligned")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vectors must have non-zero norm")
    value = sum(a * b for a, b in zip(left, right, strict=True))
    return max(-1.0, min(1.0, value / (left_norm * right_norm)))


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
        dict.fromkeys(
            part for part in [operation_name, *aliases, fallback] if part
        )
    )


class QueryFirstTypedFrameRouter:
    """Generic BGE domain anchor + deterministic within-tool typed filtering."""

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
            raise ValueError("contract and route-spec sets differ")

        self.route_ids = tuple(sorted(route_specs))
        self.route_specs = route_specs
        texts = [
            *(route_specs[route][0] for route in self.route_ids),
            *(route_specs[route][1] for route in self.route_ids),
        ]
        vectors = _to_vectors(embedder(texts))
        if len(vectors) != len(texts):
            raise ValueError("unexpected route embedding count")
        split = len(self.route_ids)
        self.schema_vectors = dict(
            zip(self.route_ids, vectors[:split], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, vectors[split:], strict=True)
        )

    def _score_with_vector(
        self,
        query_vector: list[float],
        routes: Iterable[str],
    ) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        for route_id in routes:
            schema_score = _cosine(query_vector, self.schema_vectors[route_id])
            action_score = _cosine(query_vector, self.action_vectors[route_id])
            score = SCHEMA_WEIGHT * schema_score + ACTION_WEIGHT * action_score
            scored.append((route_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._score_with_vector(query_vector, self.route_ids)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key
        frame = parse_request_frame(query)

        tool_routes = [
            route_id
            for route_id in self.route_ids
            if self.contracts[route_id].tool_key == raw_tool
        ]

        if not frame.has_structure:
            return {
                "predicted": raw_top_route,
                "raw_top_route": raw_top_route,
                "raw_top_score": raw_top_score,
                "raw_tool": raw_tool,
                "frame": asdict(frame),
                "tool_routes": tool_routes,
                "compatible_routes": tool_routes,
                "filtered": False,
                "reason": "no_explicit_typed_frame",
                "ranked_routes": [
                    {"route_id": route_id, "score": score}
                    for route_id, score in raw_ranked
                ],
            }

        compatible = [
            route_id
            for route_id in tool_routes
            if not contract_contradicts(frame, self.contracts[route_id])
        ]
        if not compatible:
            return {
                "predicted": None,
                "raw_top_route": raw_top_route,
                "raw_top_score": raw_top_score,
                "raw_tool": raw_tool,
                "frame": asdict(frame),
                "tool_routes": tool_routes,
                "compatible_routes": [],
                "filtered": True,
                "reason": "empty_typed_capability_set",
                "ranked_routes": [
                    {"route_id": route_id, "score": score}
                    for route_id, score in raw_ranked
                ],
            }

        compatible_ranked = self._score_with_vector(query_vector, compatible)
        predicted = compatible_ranked[0][0]
        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "frame": asdict(frame),
            "tool_routes": tool_routes,
            "compatible_routes": compatible,
            "filtered": set(compatible) != set(tool_routes),
            "reason": "typed_filter_then_rank",
            "ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
            "compatible_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in compatible_ranked
            ],
        }
