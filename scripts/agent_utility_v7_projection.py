"""Output-field projection surface for the #506 experiment.

B1 (#420) varied how many *tools* the agent could see. #434 varied how a
capability is *represented for retrieval*. Neither isolates the step this module
measures: SchemaRouter validates a raw tool response and then hands the agent
only the declared fields the plan asked for.

Every condition here receives the same query, the same candidate exposure, the
same route and the same frozen raw record. Only `project_observation` differs.
That keeps the comparison about projection rather than about routing.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from scripts.agent_utility_generated_corpus import LANGUAGES, _pick, _step, _tagged

PROJECTION_CONDITIONS = (
    "RAW-FULL",
    "PROJECTED",
    "PROJECTED+CONTRACT",
    "ORACLE-MINIMAL",
)

# `status` and `error` are transport control, not payload. An agent that cannot
# distinguish a failed call from an empty result would produce answer-quality
# differences that have nothing to do with projection, so they survive in every
# condition.
CONTROL_KEYS = frozenset({"status", "error"})

PROJECTION_STRATA = (
    "qualifier_sibling",
    "unit_variant",
    "superseded_duplicate",
    "nested_record",
    "cross_provider_name_collision",
    "multi_step_provenance",
)

CATALOG_SIZES = (100, 250)
TASKS_PER_CELL = 4


def project_observation(
    observation: dict[str, Any],
    *,
    condition: str,
    planned_fields: Sequence[str],
    gold_fields: Sequence[str],
    field_contracts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the observation as one condition would hand it to the agent.

    Projection only ever removes. A condition that added a key would be
    measuring something other than field projection.
    """
    if condition not in PROJECTION_CONDITIONS:
        raise ValueError(f"unsupported projection condition: {condition}")

    if condition == "RAW-FULL":
        return dict(observation)

    keep = set(gold_fields if condition == "ORACLE-MINIMAL" else planned_fields)
    projected = {
        key: value
        for key, value in observation.items()
        if key in CONTROL_KEYS or key in keep
    }

    if condition == "PROJECTED+CONTRACT":
        contracts = {
            key: value
            for key, value in (field_contracts or {}).items()
            if key in keep and key in observation
        }
        if contracts:
            projected["field_contracts"] = contracts

    return projected


def projection_authoring_slots() -> list[dict[str, Any]]:
    """Frozen slot plan: one preregistered stratum/language cell per task."""
    slots: list[dict[str, Any]] = []
    for stratum in PROJECTION_STRATA:
        for language in LANGUAGES:
            for repeat in range(TASKS_PER_CELL):
                index = len(slots)
                slots.append(
                    {
                        "semantic_task_id": f"P{index:04d}",
                        "projection_stratum": stratum,
                        "language": language,
                        "repeat": repeat,
                    }
                )
    return slots


def _fact(key: str, value: Any, source_id: str, *, unit: str | None = None) -> dict[str, Any]:
    return {"key": key, "value": value, "unit": unit, "source_id": source_id}


