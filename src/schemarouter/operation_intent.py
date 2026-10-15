"""Conservative, offline multilingual operation-intent *hypotheses* (#1339).

This is an optional developer baseline, NOT an authorization source, a general
language understanding model, or a calibrated open-set classifier. A host must
independently establish requested operation/route authority before creating a
DeclaredOperationFitPolicy. Ambiguous, negated, explanatory or unknown requests
abstain instead of guessing from a high-similarity tool description.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .operation_fit import OperationKind

IntentReason = Literal[
    "explicit_single_operation",
    "missing_operation",
    "ambiguous_operations",
    "negated_or_explanatory",
    "empty_query",
    "oversized_query",
]

# Deliberately small, inspectable action lexicon. Never silently infer
# operation types from a tool's title, description, or similarity score.
# English verb boundaries avoid matching substrings such as "research".
_EXPLICIT_ACTIONS: dict[OperationKind, tuple[str, ...]] = {
    "search": (
        r"\bsearch\b|\bfind\b|\blook\s+for\b",
        r"검색|찾아|찾기",
        r"検索|探して|探す",
    ),
    "lookup": (
        r"\blook\s+up\b|\blookup\b|\bretrieve\b|\bfetch\b",
        r"조회|열람|확인해|확인하",
        r"照会|参照|確認して|確認する",
    ),
    "list": (
        r"\blist\b|\benumerate\b",
        r"목록|나열",
        r"一覧|列挙|リストアップ",
    ),
    "history": (
        r"\bhistory\b|\bhistorical\b|\bpast\s+records\b",
        r"이력|내역",
        r"履歴|過去の記録",
    ),
    "convert": (
        r"\bconvert\b|\bconversion\b",
        r"환산|변환",
        r"換算|変換",
    ),
    "directions": (
        r"\bdirections\b|\bwalking\s+route\b|\bdriving\s+route\b",
        r"길찾기|가는\s+길|경로\s*안내|도보\s*경로",
        r"道順|徒歩ルート|経路案内",
    ),
    "create": (
        r"\bcreate\b|\bschedule\b|\bregister\b",
        r"생성|등록|새로\s*만들|추가해|추가하",
        r"作成|新規登録|追加して|追加する",
    ),
    "update": (
        r"\bupdate\b|\bmodify\b|\bchange\b|\bedit\b",
        r"수정|변경|갱신|업데이트",
        r"更新|変更|修正",
    ),
    "delete": (
        r"\bdelete\b|\berase\b|\bremove\b",
        r"삭제|지워|제거",
        r"削除|消去|消して",
    ),
}

_NEGATED_OR_EXPLANATORY = re.compile(
    r"\b(?:do\s+not|don't|doesn't|not|without|how\s+to|"
    r"what\s+(?:does|is)|meaning\s+of)\b"
    r"|하지\s*마|하지\s*말|하지\s*않|삭제하지|지우지|말고|방법|뜻은|의미는"
    r"|しない|しなく|しないで|せず|ないで|とは|方法|意味",
    flags=re.IGNORECASE,
)

_COMPILED = {
    kind: tuple(re.compile(part, flags=re.IGNORECASE | re.ASCII) for part in expressions)
    for kind, expressions in _EXPLICIT_ACTIONS.items()
}


@dataclass(frozen=True)
class OperationIntentHypothesis:
    """Untrusted lexical evidence; never grants permission to execute a tool."""

    operation: OperationKind | None
    reason: IntentReason
    matched_operations: tuple[OperationKind, ...]

    @property
    def abstained(self) -> bool:
        return self.operation is None


def infer_operation_intent(query: str) -> OperationIntentHypothesis:
    """High-precision, low-coverage EN/KO/JA baseline with explicit abstention.

    This is purposefully separate from the trusted declared-operation gate.
    Do NOT automatically turn this hypothesis into execution authorization.
    """
    if not isinstance(query, str):
        raise TypeError("operation intent query must be a string")
    stripped = query.strip()
    if not stripped:
        return OperationIntentHypothesis(None, "empty_query", ())
    if len(stripped) > 8192:
        return OperationIntentHypothesis(None, "oversized_query", ())
    matches = tuple(
        kind for kind, expressions in _COMPILED.items()
        if any(pattern.search(stripped) for pattern in expressions)
    )
    if _NEGATED_OR_EXPLANATORY.search(stripped):
        return OperationIntentHypothesis(None, "negated_or_explanatory", matches)
    if not matches:
        return OperationIntentHypothesis(None, "missing_operation", ())
    if len(matches) > 1:
        return OperationIntentHypothesis(None, "ambiguous_operations", matches)
    return OperationIntentHypothesis(matches[0], "explicit_single_operation", matches)
