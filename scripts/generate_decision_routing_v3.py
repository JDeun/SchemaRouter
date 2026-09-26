"""Generate the deterministic 600-case decision-routing v3 untouched holdout."""

from __future__ import annotations

import json
import re
from pathlib import Path

from generate_decision_routing_v2 import CONFIG

WRAPPERS = json.loads(r'''{
  "en": [
    "Could you handle this request: {core}",
    "What I am trying to do is {core}",
    "Please use the appropriate capability to {core}",
    "I only need you to {core}",
    "For the next step, {core}"
  ],
  "ko": [
    "이 요청만 처리해줘: {core}",
    "내가 하려는 건 {core}",
    "적절한 기능을 사용해서 {core}",
    "다른 건 필요 없고 {core}",
    "다음 단계로 {core}"
  ],
  "es": [
    "Gestiona solo esta solicitud: {core}",
    "Lo que intento hacer es {core}",
    "Usa la capacidad adecuada para {core}",
    "Solo necesito que {core}",
    "Como siguiente paso, {core}"
  ],
  "ja": [
    "この依頼だけ処理して: {core}",
    "やりたいことは{core}",
    "適切な機能を使って{core}",
    "必要なのは{core}だけ",
    "次の手順として{core}"
  ],
  "de": [
    "Bearbeite nur diese Anfrage: {core}",
    "Ich möchte Folgendes tun: {core}",
    "Nutze die passende Funktion, um {core}",
    "Ich brauche nur, dass du {core}",
    "Als nächsten Schritt: {core}"
  ],
  "mixed": [
    "이 request만 처리해: {core}",
    "내가 하려는 task는 {core}",
    "appropriate capability로 {core}",
    "다른 건 필요 없고 just {core}",
    "next step으로 {core}"
  ]
}''')

def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    languages = CONFIG["languages"]
    for route in CONFIG["routes"]:
        route_id = route["route"].replace(".", "-").replace("_", "-")
        for language_index, language in enumerate(languages):
            for index in range(5):
                values = route["values"]
                value = values[(index * 2 + language_index + 3) % len(values)]
                core = route["cores"][language].replace("{v}", value)
                cases.append({
                    "id": f"v3-{route_id}-{language}-{index + 1:02d}",
                    "query": WRAPPERS[language][index].replace("{core}", core),
                    "expected": route["route"],
                    "category": (
                        "natural_paraphrase" if index == 0 else
                        "indirect" if index == 1 else
                        "long_tail" if index == 2 else
                        "distractor" if index == 3 else
                        "held_out_paraphrase"
                    ),
                    "expect_abstain": False,
                    "split": "test",
                    "language": language,
                })
    for language in languages:
        for core_index, core in enumerate(CONFIG["unsupported"][language]):
            for index in range(5):
                cases.append({
                    "id": f"v3-no-route-{language}-{core_index + 1}-{index + 1:02d}",
                    "query": WRAPPERS[language][index].replace("{core}", core),
                    "expected": None,
                    "category": (
                        "out_of_domain" if index < 3
                        else "adversarial_or_out_of_domain"
                    ),
                    "expect_abstain": True,
                    "split": "test",
                    "language": language,
                })
    return cases

def _normalize(query: str) -> str:
    return re.sub(r"[^\w]+", "", query.casefold())

def validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 600:
        raise ValueError(f"expected 600 cases, got {len(cases)}")
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case IDs")
    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized v3 query")

def main() -> None:
    cases = build()
    validate(cases)
    destination = Path("benchmarks/decision-routing-v3.json")
    destination.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} cases to {destination}")

if __name__ == "__main__":
    main()