def _projected_step(
    route_id: str,
    argument_rules: dict[str, Any],
    observation: dict[str, Any],
    *,
    planned_fields: Iterable[str],
    gold_fields: Iterable[str],
    field_contracts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step = _step(route_id, argument_rules, observation)
    step["planned_fields"] = list(planned_fields)
    step["gold_fields"] = list(gold_fields)
    step["field_contracts"] = dict(field_contracts or {})
    return step


# Query templates per stratum and language. `{id}` is the material identifier.
# Kept as templates rather than f-strings so the multilingual lines stay inside
# the project's 100-column limit.
_QUERY_TEMPLATES: dict[str, dict[str, str]] = {
    "qualifier_sibling": {
        "en": "Report the room-temperature Young's modulus for {id} "
        "with its unit and source.",
        "ko": "{id}의 상온 영률을 단위와 출처와 함께 알려줘.",
        "es": "Indica el módulo de Young a temperatura ambiente de {id} "
        "con unidad y fuente.",
        "ja": "{id} の室温ヤング率を、単位と出典付きで報告してください。",
        "de": "Nenne den Young-Modul von {id} bei Raumtemperatur "
        "mit Einheit und Quelle.",
        "mixed": "{id}의 room-temperature Young's modulus를 "
        "unit과 source와 함께 report해줘.",
    },
    "unit_variant": {
        "en": "Give the Young's modulus of {id} in GPa with its source identifier.",
        "ko": "{id}의 영률을 GPa 단위로, 출처 식별자와 함께 알려줘.",
        "es": "Da el módulo de Young de {id} en GPa con su identificador de fuente.",
        "ja": "{id} のヤング率を GPa 単位で、出典 ID とともに示してください。",
        "de": "Gib den Young-Modul von {id} in GPa mit Quellenkennung an.",
        "mixed": "{id}의 Young's modulus를 GPa로, source id와 함께 알려줘.",
    },
    "superseded_duplicate": {
        "en": "Return the current certified density for {id} with unit and source.",
        "ko": "{id}의 현재 인증 밀도를 단위와 출처와 함께 반환해줘.",
        "es": "Devuelve la densidad certificada actual de {id} con unidad y fuente.",
        "ja": "{id} の現行認証密度を、単位と出典付きで返してください。",
        "de": "Gib die aktuelle zertifizierte Dichte von {id} "
        "mit Einheit und Quelle zurück.",
        "mixed": "{id}의 current certified density를 unit과 source와 함께 return해줘.",
    },
    "nested_record": {
        "en": "Report the measured band gap for {id} with unit and source.",
        "ko": "{id}의 측정된 밴드갭을 단위와 출처와 함께 보고해줘.",
        "es": "Informa la banda prohibida medida de {id} con unidad y fuente.",
        "ja": "{id} の測定バンドギャップを、単位と出典付きで報告してください。",
        "de": "Berichte die gemessene Bandlücke von {id} mit Einheit und Quelle.",
        "mixed": "{id}의 measured band gap을 unit과 source와 함께 report해줘.",
    },
    "cross_provider_name_collision": {
        "en": "Return the certified thermal conductivity for {id} "
        "with unit and source.",
        "ko": "{id}의 인증 열전도율을 단위와 출처와 함께 반환해줘.",
        "es": "Devuelve la conductividad térmica certificada de {id} "
        "con unidad y fuente.",
        "ja": "{id} の認証熱伝導率を、単位と出典付きで返してください。",
        "de": "Gib die zertifizierte Wärmeleitfähigkeit von {id} "
        "mit Einheit und Quelle zurück.",
        "mixed": "{id}의 certified thermal conductivity를 "
        "unit과 source와 함께 return해줘.",
    },
    "multi_step_provenance": {
        "en": "Retrieve {id}, export it, and report the export URI with its source.",
        "ko": "{id}를 조회하고 내보낸 뒤, 내보내기 URI를 출처와 함께 알려줘.",
        "es": "Recupera {id}, expórtalo e informa el URI de exportación con su fuente.",
        "ja": "{id} を取得してエクスポートし、エクスポート URI を出典付きで報告してください。",
        "de": "Rufe {id} ab, exportiere es und melde die Export-URI mit Quelle.",
        "mixed": "{id}를 retrieve하고 export한 뒤 export URI를 source와 함께 report해줘.",
    },
}


def _query(language: str, tag: str, stratum: str, material_id: str) -> str:
    bodies = {
        key: template.format(id=material_id)
        for key, template in _QUERY_TEMPLATES[stratum].items()
    }
    return _tagged(language, tag, _pick(language, bodies))


def build_projection_task(
    slot: dict[str, Any],
    index: int,
    *,
    prefix: str = "P",
) -> dict[str, Any]:
    """Build one frozen task whose raw records carry competing content.

    Each raw observation deliberately contains more than the plan declared. If it
    did not, `RAW-FULL` and `PROJECTED` would be the same observation and the
    experiment would measure nothing.
    """
    stratum = str(slot["projection_stratum"])
    language = str(slot["language"])
    tag = f"{prefix}{index:04d}"
    material_id = f"MAT-{prefix}{index:04d}"
    source_a = f"SRC-{prefix}{index:04d}-A"
    source_b = f"SRC-{prefix}{index:04d}-B"
    query = _query(language, tag, stratum, material_id)

    if stratum == "qualifier_sibling":
        value = 130.0 + (index % 23)
        observation = {
            "status": "ok",
            "youngs_modulus": value,
            "unit": "GPa",
            "source_id": source_a,
            "youngs_modulus_at_77k": round(value * 1.11, 3),
            "youngs_modulus_at_900k": round(value * 0.74, 3),
            "measurement_campaign": f"CAMP-{index % 17:03d}",
        }
        planned = ("youngs_modulus", "unit", "source_id")
        contracts = {
            "youngs_modulus": {
                "semantic_id": "materials.youngs_modulus",
                "unit": "GPa",
                "qualifiers": {"temperature_k": 300},
            }
        }
        steps = [
            _projected_step(
                "materials.current",
                {"material_id": {"eq": material_id}},
                observation,
                planned_fields=planned,
                gold_fields=planned,
                field_contracts=contracts,
            )
        ]
        required_facts = [_fact("youngs_modulus", value, source_a, unit="GPa")]
        tolerances = {"youngs_modulus": {"absolute": 0.01}}
        accepted_units = {"youngs_modulus": ["GPa"]}
        forbidden = [
            {
                "key": "youngs_modulus",
                "value": observation["youngs_modulus_at_900k"],
                "source_id": source_a,
            }
        ]

    elif stratum == "unit_variant":
        value = 118.0 + (index % 19)
        observation = {
            "status": "ok",
            "youngs_modulus": value,
            "unit": "GPa",
            "source_id": source_a,
            "youngs_modulus_mpa": round(value * 1000.0, 3),
            "youngs_modulus_psi": round(value * 145037.7, 1),
            "conversion_note": "Derived columns are provider-side conveniences.",
        }
        planned = ("youngs_modulus", "unit", "source_id")
        contracts = {
            "youngs_modulus": {
                "semantic_id": "materials.youngs_modulus",
                "unit": "GPa",
                "canonical_unit": "GPa",
            }
        }
        steps = [
            _projected_step(
                "materials.current",
                {"material_id": {"eq": material_id}},
                observation,
                planned_fields=planned,
                gold_fields=planned,
                field_contracts=contracts,
            )
        ]
        required_facts = [_fact("youngs_modulus", value, source_a, unit="GPa")]
        tolerances = {"youngs_modulus": {"absolute": 0.01}}
        accepted_units = {"youngs_modulus": ["GPa"]}
        forbidden = [
            {
                "key": "youngs_modulus",
                "value": observation["youngs_modulus_mpa"],
                "source_id": source_a,
            }
        ]

    elif stratum == "superseded_duplicate":
        value = 7.8 + (index % 7) * 0.1
        observation = {
            "status": "ok",
            "density": round(value, 3),
            "unit": "g/cm^3",
            "source_id": source_a,
            "density_legacy_2019": round(value - 0.4, 3),
            "density_draft": round(value + 0.6, 3),
            "record_state": "current",
            "superseded_record_ids": [f"REC-{index % 13:03d}"],
        }
        planned = ("density", "unit", "source_id")
        contracts = {
            "density": {
                "semantic_id": "materials.density",
                "unit": "g/cm^3",
            }
        }
        steps = [
            _projected_step(
                "materials.current",
                {"material_id": {"eq": material_id}},
                observation,
                planned_fields=planned,
                gold_fields=planned,
                field_contracts=contracts,
            )
        ]
        required_facts = [_fact("density", round(value, 3), source_a, unit="g/cm^3")]
        tolerances = {"density": {"absolute": 0.001}}
        accepted_units = {"density": ["g/cm^3"]}
        forbidden = [
            {"key": "density", "value": observation["density_legacy_2019"], "source_id": source_a}
        ]

    elif stratum == "nested_record":
        value = 1.1 + (index % 11) * 0.05
        observation = {
            "status": "ok",
            "band_gap": round(value, 3),
            "unit": "eV",
            "source_id": source_a,
            "record": {
                "material_id": material_id,
                "computed": {
                    "band_gap": round(value + 0.35, 3),
                    "functional": "PBE",
                },
                "audit": {"reviewer": "lab-3", "ticket": f"T-{index % 29:03d}"},
            },
        }
        planned = ("band_gap", "unit", "source_id")
        contracts = {
            "band_gap": {
                "semantic_id": "materials.band_gap",
                "unit": "eV",
                "qualifiers": {"method": "measured"},
            }
        }
        steps = [
            _projected_step(
                "materials.current",
                {"material_id": {"eq": material_id}},
                observation,
                planned_fields=planned,
                gold_fields=planned,
                field_contracts=contracts,
            )
        ]
        required_facts = [_fact("band_gap", round(value, 3), source_a, unit="eV")]
        tolerances = {"band_gap": {"absolute": 0.001}}
        accepted_units = {"band_gap": ["eV"]}
        forbidden = [
            {
                "key": "band_gap",
                "value": observation["record"]["computed"]["band_gap"],
                "source_id": source_a,
            }
        ]

    elif stratum == "cross_provider_name_collision":
        value = 150.0 + (index % 31)
        observation = {
            "status": "ok",
            "thermal_conductivity": round(value, 3),
            "unit": "W/(m*K)",
            "source_id": source_a,
            "value": round(value - 12.0, 3),
            "result": round(value + 9.0, 3),
            "provider_b_thermal_conductivity": round(value - 5.0, 3),
            "provider_b_source_id": source_b,
        }
        planned = ("thermal_conductivity", "unit", "source_id")
        contracts = {
            "thermal_conductivity": {
                "semantic_id": "materials.thermal_conductivity",
                "unit": "W/(m*K)",
                "provider": "materials.current",
            }
        }
        steps = [
            _projected_step(
                "materials.current",
                {"material_id": {"eq": material_id}},
                observation,
                planned_fields=planned,
                gold_fields=planned,
                field_contracts=contracts,
            )
        ]
        required_facts = [
            _fact("thermal_conductivity", round(value, 3), source_a, unit="W/(m*K)")
        ]
        tolerances = {"thermal_conductivity": {"absolute": 0.001}}
        accepted_units = {"thermal_conductivity": ["W/(m*K)"]}
        forbidden = [
            {
                "key": "thermal_conductivity",
                "value": observation["provider_b_thermal_conductivity"],
                "source_id": source_a,
            }
        ]

    elif stratum == "multi_step_provenance":
        artifact = f"ART-{prefix}{index:04d}"
        uri = f"file:///tmp/{artifact}.json"
        retrieve_observation = {
            "status": "ok",
            "material_id": material_id,
            "artifact_id": artifact,
            "source_id": source_a,
            "staging_artifact_id": f"{artifact}-STAGING",
            "cache_artifact_id": f"{artifact}-CACHE",
            "record_bytes": 4096 + index,
        }
        export_observation = {
            "status": "ok",
            "file_uri": uri,
            "source_id": source_b,
            "temp_file_uri": f"file:///tmp/{artifact}.partial",
            "mirror_file_uri": f"s3://mirror/{artifact}.json",
            "bytes_written": 2048 + index,
        }
        steps = [
            _projected_step(
                "materials.retrieve",
                {"material_id": {"eq": material_id}},
                retrieve_observation,
                planned_fields=("material_id", "artifact_id", "source_id"),
                gold_fields=("artifact_id", "source_id"),
                field_contracts={
                    "artifact_id": {"semantic_id": "exports.artifact_id", "unit": None}
                },
            ),
            _projected_step(
                "exports.export",
                {"artifact_id": {"state": "artifact_id"}},
                export_observation,
                planned_fields=("file_uri", "source_id"),
                gold_fields=("file_uri", "source_id"),
                field_contracts={
                    "file_uri": {"semantic_id": "exports.file_uri", "unit": None}
                },
            ),
        ]
        required_facts = [_fact("file_uri", uri, source_b)]
        tolerances = {}
        accepted_units = {}
        forbidden = [
            {
                "key": "file_uri",
                "value": export_observation["temp_file_uri"],
                "source_id": source_b,
            }
        ]

    else:  # pragma: no cover - guarded by the frozen stratum tuple
        raise ValueError(stratum)

    required_routes = list(dict.fromkeys(str(step["route_id"]) for step in steps))
    evidence = [
        {"source_id": step["observation"]["source_id"], "payload": step["observation"]}
        for step in steps
        if "source_id" in step["observation"]
    ]

    return {
        "semantic_task_id": slot["semantic_task_id"],
        "projection_stratum": stratum,
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
        "forbidden_facts": forbidden,
        "numeric_tolerances": tolerances,
        "accepted_units": accepted_units,
        "mandatory_answer_fields": [fact["key"] for fact in required_facts],
        "corrective_contract": None,
    }
