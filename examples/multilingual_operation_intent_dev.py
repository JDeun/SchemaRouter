"""Conservative multilingual operation-intent *diagnostics*, not execution.

Run: python examples/multilingual_operation_intent_dev.py

Never automatically construct DeclaredOperationFitPolicy from this untrusted
text classifier. The host must independently verify intent and authorization.
"""
from schemarouter import infer_operation_intent


def main() -> None:
    queries = [
        "환율을 엔화로 환산해주세요",
        "為替レートの履歴を表示してください",
        "Delete the inventory record",
        "Please don't delete any records",
        "검색한 뒤에 삭제해주세요",
        "What does delete mean?",
        "날씨를 알려주세요",
    ]
    for query in queries:
        result = infer_operation_intent(query)
        print({
            "query": query,
            "hypothesis": result.operation,
            "abstained": result.abstained,
            "reason": result.reason,
        })
    print("Advisory only — no tool call, policy creation, or authorization.")


if __name__ == "__main__":
    main()
