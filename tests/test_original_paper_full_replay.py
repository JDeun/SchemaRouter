"""Reproduce the frozen paper's 110 plans and compare the actual library.

Conditional archived understanding, not independent model or end-task quality.
The historical tool/field/parameter outputs never enter the current router.
All 19 frozen sources are registered together; no provider or model is invoked.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "original_paper_full_replay.json").read_text(
        encoding="utf-8",
    )
)
APIS = {a["name"]: a for a in FIXTURE["inventory"]["apis"]}
INTENTS = {i["name"]: i for i in FIXTURE["inventory"]["intents"]}
CASES = FIXTURE["cases"]
ACTOR = PrincipalContext(subject="original-paper-conditional-replay")

# Deliberately conservative, test-host-owned semantic review of the pinned
# source fields. Every member must have the same declared type and unit.
# Do not infer semantic equality from spelling, compare different DFT methods
# as equal, equate a space-group symbol with a number, or turn the OQMD
# hull-distance number into the MP Boolean stability flag.
# This table is source inventory review, not an independently held-out ontology.
MEANINGS = (
    ("mat.band_gap", ("band_gap", "band gap"), "calculated", (
        "materials_project:band_gap", "oqmd:band_gap",
        "nomad:results.properties.electronic_band_gap_value",
    )),
    ("mat.formation_energy", ("formation_energy",), "calculated", (
        "materials_project:formation_energy_per_atom", "oqmd:delta_e",
        "jarvis:formation_energy_peratom",
    )),
    # For this host's broad thermodynamic assessment vocabulary, "stability"
    # requests the continuous hull-energy indicator. The frozen OQMD source
    # explicitly equates its stability field with MP energy_above_hull.
    # This is NOT a universal alias for Boolean stability or decomposition energy.
    ("mat.hull_energy", ("energy_above_hull", "stability"), "calculated", (
        "materials_project:energy_above_hull", "oqmd:stability", "jarvis:ehull",
    )),
    ("mat.stability_flag", ("is_stable", "stable", "thermodynamic_stability"), "calculated", (
        "materials_project:is_stable",
    )),
    ("mat.crystal_system", ("crystal_structure", "crystal_system"), "calculated", (
        "materials_project:crystal_system", "nomad:results.material.symmetry.crystal_system",
    )),
    ("mat.space_group_number", ("space_group", "space_group_number"), "calculated", (
        "materials_project:spacegroup_number", "jarvis:spg_number",
        "nomad:results.material.symmetry.space_group_number",
    )),
    ("mat.experimental_space_group", ("space_group", "space_group_symbol"), "experimental", (
        "cod:_cod_sg",
    )),
    ("mat.density", ("density",), "calculated", (
        "materials_project:density", "jarvis:density",
    )),
    ("mat.magnetic_moment", ("magnetic_moment",), "calculated", (
        "materials_project:total_magnetization",
    )),
    ("mat.magnetic_ordering", ("magnetic_ordering",), "calculated", (
        "materials_project:magnetic_ordering",
    )),
    ("mat.bulk_modulus", ("bulk_modulus",), "calculated", ("materials_project:k_vrh",)),
    ("mat.shear_modulus", ("shear_modulus",), "calculated", ("materials_project:g_vrh",)),
    ("chem.formula", ("molecular_formula", "chemical_formula"), "experimental", (
        "pubchem:molecular_formula",
    )),
    ("chem.weight", ("molecular_weight",), "experimental", ("pubchem:molecular_weight",)),
    ("chem.smiles", ("smiles",), "experimental", ("pubchem:canonical_smiles",)),
    ("chem.inchikey", ("inchikey",), "experimental", ("pubchem:inchikey",)),
    ("chem.isomeric_smiles", ("isomeric_smiles",), "experimental", (
        "pubchem:isomeric_smiles",
    )),
    ("chem.inchi", ("inchi",), "experimental", ("pubchem:inchi",)),
    ("chem.xlogp", ("xlogp",), "experimental", ("pubchem:xlogp",)),
    ("paper.title", ("title", "paper title"), "literature", (
        "arxiv:title", "europe_pmc:title", "openalex:title", "pubmed:title",
    )),
    ("paper.abstract", ("abstract", "summary"), "literature", (
        "arxiv:summary", "crossref:abstract", "europe_pmc:abstract",
        "openalex:abstract", "pubmed:abstract",
    )),
    ("paper.authors", ("authors",), "literature", (
        "arxiv:authors", "crossref:author", "openalex:authors", "pubmed:authors",
    )),
    ("paper.submitted_date", ("publication_date", "publication date"), "literature", (
        "arxiv:published",
    )),
)
# No reviewed semantics for broad elastic_modulus, missing Young's modulus,
# decomposition energy, lattice angles, unsupported PubChem properties,
# topic words, logP vs xlogp, or date/year equivalence.
# Both source inventory descriptions identify the chemistry formula input.
# The OQMD composition domain also admits element systems; only the common
# literal formula role is approved for this fixed comparison intent.
PARAMETER_SEMANTICS = {
    ("materials_project", "formula"): "material.formula",
    ("oqmd", "composition"): "material.formula",
}
PARAMETER_ALIASES = {
    "oqmd": {"composition": ("formula",)},
    "arxiv": {"search_query": ("search topic",), "sortBy": ("sort order",)},
    "crossref": {"query": ("search topic",)},
    "europe_pmc": {"query": ("search topic",)},
    "openalex": {"search": ("search topic",)},
    "pubmed": {"term": ("search topic",)},
}
TYPES = {
    "str": {"type": "string"}, "string": {"type": "string"},
    "int": {"type": "integer"}, "integer": {"type": "integer"},
    "float": {"type": "number"}, "bool": {"type": "boolean"},
    "boolean": {"type": "boolean"},
    "datetime": {"type": "string", "format": "date-time"},
    "dict": {"type": "object"}, "object": {"type": "object"},
    "list[str]": {"type": "array", "items": {"type": "string"}},
    "list[float]": {"type": "array", "items": {"type": "number"}},
    "list[int]": {"type": "array", "items": {"type": "integer"}},
    "tuple[float, float]": {
        "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
    },
}


def _schema(type_name):
    if type_name in TYPES:
        return dict(TYPES[type_name])
    parts = type_name.split(" | ")
    if len(parts) > 1 and all(part in TYPES for part in parts):
        return {"anyOf": [dict(TYPES[part]) for part in parts]}
    # The inventory does not enumerate the source's CrystalSystem/Ordering
    # values. Unknown contracts remain unknown; don't fabricate enum values.
    return {}


def _literal_hints(case):
    query = case["query"]
    named = []
    for api in APIS.values():
        for label in dict.fromkeys((api["name"], api["display_name"])):
            match = re.search(
                r"(?<![A-Za-z0-9_])" + re.escape(label) + r"(?![A-Za-z0-9_])",
                query, flags=re.IGNORECASE,
            )
            if match:
                named.append((match.start(), api["name"], match.group()))
                break
    source = (
        "experimental" if "실험으로 측정된" in query else
        "calculated" if "DFT로 계산된" in query else None
    )
    hints = {}
    if case["category"] == "literature_search":
        match = re.match(r"^(.+?) 관련 최신 arXiv 논문을 찾아줘\.$", query)
        if match:
            hints = {"search topic": match[1], "sort order": "latest"}
    elif case["category"] == "chemical_lookup":
        match = re.match(r"^(.+?)의 ", query)
        if match:
            hints = {"identifier": match[1]}
    elif case["intent"] is not None:
        match = re.match(
            r"^(?:실험으로 측정된 |DFT로 계산된 )?([A-Za-z0-9]+)(?:의| 안정성)", query,
        )
        if match:
            hints = {"formula": match[1]}
    return sorted(named), source, hints


def _norm(value):
    return value.strip().lower().replace("_", "").replace(" ", "").replace("-", "")


def _reference_plan(case, named, source):
    """Test-only transcription of the pinned original deterministic algorithm."""
    concepts = case["concepts"]
    intent = INTENTS.get(case["intent"])
    if named:
        candidates = [APIS[key] for _, key, _ in named]
    else:
        candidates = [
            api for api in APIS.values() if intent is not None
            and (not intent["target_api_names"] or api["name"] in intent["target_api_names"])
            and (not intent["applicable_domains"] or api["domain"] in intent["applicable_domains"])
            and (not intent["required_groups"] or set(intent["required_groups"]) & {
                group["name"] for group in api["field_groups"]
            })
        ]
        if not candidates:
            candidates = [api for api in APIS.values() if any(
                label.lower() in field["name"].lower() or field["name"].lower() in label.lower()
                for label in concepts for field in api["fields"]
            )]
        # Historical permissive fallback is reproduced ONLY in this reference.
        if source:
            candidates = [api for api in candidates if api["source_type"] == source] or candidates
        if not (intent and intent["target_api_names"]) and len(candidates) > 1:
            def rank(api):
                names = {field["name"].lower() for field in api["fields"]}
                score = sum(2 if label.strip().lower() in names else
                            int(any(label.strip().lower() in name or name in label.strip().lower()
                                    for name in names)) for label in concepts)
                return (-score, api["domain"] == "web", -api.get("priority", 1),
                        len(api["fields"]), api["name"])
            candidates = sorted(candidates, key=rank)[:1]
    result = {}
    for api in candidates:
        names = {f["name"] for f in api["fields"]}
        groups = {g["name"]: set(g["field_names"]) & names for g in api["field_groups"]}
        synonyms = {_norm(alias): f["name"] for f in api["fields"] for alias in f["aliases"]}
        equivalent = {eq["field_name"].lower(): f["name"]
                      for f in api["fields"] for eq in f["equivalent_to"]}
        selected = {f["name"] for f in api["fields"] if f["is_identifier"]}
        for label in concepts:
            key = _norm(label)
            matches = {name for name in names if key in _norm(name) or _norm(name) in key}
            if key in synonyms:
                matches.add(synonyms[key])
            if label.strip().lower() in equivalent:
                matches.add(equivalent[label.strip().lower()])
            selected.update(matches)
            for members in groups.values():
                if matches & members:
                    selected.update(members)
            selected.update(groups.get(label.strip().lower(), ()))
        for group in intent["required_groups"] if intent else ():
            selected.update(groups.get(group, ()))
        if selected:
            result[api["name"]] = selected
    return result


def _build():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    semantics = {member: sid for sid, _, _, members in MEANINGS for member in members}
    assert len(semantics) == sum(len(members) for _, _, _, members in MEANINGS)
    fields = {}
    for api in APIS.values():
        key = api["name"]
        output = []
        for raw in api["fields"]:
            ref = f"{key}:{raw['name']}"
            field = FieldSpec(
                name=raw["name"], semantic_id=semantics.get(ref, f"frozen.{key}.{raw['name']}"),
                json_schema=_schema(raw["type"]), unit=raw["unit"], identifier=raw["is_identifier"],
            )
            output.append(field)
            fields[ref] = field
        parameters = []
        for raw in api["parameters"]:
            schema = _schema(raw["type"])
            if key == "arxiv" and raw["name"] == "sortBy":
                schema["enum"] = ["relevance", "lastUpdatedDate", "submittedDate"]
            parameters.append(ParameterSpec(
                name=raw["name"], required=raw["required"], json_schema=schema,
                aliases=list(PARAMETER_ALIASES.get(key, {}).get(raw["name"], ())),
                semantic_id=PARAMETER_SEMANTICS.get((key, raw["name"])),
            ))
        router.add_tool(ToolSpec(
            name=key, source_type=api["source_type"], license=api["license"],
            endpoints=[EndpointSpec(
                name="search", read_only=True, output_fields=output, parameters=parameters,
                input_schema={
                    "type": "object",
                    "properties": {p.name: p.json_schema for p in parameters},
                    "required": [p.name for p in parameters if p.required],
                    "additionalProperties": False,
                },
            )],
        ))
    contracts = {}
    concepts = []
    for sid, aliases, source, members in MEANINGS:
        contract = CapabilityFieldContract.from_field(fields[members[0]])
        assert contract is not None
        assert all(CapabilityFieldContract.from_field(fields[m]) == contract for m in members)
        assert all(APIS[m.split(":", 1)[0]]["source_type"] == source for m in members)
        contracts[sid] = contract
        concepts.append(NativeDeclaredConcept(
            concept_id=sid, aliases=aliases, source_type=source, required_fields=(contract,),
        ))
    # Source-backed aggregate meanings, independent of historical selected calls.
    concepts.extend((
        NativeDeclaredConcept(
            concept_id="chem.structure", aliases=("structure",), source_type="experimental",
            required_fields=tuple(contracts[sid] for sid in (
                "chem.smiles", "chem.isomeric_smiles", "chem.inchi", "chem.inchikey",
            )),
        ),
        NativeDeclaredConcept(
            concept_id="paper.record", aliases=("research papers",), source_type="literature",
            required_fields=(contracts["paper.title"], contracts["paper.abstract"]),
        ),
    ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(concepts)))
    # Intent groups are discovery/recall memberships, NOT an invented global AND.
    intents = PaperIntentRegistry(
        intents=tuple(PaperIntentDeclaration(
            intent_id=i["name"], required_concept_ids=(),
            domains=tuple(i["applicable_domains"]),
            recall_group_ids=tuple(i["required_groups"]),
            target_tool_keys=tuple(i["target_api_names"]),
            shared_parameter_semantics=(
                {"formula": "material.formula"} if i["name"] == "cross_validate" else {}
            ),
        ) for i in INTENTS.values()),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={f"{key}.search": {
            g["name"]: tuple(g["field_names"]) for g in api["field_groups"]
        } for key, api in APIS.items()},
        route_parameter_value_aliases={"arxiv.search": {"sortBy": {"latest": "submittedDate"}}},
    )
    rank = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        route_domains={f"{key}.search": (api["domain"],) for key, api in APIS.items()},
        route_priorities={f"{key}.search": api.get("priority", 1) for key, api in APIS.items()},
        web_route_ids=tuple(f"{key}.search" for key, api in APIS.items() if api["domain"] == "web"),
    )
    return session, intents, rank


def test_frozen_original_reference_matches_all_archived_plans():
    assert len(APIS) == 19 and len(INTENTS) == 13 and len(CASES) == 110
    assert sum(len(api["fields"]) for api in APIS.values()) == 166
    assert len({case["query_id"] for case in CASES}) == 110
    missing_required = 0
    call_count = 0
    for case in CASES:
        named, source, _ = _literal_hints(case)
        expected = {call["tool"]: set(call["fields"]) for call in case["archived_calls"]}
        assert _reference_plan(case, named, source) == expected, case["query_id"]
        for call in case["archived_calls"]:
            api = APIS[call["tool"]]
            assert call["evidence_requirements"]["source_type"] == api["source_type"]
            assert call["evidence_requirements"]["license"] == api["license"]
            assert set(call["parameters"]) <= {p["name"] for p in api["parameters"]}
            missing_required += int(any(
                p["required"] and p["name"] not in call["parameters"] for p in api["parameters"]
            ))
            call_count += 1
    assert call_count == 110 and missing_required == 24


def test_stability_meaning_is_grounded_in_frozen_source_contracts():
    mp = {field["name"]: field for field in APIS["materials_project"]["fields"]}
    oqmd = {field["name"]: field for field in APIS["oqmd"]["fields"]}
    jarvis = {field["name"]: field for field in APIS["jarvis"]["fields"]}
    indicators = (mp["energy_above_hull"], oqmd["stability"], jarvis["ehull"])
    assert all(
        field["type"] == "float" and field["unit"] == "eV/atom"
        and field["source_type"] == "calculated" for field in indicators
    )
    assert any(
        equivalent["api_name"] == "materials_project"
        and equivalent["field_name"] == "energy_above_hull"
        for equivalent in oqmd["stability"]["equivalent_to"]
    )
    assert mp["is_stable"]["type"] == "boolean" and mp["is_stable"]["unit"] is None
    # Source aliases describe source-specific meanings, not global equivalence.
    assert "stability" in mp["is_stable"]["aliases"]
    assert "stability" in oqmd["stability"]["aliases"]


@pytest.fixture(scope="module")
def stability_session():
    return _build()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,display,concept,unit,source,expected_field,expected_sid", [
    ("materials_project", "Materials Project", "stability", "eV/atom", "calculated",
     "energy_above_hull", "mat.hull_energy"),
    ("oqmd", "OQMD", "stability", "eV/atom", "calculated",
     "stability", "mat.hull_energy"),
    ("jarvis", "JARVIS", "stability", "eV/atom", "calculated",
     "ehull", "mat.hull_energy"),
    ("materials_project", "Materials Project", "is_stable", None, "calculated",
     "is_stable", "mat.stability_flag"),
    ("materials_project", "Materials Project", "stable", None, "calculated",
     "is_stable", "mat.stability_flag"),
    ("oqmd", "OQMD", "is_stable", None, "calculated", None, None),
    ("oqmd", "OQMD", "thermodynamic_stability", None, "calculated", None, None),
    ("materials_project", "Materials Project", "stability", "GPa", "calculated", None, None),
    ("materials_project", "Materials Project", "is_stable", "eV/atom",
     "calculated", None, None),
    ("materials_project", "Materials Project", "stability", "eV/atom",
     "experimental", None, None),
    ("materials_project", "Materials Project", "decomposition_energy", "eV/atom",
     "calculated", None, None),
])
async def test_stability_indicator_and_boolean_are_distinct_native_proofs(
    stability_session, tool, display, concept, unit, source, expected_field, expected_sid,
):
    session, intents, rank = stability_session
    need = {"concept": concept}
    if unit is not None:
        need["unit"] = unit
    raw = {
        "intent_id": "check_stability", "needs": [need],
        "named_tools": [display], "source_type": source,
    }
    plan = await session.acompile_query(
        f"Find {concept} for a material using {display}.",
        principal=ACTOR, intent_registry=intents, rank_policy=rank,
        model=lambda _: raw, model_visible_intent_ids=("check_stability",),
    )
    assert not plan.executable_authority and not plan.bindings
    assert plan.coverage is not None
    if expected_field is None:
        assert not plan.coverage.complete
        assert not plan.calls
        assert any(item.semantic_id == concept for item in plan.coverage.uncovered)
        return
    assert plan.coverage.complete
    assert [call.call.tool for call in plan.calls] == [tool]
    call = plan.calls[0]
    assert call.call.arguments == {}
    metas = {meta.name: meta for meta in call.fields_meta}
    meta = metas[expected_field]
    assert meta.semantic_id == expected_sid
    assert meta.unit == unit
    assert meta.json_schema["type"] == ("number" if unit else "boolean")
    if tool == "materials_project":
        # Recall expansion may return both quantities, but their typed
        # contracts remain distinct. No bool<->number conversion is inferred.
        assert metas["energy_above_hull"].semantic_id == "mat.hull_energy"
        assert metas["energy_above_hull"].unit == "eV/atom"
        assert metas["is_stable"].semantic_id == "mat.stability_flag"
        assert metas["is_stable"].json_schema["type"] == "boolean"
        assert metas["is_stable"].unit is None


def _fixed_understanding(case, *, role_aware=False):
    named, source, hints = _literal_hints(case)
    labels = case["concepts"]
    if role_aware and case["category"] == "literature_search":
        labels = ["research papers"]
    needs = [{"concept": label} for label in labels[:8]]
    # Preserve explicit units when the original labels identify the quantity.
    unit_labels = {
        "GPa": {"elastic_modulus", "bulk_modulus", "shear_modulus", "youngs_modulus"},
        "g/cm³": {"density"},
        "eV/atom": {"formation_energy"},
    }
    for unit, names in unit_labels.items():
        if unit in case["query"]:
            for need in needs:
                if need["concept"] in names:
                    need["unit"] = unit
    return {
        "intent_id": case["intent"], "needs": needs,
        "needs_truncated": len(labels) > 8,
        "named_tools": [label for _, _, label in named],
        "source_type": source, "parameter_hints": hints,
    }


async def _replay(session, intents, rank, case, *, role_aware=False):
    raw = _fixed_understanding(case, role_aware=role_aware)
    observed = []

    def model(payload):
        observed.append(payload)
        return raw

    plan = await session.acompile_query(
        case["query"], principal=ACTOR, intent_registry=intents, rank_policy=rank,
        model=model, model_visible_intent_ids=tuple(INTENTS),
    )
    assert len(observed) == 1
    assert "schema_catalog" not in observed[0] and "offered_concepts" not in observed[0]
    assert not plan.executable_authority and not plan.bindings
    assert plan.coverage is not None
    assert len(plan.calls) <= 5
    current = {}
    proposals = {}
    missing = {}
    for call in plan.calls:
        key = call.call.tool
        api = APIS[key]
        assert call.route_id == f"{key}.search"
        assert call.call.arguments == {}
        assert call.source_type == api["source_type"] and call.license == api["license"]
        source_fields = {field["name"]: field for field in api["fields"]}
        assert set(call.call.fields) <= source_fields.keys()
        assert len(call.call.fields) == len(set(call.call.fields))
        assert {m.name for m in call.fields_meta} == set(call.call.fields)
        for meta in call.fields_meta:
            assert meta.unit == source_fields[meta.name]["unit"]
        assert {name for name, _ in call.parameter_proposals} <= {
            p["name"] for p in api["parameters"]
        }
        current[key] = sorted(call.call.fields)
        proposals[key] = dict(call.parameter_proposals)
        missing[key] = list(call.call.missing_required_arguments)
    expected = {c["tool"]: sorted(c["fields"]) for c in case["archived_calls"]}
    tool_exact = set(current) == set(expected)
    if case["intent"] is None:
        assert not plan.calls and plan.status == "no_proven_hit"
    if len(case["concepts"]) > 8 and not role_aware:
        assert not plan.calls and plan.status == "budget_unsatisfied"
    return {
        "query_id": case["query_id"], "category": case["category"],
        "status": plan.status, "coverage_complete": plan.coverage.complete,
        "tool_exact": tool_exact, "field_exact": tool_exact and current == expected,
        "selected": current, "historical": expected, "proposals": proposals,
        "missing_required": missing,
        "uncovered": [item.semantic_id for item in plan.coverage.uncovered],
        # Persist exact input proof classifications for failure attribution;
        # values remain in the bounded detached proposal/Understanding data.
        "uncovered_requirements": [
            item.model_dump(mode="json") for item in plan.coverage.uncovered
        ],
        "raw_needs": raw["needs"], "raw_needs_truncated": raw["needs_truncated"],
    }


@pytest.mark.asyncio
async def test_full_original_inventory_conditional_library_replay():
    session, intents, rank = _build()
    assert session._index.field_index.indexed_route_count == 19
    rows: list[dict[str, Any]] = []
    errors = []
    for case in CASES:
        try:
            rows.append(await _replay(session, intents, rank, case))
        except Exception as exc:
            errors.append({"query_id": case["query_id"], "error": type(exc).__name__,
                           "detail": str(exc)[:500]})
    role_aware = []
    for case in CASES:
        if case["category"] == "literature_search":
            try:
                role_aware.append(await _replay(session, intents, rank, case, role_aware=True))
            except Exception as exc:
                errors.append({"query_id": case["query_id"], "arm": "role_aware_literature",
                               "error": type(exc).__name__, "detail": str(exc)[:500]})
    positive = [row for row in rows if row["historical"]]
    categories = {}
    for row in rows:
        category = categories.setdefault(row["category"], Counter())
        category["n"] += 1
        category["tool_exact"] += row["tool_exact"]
        category["field_exact"] += row["field_exact"]
        category["coverage_complete"] += row["coverage_complete"]
    summary = {
        "scope": "fixed archived labels + reconstructed literal hints, no model/provider IO",
        "query_count": len(CASES), "completed": len(rows), "errors": errors,
        "tool_exact": sum(row["tool_exact"] for row in rows),
        "field_exact": sum(row["field_exact"] for row in rows),
        "supported_rows_with_calls": sum(bool(row["selected"]) for row in positive),
        "supported_coverage_complete": sum(row["coverage_complete"] for row in positive),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "categories": {key: dict(value) for key, value in categories.items()},
        "role_aware_literature": {
            "n": len(role_aware), "tool_exact": sum(row["tool_exact"] for row in role_aware),
            "field_exact": sum(row["field_exact"] for row in role_aware),
            "coverage_complete": sum(row["coverage_complete"] for row in role_aware),
            "statuses": dict(Counter(row["status"] for row in role_aware)),
        },
    }
    print("PAPER_110_REPLAY_SUMMARY " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    report = os.environ.get("SCHEMAROUTER_PAPER_REPLAY_REPORT")
    if report:
        Path(report).write_text(json.dumps(
            {"provenance": FIXTURE["provenance"], "summary": summary, "rows": rows,
             "role_aware_literature": role_aware}, ensure_ascii=False, indent=2,
        ) + "\n", encoding="utf-8")
    # Fail engineering errors, not scientifically informative mismatches.
    assert not errors, errors
    assert len(rows) == 110 and len(role_aware) == 10
    # No expected historical labels enter the planner. Verify the specific
    # union-input seam on the full cohort after execution, not a tuned route
    # selection or overall task-quality target.
    for row in rows:
        raw_case = next(case for case in CASES if case["query_id"] == row["query_id"])
        _, _, hints = _literal_hints(raw_case)
        if set(row["selected"]) == {"materials_project"} and "formula" in hints:
            assert row["proposals"]["materials_project"].get("formula") == hints["formula"]
            assert "formula" not in row["uncovered"]
        if set(row["selected"]) == {"pubchem"} and "identifier" in hints:
            assert row["proposals"]["pubchem"].get("identifier") == hints["identifier"]
            assert "identifier" not in row["uncovered"]
        # A broad stability request in this frozen host vocabulary uses
        # quantitative hull energy. Do not select an expected provider by
        # case ID or archived output. Check unchanged historical results only
        # after the native router has selected its sources.
        if (
            raw_case["intent"] == "check_stability"
            and set(raw_case["concepts"]) == {"formation_energy", "stability"}
        ):
            assert row["coverage_complete"], row["query_id"]
            assert row["tool_exact"] and row["field_exact"], row["query_id"]
            assert row["status"] == "requires_arguments"
        if "decomposition_energy" in raw_case["concepts"]:
            assert "decomposition_energy" in row["uncovered"]
            assert not row["coverage_complete"]
        if row["category"] == "cross_source_comparison":
            assert set(row["selected"]) == {"materials_project", "oqmd"}
            assert row["coverage_complete"]
            assert row["proposals"]["materials_project"]["formula"] == hints["formula"]
            assert row["proposals"]["oqmd"]["composition"] == hints["formula"]
            assert row["status"] == "requires_arguments"
