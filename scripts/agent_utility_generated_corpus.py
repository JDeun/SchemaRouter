"""Deterministic task authoring helpers for the 0.14 downstream conveyor.

The functions in this module are pure authoring logic. Workflows may call them
only after the canonical B2 run has completed successfully.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.agent_utility_generated_common import (
    build_extended_registry,
    sha256_json,
    static_ranked_routes,
)

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
RECIPIENT = "analyst@example.org"


def _pick(language: str, values: dict[str, str]) -> str:
    try:
        return values[language]
    except KeyError as exc:
        raise ValueError(f"unsupported language: {language}") from exc


def _tagged(language: str, tag: str, body: str) -> str:
    prefix = {
        "en": f"Case {tag}. ",
        "ko": f"사례 {tag}. ",
        "es": f"Caso {tag}. ",
        "ja": f"ケース {tag}。 ",
        "de": f"Fall {tag}. ",
        "mixed": f"Case {tag} / 사례. ",
    }[language]
    return prefix + body


def _q_material_search_current(language: str, tag: str, topic: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Search material records for {topic}, then use the returned material identifier "
                "to obtain its current Young's modulus in GPa."
            ),
            "ko": (
                f"{topic} 재료 레코드를 검색한 뒤, 반환된 재료 식별자를 사용해 현재 영률을 "
                "GPa 단위로 조회하세요."
            ),
            "es": (
                f"Busca registros de material para {topic} y usa el identificador devuelto para "
                "obtener el módulo de Young actual en GPa."
            ),
            "ja": (
                f"{topic} の材料レコードを検索し、返された材料識別子を使って現在のヤング率を"
                " GPa で取得してください。"
            ),
            "de": (
                f"Suche Materialdatensätze zu {topic} und verwende die zurückgegebene Material-ID, "
                "um den aktuellen Young-Modul in GPa abzurufen."
            ),
            "mixed": (
                f"{topic} material record를 search한 뒤 returned material ID로 current Young's "
                "modulus를 GPa로 조회하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_paper_search_retrieve(language: str, tag: str, topic: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Search scientific papers about {topic}, then retrieve the selected paper using "
                "the paper identifier returned by the search."
            ),
            "ko": (
                f"{topic} 관련 과학 논문을 검색하고, 검색 결과에서 반환된 논문 식별자로 선택된 "
                "논문을 조회하세요."
            ),
            "es": (
                f"Busca artículos científicos sobre {topic} y recupera el artículo seleccionado "
                "con el identificador devuelto por la búsqueda."
            ),
            "ja": (
                f"{topic} に関する科学論文を検索し、検索で返された論文識別子を使って選択された"
                "論文を取得してください。"
            ),
            "de": (
                f"Suche wissenschaftliche Arbeiten zu {topic} und rufe die ausgewählte Arbeit mit "
                "der von der Suche gelieferten Paper-ID ab."
            ),
            "mixed": (
                f"{topic} 관련 paper를 search하고, returned paper ID로 selected paper를 retrieve하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_paper_search_retrieve_summary(language: str, tag: str, topic: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Search for a scientific paper about {topic}, retrieve the selected paper using "
                "the returned identifier, and then summarize that paper."
            ),
            "ko": (
                f"{topic} 관련 논문을 검색하고 반환된 식별자로 선택 논문을 조회한 다음 그 논문을 "
                "요약하세요."
            ),
            "es": (
                f"Busca un artículo científico sobre {topic}, recupera el seleccionado con el "
                "identificador devuelto y después resúmelo."
            ),
            "ja": (
                f"{topic} の論文を検索し、返された識別子で選択論文を取得してから、その論文を"
                "要約してください。"
            ),
            "de": (
                f"Suche eine wissenschaftliche Arbeit zu {topic}, rufe die ausgewählte Arbeit mit "
                "der zurückgegebenen ID ab und fasse sie anschließend zusammen."
            ),
            "mixed": (
                f"{topic} paper를 search → returned ID로 retrieve → 그 paper를 summarize하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_material_search_retrieve_export(language: str, tag: str, topic: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Search material records for {topic}, retrieve the selected material using the "
                "returned identifier, then export the resulting artifact."
            ),
            "ko": (
                f"{topic} 재료를 검색하고 반환된 식별자로 선택 재료를 조회한 뒤 생성된 아티팩트를 "
                "내보내세요."
            ),
            "es": (
                f"Busca materiales para {topic}, recupera el material seleccionado con el "
                "identificador devuelto y exporta el artefacto resultante."
            ),
            "ja": (
                f"{topic} の材料を検索し、返された識別子で選択材料を取得して、生成された"
                "アーティファクトをエクスポートしてください。"
            ),
            "de": (
                f"Suche Materialien zu {topic}, rufe das ausgewählte Material mit der "
                "zurückgegebenen ID ab und exportiere anschließend das erzeugte Artefakt."
            ),
            "mixed": (
                f"{topic} material search → returned ID로 retrieve → resulting artifact를 export하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_material_retrieve_export(language: str, tag: str, material_id: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Retrieve material {material_id}, then export the artifact produced by that "
                "material record."
            ),
            "ko": f"재료 {material_id}를 조회한 뒤 그 재료 레코드에서 생성된 아티팩트를 내보내세요.",
            "es": (
                f"Recupera el material {material_id} y exporta el artefacto producido por ese "
                "registro."
            ),
            "ja": f"材料 {material_id} を取得し、その材料レコードから生成されたアーティファクトをエクスポートしてください。",
            "de": (
                f"Rufe Material {material_id} ab und exportiere anschließend das von diesem "
                "Materialdatensatz erzeugte Artefakt."
            ),
            "mixed": f"material {material_id}를 retrieve한 뒤 produced artifact를 export하세요.",
        },
    )
    return _tagged(language, tag, body)


def _q_credit_create_share(language: str, tag: str, amount: int) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Create a research-credit request for {amount} credits, then share the returned "
                f"artifact with {RECIPIENT}."
            ),
            "ko": (
                f"{amount} 크레딧의 연구 크레딧 요청을 만들고, 반환된 아티팩트를 {RECIPIENT}와 "
                "공유하세요."
            ),
            "es": (
                f"Crea una solicitud de {amount} créditos de investigación y comparte el artefacto "
                f"devuelto con {RECIPIENT}."
            ),
            "ja": (
                f"{amount} 研究クレジットの申請を作成し、返されたアーティファクトを "
                f"{RECIPIENT} と共有してください。"
            ),
            "de": (
                f"Erstelle eine Forschungskreditanfrage über {amount} Credits und teile das "
                f"zurückgegebene Artefakt mit {RECIPIENT}."
            ),
            "mixed": (
                f"{amount} research credit request를 create하고 returned artifact를 "
                f"{RECIPIENT}와 share하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_inventory_create_send(language: str, tag: str, item_name: str) -> str:
    body = _pick(
        language,
        {
            "en": (
                f"Create laboratory inventory item {item_name}, then send {RECIPIENT} a confirmation "
                "message that contains the returned item identifier."
            ),
            "ko": (
                f"실험실 재고 항목 {item_name}을 만들고, 반환된 항목 식별자가 포함된 확인 메시지를 "
                f"{RECIPIENT}에게 보내세요."
            ),
            "es": (
                f"Crea el artículo de inventario {item_name} y envía a {RECIPIENT} un mensaje de "
                "confirmación que incluya el identificador devuelto."
            ),
            "ja": (
                f"研究室在庫項目 {item_name} を作成し、返された項目識別子を含む確認メッセージを "
                f"{RECIPIENT} に送信してください。"
            ),
            "de": (
                f"Erstelle den Laborbestandseintrag {item_name} und sende {RECIPIENT} eine "
                "Bestätigung mit der zurückgegebenen Artikel-ID."
            ),
            "mixed": (
                f"inventory item {item_name}을 create하고 returned item ID를 포함한 confirmation을 "
                f"{RECIPIENT}에게 send하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_current_then(language: str, tag: str, material_id: str, target: str) -> str:
    target_text = {
        "history": {
            "en": "historical values",
            "ko": "과거 값",
            "es": "valores históricos",
            "ja": "履歴値",
            "de": "historische Werte",
            "mixed": "history values",
        },
        "forecast": {
            "en": "forecast values",
            "ko": "예측 값",
            "es": "valores pronosticados",
            "ja": "予測値",
            "de": "Prognosewerte",
            "mixed": "forecast values",
        },
    }[target][language]
    body = _pick(
        language,
        {
            "en": (
                f"Read the current Young's modulus for material {material_id} in GPa, then obtain "
                f"its {target_text}."
            ),
            "ko": (
                f"재료 {material_id}의 현재 영률을 GPa 단위로 읽은 뒤 같은 재료의 {target_text}을 "
                "조회하세요."
            ),
            "es": (
                f"Obtén el módulo de Young actual de {material_id} en GPa y después sus "
                f"{target_text}."
            ),
            "ja": (
                f"材料 {material_id} の現在のヤング率を GPa で取得し、その後に同じ材料の "
                f"{target_text}を取得してください。"
            ),
            "de": (
                f"Lies den aktuellen Young-Modul von Material {material_id} in GPa und rufe danach "
                f"die {target_text} ab."
            ),
            "mixed": (
                f"material {material_id}의 current Young's modulus를 GPa로 읽고 then "
                f"{target_text}를 조회하세요."
            ),
        },
    )
    return _tagged(language, tag, body)


def _q_direct(language: str, tag: str, route: str, value: str) -> str:
    templates: dict[str, dict[str, str]] = {
        "materials.current": {
            "en": f"Get the current Young's modulus in GPa for material {value}.",
            "ko": f"재료 {value}의 현재 영률을 GPa 단위로 조회하세요.",
            "es": f"Obtén el módulo de Young actual en GPa del material {value}.",
            "ja": f"材料 {value} の現在のヤング率を GPa で取得してください。",
            "de": f"Rufe den aktuellen Young-Modul in GPa für Material {value} ab.",
            "mixed": f"material {value}의 current Young's modulus를 GPa로 get하세요.",
        },
        "materials.history": {
            "en": f"Get historical Young's modulus values for material {value}.",
            "ko": f"재료 {value}의 과거 영률 값을 조회하세요.",
            "es": f"Obtén los valores históricos del módulo de Young del material {value}.",
            "ja": f"材料 {value} の過去のヤング率を取得してください。",
            "de": f"Rufe historische Young-Modul-Werte für Material {value} ab.",
            "mixed": f"material {value}의 historical Young's modulus values를 get하세요.",
        },
        "materials.forecast": {
            "en": f"Forecast future Young's modulus values for material {value}.",
            "ko": f"재료 {value}의 향후 영률 값을 예측하세요.",
            "es": f"Pronostica los valores futuros del módulo de Young del material {value}.",
            "ja": f"材料 {value} の将来のヤング率を予測してください。",
            "de": f"Prognostiziere zukünftige Young-Modul-Werte für Material {value}.",
            "mixed": f"material {value}의 future Young's modulus values를 forecast하세요.",
        },
        "papers.retrieve": {
            "en": f"Retrieve scientific paper {value} by its identifier.",
            "ko": f"식별자 {value}로 과학 논문을 조회하세요.",
            "es": f"Recupera el artículo científico {value} por su identificador.",
            "ja": f"識別子 {value} の科学論文を取得してください。",
            "de": f"Rufe die wissenschaftliche Arbeit {value} über ihre ID ab.",
            "mixed": f"paper ID {value}로 scientific paper를 retrieve하세요.",
        },
        "papers.summarize": {
            "en": f"Summarize scientific paper {value}.",
            "ko": f"과학 논문 {value}를 요약하세요.",
            "es": f"Resume el artículo científico {value}.",
            "ja": f"科学論文 {value} を要約してください。",
            "de": f"Fasse die wissenschaftliche Arbeit {value} zusammen.",
            "mixed": f"scientific paper {value}를 summarize하세요.",
        },
        "inventory.update": {
            "en": f"Update laboratory inventory item {value}; do not delete it.",
            "ko": f"실험실 재고 항목 {value}를 수정하세요. 삭제하지 마세요.",
            "es": f"Actualiza el artículo de inventario {value}; no lo elimines.",
            "ja": f"研究室在庫項目 {value} を更新してください。削除しないでください。",
            "de": f"Aktualisiere den Laborbestandseintrag {value}; lösche ihn nicht.",
            "mixed": f"inventory item {value}을 update하세요; delete하지 마세요.",
        },
        "inventory.delete": {
            "en": f"Permanently delete laboratory inventory item {value}.",
            "ko": f"실험실 재고 항목 {value}를 영구 삭제하세요.",
            "es": f"Elimina permanentemente el artículo de inventario {value}.",
            "ja": f"研究室在庫項目 {value} を完全に削除してください。",
            "de": f"Lösche den Laborbestandseintrag {value} dauerhaft.",
            "mixed": f"inventory item {value}을 permanently delete하세요.",
        },
        "runtime.restart": {
            "en": f"Restart registered workflow runtime {value}.",
            "ko": f"등록된 워크플로 런타임 {value}를 재시작하세요.",
            "es": f"Reinicia el runtime de flujo registrado {value}.",
            "ja": f"登録済みワークフローランタイム {value} を再起動してください。",
            "de": f"Starte die registrierte Workflow-Laufzeit {value} neu.",
            "mixed": f"registered workflow runtime {value}를 restart하세요.",
        },
    }
    if route not in templates:
        raise ValueError(route)
    return _tagged(language, tag, templates[route][language])


def _q_unsupported(language: str, tag: str, kind: str, value: str) -> str:
    if kind == "missing":
        body = _pick(
            language,
            {
                "en": f"Use the registered neutron-diffraction refinement service for sample {value}.",
                "ko": f"시료 {value}에 등록된 중성자 회절 정련 서비스를 사용하세요.",
                "es": f"Usa el servicio registrado de refinamiento por difracción de neutrones para {value}.",
                "ja": f"試料 {value} に登録済みの中性子回折リファインメントサービスを使用してください。",
                "de": f"Nutze den registrierten Neutronenbeugungs-Verfeinerungsdienst für Probe {value}.",
                "mixed": f"sample {value}에 registered neutron-diffraction refinement service를 사용하세요.",
            },
        )
    elif kind == "insufficient":
        body = _pick(
            language,
            {
                "en": "Refund the research credit, but no credit identifier is available.",
                "ko": "연구 크레딧을 환불하세요. 단, 크레딧 식별자는 제공되지 않았습니다.",
                "es": "Reembolsa el crédito de investigación, pero no se proporciona ningún identificador.",
                "ja": "研究クレジットを返金してください。ただしクレジット識別子は提供されていません。",
                "de": "Erstatte den Forschungskredit, aber es ist keine Kredit-ID angegeben.",
                "mixed": "research credit를 refund해야 하지만 credit ID는 제공되지 않았습니다.",
            },
        )
    else:
        body = _pick(
            language,
            {
                "en": f"Reserve a restaurant table for {value} tonight.",
                "ko": f"오늘 밤 {value} 이름으로 식당 좌석을 예약하세요.",
                "es": f"Reserva una mesa de restaurante para {value} esta noche.",
                "ja": f"今夜 {value} 名義でレストランの席を予約してください。",
                "de": f"Reserviere heute Abend einen Restauranttisch für {value}.",
                "mixed": f"오늘 밤 restaurant table을 {value} 이름으로 reserve하세요.",
            },
        )
    return _tagged(language, tag, body)


def _step(
    route_id: str,
    argument_rules: dict[str, dict[str, Any]],
    observation: dict[str, Any],
    *,
    fail_once_error: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "route_id": route_id,
        "argument_rules": argument_rules,
        "observation": observation,
    }
    if fail_once_error is not None:
        row["fail_once_error"] = fail_once_error
    return row


def _base_values(index: int) -> dict[str, Any]:
    return {
        "tag": f"{index:04d}",
        "topic": f"novel-electrolyte-series-{index:04d}",
        "material_id": f"MAT-H{index:04d}",
        "paper_id": f"P-H{index:04d}",
        "item_id": f"INV-H{index:04d}",
        "item_name": f"sample-holder-{index:04d}",
        "credit_id": f"CR-H{index:04d}",
        "runtime_id": f"RT-H{index:04d}",
        "artifact_id": f"ART-H{index:04d}",
        "amount": 100 + (index % 37),
    }


def _scenario(
    scenario: str,
    *,
    language: str,
    index: int,
    fail_once: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    v = _base_values(index)
    tag = v["tag"]

    if scenario == "material_search_current":
        material = f"MAT-SEARCH-H{index:04d}"
        query = _q_material_search_current(language, tag, v["topic"])
        steps = [
            _step(
                "materials.search",
                {"query": {"nonempty": True}},
                {"status": "ok", "material_id": material, "formula": f"X{index}Y"},
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "materials.current",
                {"material_id": {"state": "material_id"}},
                {
                    "status": "ok",
                    "youngs_modulus": 110.0 + (index % 41),
                    "unit": "GPa",
                },
            ),
        ]
        return query, steps

    if scenario == "paper_search_retrieve":
        paper = f"P-SEARCH-H{index:04d}"
        query = _q_paper_search_retrieve(language, tag, v["topic"])
        steps = [
            _step(
                "papers.search",
                {"query": {"nonempty": True}},
                {"status": "ok", "paper_id": paper, "title": f"Paper {index}"},
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "papers.retrieve",
                {"paper_id": {"state": "paper_id"}},
                {
                    "status": "ok",
                    "paper_id": paper,
                    "paper_text": f"Independent deterministic evidence {index}.",
                },
            ),
        ]
        return query, steps

    if scenario == "paper_search_retrieve_summary":
        paper = f"P-SEARCH-H{index:04d}"
        query = _q_paper_search_retrieve_summary(language, tag, v["topic"])
        steps = [
            _step(
                "papers.search",
                {"query": {"nonempty": True}},
                {"status": "ok", "paper_id": paper, "title": f"Paper {index}"},
            ),
            _step(
                "papers.retrieve",
                {"paper_id": {"state": "paper_id"}},
                {
                    "status": "ok",
                    "paper_id": paper,
                    "paper_text": f"Independent deterministic paper content {index}.",
                },
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "papers.summarize",
                {"paper_id": {"state": "paper_id"}},
                {"status": "ok", "summary": f"Independent summary {index}."},
            ),
        ]
        return query, steps

    if scenario == "material_search_retrieve_export":
        material = f"MAT-SEARCH-H{index:04d}"
        artifact = f"ART-MAT-H{index:04d}"
        query = _q_material_search_retrieve_export(language, tag, v["topic"])
        steps = [
            _step(
                "materials.search",
                {"query": {"nonempty": True}},
                {"status": "ok", "material_id": material, "formula": f"M{index}N"},
            ),
            _step(
                "materials.retrieve",
                {"material_id": {"state": "material_id"}},
                {
                    "status": "ok",
                    "material_id": material,
                    "formula": f"M{index}N",
                    "artifact_id": artifact,
                },
            ),
            _step(
                "exports.export",
                {"artifact_id": {"state": "artifact_id"}},
                {"status": "ok", "file_uri": f"file:///tmp/{artifact}.json"},
                fail_once_error="transient_backend" if fail_once else None,
            ),
        ]
        return query, steps

    if scenario == "material_retrieve_export":
        artifact = f"ART-MAT-H{index:04d}"
        query = _q_material_retrieve_export(language, tag, v["material_id"])
        steps = [
            _step(
                "materials.retrieve",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "material_id": v["material_id"],
                    "formula": f"Q{index}R",
                    "artifact_id": artifact,
                },
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "exports.export",
                {"artifact_id": {"state": "artifact_id"}},
                {"status": "ok", "file_uri": f"file:///tmp/{artifact}.json"},
            ),
        ]
        return query, steps

    if scenario == "credit_create_share":
        artifact = f"ART-CREDIT-H{index:04d}"
        query = _q_credit_create_share(language, tag, int(v["amount"]))
        steps = [
            _step(
                "credits.create",
                {"amount": {"eq": v["amount"]}},
                {
                    "status": "ok",
                    "credit_id": f"CR-NEW-H{index:04d}",
                    "artifact_id": artifact,
                },
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "messaging.share",
                {
                    "artifact_id": {"state": "artifact_id"},
                    "recipient": {"eq": RECIPIENT},
                },
                {"status": "ok", "share_id": f"SHARE-H{index:04d}"},
            ),
        ]
        return query, steps

    if scenario == "inventory_create_send":
        item_id = f"INV-NEW-H{index:04d}"
        query = _q_inventory_create_send(language, tag, v["item_name"])
        steps = [
            _step(
                "inventory.create",
                {"item_name": {"eq": v["item_name"]}},
                {"status": "ok", "item_id": item_id},
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                "messaging.send",
                {
                    "recipient": {"eq": RECIPIENT},
                    "message": {"contains_state": "item_id"},
                },
                {"status": "ok", "message_id": f"MSG-H{index:04d}"},
            ),
        ]
        return query, steps

    if scenario in {"current_history", "current_forecast"}:
        target = "history" if scenario == "current_history" else "forecast"
        second_route = f"materials.{target}"
        query = _q_current_then(language, tag, v["material_id"], target)
        first_value = 115.0 + (index % 31)
        second_value: Any = (
            [first_value - 2.0, first_value - 1.0, first_value]
            if target == "history"
            else [first_value + 1.0, first_value + 2.0]
        )
        steps = [
            _step(
                "materials.current",
                {"material_id": {"eq": v["material_id"]}},
                {"status": "ok", "youngs_modulus": first_value, "unit": "GPa"},
                fail_once_error="transient_backend" if fail_once else None,
            ),
            _step(
                second_route,
                {"material_id": {"eq": v["material_id"]}},
                {"status": "ok", "youngs_modulus": second_value, "unit": "GPa"},
            ),
        ]
        return query, steps

    if scenario.startswith("direct:"):
        route = scenario.split(":", 1)[1]
        value_key = {
            "materials.current": "material_id",
            "materials.history": "material_id",
            "materials.forecast": "material_id",
            "papers.retrieve": "paper_id",
            "papers.summarize": "paper_id",
            "inventory.update": "item_id",
            "inventory.delete": "item_id",
            "runtime.restart": "runtime_id",
        }[route]
        value = str(v[value_key])
        parameter = {
            "materials.current": "material_id",
            "materials.history": "material_id",
            "materials.forecast": "material_id",
            "papers.retrieve": "paper_id",
            "papers.summarize": "paper_id",
            "inventory.update": "item_id",
            "inventory.delete": "item_id",
            "runtime.restart": "runtime_id",
        }[route]
        query = _q_direct(language, tag, route, value)
        observations: dict[str, dict[str, Any]] = {
            "materials.current": {
                "status": "ok",
                "youngs_modulus": 120.0 + (index % 17),
                "unit": "GPa",
            },
            "materials.history": {
                "status": "ok",
                "youngs_modulus": [118.0, 119.0, 120.0],
                "unit": "GPa",
            },
            "materials.forecast": {
                "status": "ok",
                "youngs_modulus": [121.0, 122.0],
                "unit": "GPa",
            },
            "papers.retrieve": {
                "status": "ok",
                "paper_id": value,
                "paper_text": f"Independent paper evidence {index}.",
            },
            "papers.summarize": {
                "status": "ok",
                "summary": f"Independent summary evidence {index}.",
            },
            "inventory.update": {"status": "ok", "item_id": value},
            "inventory.delete": {"status": "ok", "deleted_item_id": value},
            "runtime.restart": {"status": "ok", "runtime_id": value, "state": "running"},
        }
        return query, [
            _step(
                route,
                {parameter: {"eq": value}},
                observations[route],
                fail_once_error="transient_backend" if fail_once else None,
            )
        ]

    raise ValueError(f"unknown scenario: {scenario}")


def build_corrective_task(slot: dict[str, Any], index: int) -> dict[str, Any]:
    stratum = str(slot["task_stratum"])
    ordinal = int(slot["ordinal_in_cell"])
    scenarios = {
        "two_step_state_dependency": (
            "material_search_current",
            "paper_search_retrieve",
            "credit_create_share",
            "inventory_create_send",
            "material_retrieve_export",
            "current_history",
        ),
        "three_step_state_dependency": (
            "paper_search_retrieve_summary",
            "material_search_retrieve_export",
        ),
        "recoverable_execution_failure": (
            "material_search_current",
            "paper_search_retrieve_summary",
            "material_retrieve_export",
            "credit_create_share",
            "inventory_create_send",
            "current_forecast",
        ),
        "identifier_provenance_propagation": (
            "material_retrieve_export",
            "credit_create_share",
            "inventory_create_send",
        ),
        "typed_unit_state_transition": (
            "current_history",
            "current_forecast",
        ),
    }
    scenario = scenarios[stratum][(ordinal - 1) % len(scenarios[stratum])]
    query, steps = _scenario(
        scenario,
        language=str(slot["language"]),
        index=index,
        fail_once=stratum == "recoverable_execution_failure",
    )
    required = list(dict.fromkeys(str(step["route_id"]) for step in steps))
    return {
        "semantic_task_id": slot["semantic_task_id"],
        "task_stratum": stratum,
        "language": slot["language"],
        "query": query,
        "supported": True,
        "required_routes": required,
        "executor_fixture": {"steps": steps},
        "expected_outcome": {"complete": True},
    }


def build_heldout_task(slot: dict[str, Any], index: int) -> dict[str, Any]:
    stratum = str(slot["task_stratum"])
    ordinal = int(slot["ordinal_in_cell"])
    language = str(slot["language"])

    scenario_map = {
        "single_tool_exact": (
            "direct:materials.current",
            "direct:papers.retrieve",
            "direct:inventory.update",
            "direct:runtime.restart",
        ),
        "two_step_state_dependent": (
            "material_search_current",
            "paper_search_retrieve",
            "credit_create_share",
            "inventory_create_send",
        ),
        "three_step_state_dependent": (
            "paper_search_retrieve_summary",
            "material_search_retrieve_export",
        ),
        "sibling_operation_ambiguity": (
            "direct:materials.current",
            "direct:materials.history",
            "direct:materials.forecast",
            "direct:papers.retrieve",
            "direct:papers.summarize",
        ),
        "typed_numeric_units": (
            "direct:materials.current",
            "direct:materials.history",
            "direct:materials.forecast",
            "current_history",
            "current_forecast",
        ),
        "identifier_provenance_propagation": (
            "material_retrieve_export",
            "credit_create_share",
            "inventory_create_send",
        ),
        "read_vs_write_siblings": (
            "direct:inventory.update",
            "direct:materials.current",
            "direct:runtime.restart",
        ),
        "destructive_vs_non_destructive_siblings": (
            "direct:inventory.update",
            "direct:inventory.delete",
        ),
        "recoverable_execution_failure": (
            "material_search_current",
            "paper_search_retrieve_summary",
            "material_retrieve_export",
            "credit_create_share",
            "inventory_create_send",
        ),
        "semantically_adjacent_distractors": (
            "direct:materials.forecast",
            "direct:papers.summarize",
            "material_search_current",
            "paper_search_retrieve",
        ),
    }

    if stratum in {"insufficient_information", "missing_capability_unsupported", "out_of_domain"}:
        kind = {
            "insufficient_information": "insufficient",
            "missing_capability_unsupported": "missing",
            "out_of_domain": "ood",
        }[stratum]
        query = _q_unsupported(language, f"{index:04d}", kind, f"U{index:04d}")
        return {
            "semantic_task_id": slot["semantic_task_id"],
            "task_stratum": stratum,
            "language": language,
            "query": query,
            "supported": False,
            "required_routes": [],
            "executor_fixture": {"steps": []},
            "expected_outcome": {"complete": False, "unsupported": True},
        }

    scenario = scenario_map[stratum][(ordinal - 1) % len(scenario_map[stratum])]
    query, steps = _scenario(
        scenario,
        language=language,
        index=index,
        fail_once=stratum == "recoverable_execution_failure",
    )
    required = list(dict.fromkeys(str(step["route_id"]) for step in steps))
    return {
        "semantic_task_id": slot["semantic_task_id"],
        "task_stratum": stratum,
        "language": language,
        "query": query,
        "supported": True,
        "required_routes": required,
        "executor_fixture": {"steps": steps},
        "expected_outcome": {"complete": True},
    }


def _fact(
    key: str,
    value: Any,
    source_id: str,
    *,
    unit: str | None = None,
) -> dict[str, Any]:
    return {"key": key, "value": value, "unit": unit, "source_id": source_id}


def build_final_task(slot: dict[str, Any], index: int) -> dict[str, Any]:
    stratum = str(slot["answer_task_stratum"])
    language = str(slot["language"])
    v = _base_values(index)
    source_a = f"SRC-F{index:04d}-A"
    source_b = f"SRC-F{index:04d}-B"

    if stratum == "single_property_value_unit_provenance":
        query = _q_direct(language, f"F{index:04d}", "materials.current", v["material_id"])
        value = 130.0 + (index % 23)
        steps = [
            _step(
                "materials.current",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "youngs_modulus": value,
                    "unit": "GPa",
                    "source_id": source_a,
                },
            )
        ]
        required_facts = [_fact("youngs_modulus", value, source_a, unit="GPa")]
        tolerances = {"youngs_modulus": {"absolute": 0.01}}
        accepted_units = {"youngs_modulus": ["GPa"]}
        evidence = [{"source_id": source_a, "payload": steps[0]["observation"]}]

    elif stratum == "literature_fact_with_source_attribution":
        query = _q_direct(language, f"F{index:04d}", "papers.retrieve", v["paper_id"])
        text = f"Frozen literature fact {index}: stability index {index % 97}."
        steps = [
            _step(
                "papers.retrieve",
                {"paper_id": {"eq": v["paper_id"]}},
                {
                    "status": "ok",
                    "paper_id": v["paper_id"],
                    "paper_text": text,
                    "source_id": source_a,
                },
            )
        ]
        required_facts = [_fact("paper_text", text, source_a)]
        tolerances = {}
        accepted_units = {}
        evidence = [{"source_id": source_a, "payload": steps[0]["observation"]}]

    elif stratum == "multi_source_comparison":
        query = _q_current_then(language, f"F{index:04d}", v["material_id"], "history")
        current = 120.0 + (index % 19)
        history = [current - 2.0, current - 1.0, current]
        steps = [
            _step(
                "materials.current",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "current_youngs_modulus": current,
                    "unit": "GPa",
                    "source_id": source_a,
                },
            ),
            _step(
                "materials.history",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "historical_youngs_modulus": history,
                    "unit": "GPa",
                    "source_id": source_b,
                },
            ),
        ]
        required_facts = [
            _fact("current_youngs_modulus", current, source_a, unit="GPa"),
            _fact("historical_youngs_modulus", history, source_b, unit="GPa"),
        ]
        tolerances = {"current_youngs_modulus": {"absolute": 0.01}}
        accepted_units = {
            "current_youngs_modulus": ["GPa"],
            "historical_youngs_modulus": ["GPa"],
        }
        evidence = [
            {"source_id": source_a, "payload": steps[0]["observation"]},
            {"source_id": source_b, "payload": steps[1]["observation"]},
        ]

    elif stratum in {"transform_or_export_then_status_answer", "corrective_expansion_required"}:
        query = _q_material_retrieve_export(language, f"F{index:04d}", v["material_id"])
        artifact = f"ART-F{index:04d}"
        uri = f"file:///tmp/{artifact}.json"
        steps = [
            _step(
                "materials.retrieve",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "material_id": v["material_id"],
                    "artifact_id": artifact,
                    "source_id": source_a,
                },
            ),
            _step(
                "exports.export",
                {"artifact_id": {"state": "artifact_id"}},
                {"status": "ok", "file_uri": uri, "source_id": source_b},
            ),
        ]
        if stratum == "corrective_expansion_required":
            suffix = _pick(
                language,
                {
                    "en": (
                        f" Then restart runtime {v['runtime_id']} and send a completion "
                        f"message to {RECIPIENT}."
                    ),
                    "ko": (
                        f" 이어서 런타임 {v['runtime_id']}를 재시작하고 {RECIPIENT}에게 "
                        "완료 메시지를 보내세요."
                    ),
                    "es": (
                        f" Después reinicia el runtime {v['runtime_id']} y envía un mensaje "
                        f"de finalización a {RECIPIENT}."
                    ),
                    "ja": (
                        f" 続けてランタイム {v['runtime_id']} を再起動し、{RECIPIENT} に"
                        "完了メッセージを送信してください。"
                    ),
                    "de": (
                        f" Starte danach die Runtime {v['runtime_id']} neu und sende eine "
                        f"Abschlussnachricht an {RECIPIENT}."
                    ),
                    "mixed": (
                        f" 이어서 runtime {v['runtime_id']}를 restart하고 {RECIPIENT}에게 "
                        "completion message를 send하세요."
                    ),
                },
            )
            query += suffix
            steps.extend(
                [
                    _step(
                        "runtime.restart",
                        {"runtime_id": {"eq": v["runtime_id"]}},
                        {"status": "ok", "runtime_id": v["runtime_id"], "state": "running"},
                    ),
                    _step(
                        "messaging.send",
                        {
                            "recipient": {"eq": RECIPIENT},
                            "message": {"nonempty": True},
                        },
                        {"status": "ok", "message_id": f"MSG-F{index:04d}"},
                    ),
                ]
            )
        required_facts = [_fact("file_uri", uri, source_b)]
        tolerances = {}
        accepted_units = {}
        evidence = [
            {"source_id": source_a, "payload": steps[0]["observation"]},
            {"source_id": source_b, "payload": steps[1]["observation"]},
        ]

    elif stratum == "distractor_or_contradiction_resistance":
        query = _q_direct(language, f"F{index:04d}", "materials.forecast", v["material_id"])
        forecast = [140.0 + (index % 11), 141.0 + (index % 11)]
        steps = [
            _step(
                "materials.forecast",
                {"material_id": {"eq": v["material_id"]}},
                {
                    "status": "ok",
                    "forecast_youngs_modulus": forecast,
                    "unit": "GPa",
                    "source_id": source_a,
                    "distractor_note": "The historical value is not the requested forecast.",
                },
            )
        ]
        required_facts = [
            _fact("forecast_youngs_modulus", forecast, source_a, unit="GPa")
        ]
        tolerances = {}
        accepted_units = {"forecast_youngs_modulus": ["GPa"]}
        evidence = [{"source_id": source_a, "payload": steps[0]["observation"]}]

    else:
        raise ValueError(stratum)

    required_routes = list(dict.fromkeys(str(step["route_id"]) for step in steps))
    forbidden_facts: list[dict[str, Any]] = []
    if stratum == "distractor_or_contradiction_resistance":
        forbidden_facts = [
            {"key": "forecast_youngs_modulus", "value": [-1.0, -1.0], "source_id": source_a}
        ]

    corrective_contract: dict[str, Any] | None = None
    if stratum == "corrective_expansion_required":
        registry = build_extended_registry(100)
        ranking = static_ranked_routes(registry, query)
        initial_miss = not set(required_routes).issubset(set(ranking[:3]))
        corrective_contract = {
            "initial_candidate_miss": initial_miss,
            "ground_truth_trigger_visible": False,
        }

    return {
        "semantic_task_id": slot["semantic_task_id"],
        "answer_task_stratum": stratum,
        "language": language,
        "query": query,
        "supported": True,
        "required_routes": required_routes,
        "executor_fixture": {"steps": steps},
        "expected_outcome": {"complete": True},
        "evidence_payloads": evidence,
        "allowed_source_ids": [row["source_id"] for row in evidence],
        "required_facts": required_facts,
        "forbidden_facts": forbidden_facts,
        "numeric_tolerances": tolerances,
        "accepted_units": accepted_units,
        "mandatory_answer_fields": [fact["key"] for fact in required_facts],
        "corrective_contract": corrective_contract,
    }


def with_task_hashes(
    *,
    root: dict[str, Any],
    tasks: list[dict[str, Any]],
    condition_manifest: dict[str, Any],
) -> dict[str, Any]:
    root["tasks"] = tasks
    root["tasks_sha256"] = sha256_json(tasks)
    root["candidate_set_manifest_sha256"] = sha256_json(condition_manifest)
    root["condition_manifest"] = condition_manifest
    return root


def source_identity_sha(source_revision: str, plan_sha: str, conditions: dict[str, Any]) -> str:
    payload = {
        "source_revision": source_revision,
        "authoring_slots_sha256": plan_sha,
        "condition_manifest": conditions,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
