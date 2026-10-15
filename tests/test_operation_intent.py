"""No-model multilingual intent baseline regression — DEV, not external validation."""
from __future__ import annotations

import pytest

from schemarouter import infer_operation_intent


@pytest.mark.parametrize(
    ("operation", "english", "korean", "japanese"),
    [
        ("search", "Search papers about graphene",
         "논문을 검색해주세요", "論文を検索してください"),
        ("lookup", "Look up product SKU A-2",
         "SKU A-2의 재고를 조회해주세요", "商品SKU A-2を照会してください"),
        ("list", "List all upcoming meetings",
         "예정된 회의 목록을 보여주세요", "会議の一覧を見せてください"),
        ("history", "Show the currency exchange history",
         "환율 이력을 보여주세요", "為替レートの履歴を表示してください"),
        ("convert", "Convert 220 euros into yen",
         "220유로를 엔화로 환산해주세요", "220ユーロを円に換算してください"),
        ("directions", "Show walking directions to the museum",
         "박물관까지 길찾기 해주세요", "博物館までの道順を教えてください"),
        ("create", "Create a recurring calendar event",
         "반복 일정을 새로 생성해주세요", "繰り返し予定を作成してください"),
        ("update", "Update inventory quantity",
         "재고 수량을 수정해주세요", "在庫数量を更新してください"),
        ("delete", "Delete customer record 33",
         "고객 33번 정보를 삭제해주세요", "顧客情報33を削除してください"),
    ],
)
def test_explicit_operation_in_three_languages(
    operation: str, english: str, korean: str, japanese: str,
) -> None:
    for query in [english, korean, japanese]:
        result = infer_operation_intent(query)
        assert not result.abstained
        assert result.operation == operation
        assert result.reason == "explicit_single_operation"
        assert result.matched_operations == (operation,)


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("please search and delete files", "ambiguous_operations"),
        ("검색하고 삭제해줘", "ambiguous_operations"),
        ("検索して削除してください", "ambiguous_operations"),
        ("Don't delete the user record", "negated_or_explanatory"),
        ("사용자 정보를 삭제하지 마세요", "negated_or_explanatory"),
        ("ユーザーを削除しないでください", "negated_or_explanatory"),
        ("How to delete records?", "negated_or_explanatory"),
        ("파일 삭제 방법 알려줘", "negated_or_explanatory"),
        ("削除方法を教えて", "negated_or_explanatory"),
        ("Summarize the weather forecast", "missing_operation"),
        ("날씨를 알려주세요", "missing_operation"),
        ("今日の天気を教えて", "missing_operation"),
        ("research findings for paper", "missing_operation"),
        ("삭제 이력 조회", "ambiguous_operations"),
        ("calendar list history", "ambiguous_operations"),
        ("file restore", "missing_operation"),
        ("SQL DROP TABLE", "missing_operation"),
        ("이 작업을 실행해줘", "missing_operation"),
        ("remove wrong files without deleting backup", "negated_or_explanatory"),
        ("find results but do not delete data", "negated_or_explanatory"),
        ("조회만 하고 삭제하지 마", "negated_or_explanatory"),
        ("　 ", "empty_query"),
    ],
)
def test_unknown_negative_and_multi_action_abstain(
    query: str, reason: str,
) -> None:
    result = infer_operation_intent(query)
    assert result.abstained
    assert result.operation is None
    assert result.reason == reason


def test_long_input_abstains_without_regex_processing() -> None:
    out = infer_operation_intent("delete " * 2000)
    assert out.abstained
    assert out.reason == "oversized_query"


@pytest.mark.parametrize("bad", [None, 1, False, [], {}])
def test_invalid_input_is_not_cast_to_text(bad: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        infer_operation_intent(bad)  # type: ignore[arg-type]


def test_trilingual_mixed_action_does_not_infer_authority() -> None:
    # This is an advisory hypothesis and cannot construct a policy or call tools.
    out = infer_operation_intent("SKU A-2를 inventory에서 lookup해줘")
    assert out.abstained
    assert out.reason == "missing_operation"
