"""Owner-reviewed original-paper source inventory for replay and model studies.

No query cohort, expected plan, gold label, or evaluator is loaded here.
The source-only meanings are deliberately frozen, not a general ontology.
"""
from __future__ import annotations

from copy import deepcopy

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
    SchemaRouter,
    ToolSpec,
)

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
        return deepcopy(TYPES[type_name])
    parts = type_name.split(" | ")
    if len(parts) > 1 and all(part in TYPES for part in parts):
        return {"anyOf": [deepcopy(TYPES[part]) for part in parts]}
    # The inventory does not enumerate the source's CrystalSystem/Ordering
    # values. Unknown contracts remain unknown; don't fabricate enum values.
    return {}

def build_original_paper_inventory(inventory):
    """Build the single research host catalog from pinned source inventory only."""
    apis = {api["name"]: api for api in inventory["apis"]}
    intents_by_name = {intent["name"]: intent for intent in inventory["intents"]}
    if (
        len(apis) != 19 or len(intents_by_name) != 13
        or sum(len(api["fields"]) for api in apis.values()) != 166
    ):
        raise ValueError("original source inventory cardinality changed")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    semantics = {member: sid for sid, _, _, members in MEANINGS for member in members}
    assert len(semantics) == sum(len(members) for _, _, _, members in MEANINGS)
    fields = {}
    for api in apis.values():
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
        assert all(apis[m.split(":", 1)[0]]["source_type"] == source for m in members)
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
        NativeDeclaredConcept(
            concept_id="mat.magnetic_properties",
            aliases=("magnetic_property", "magnetic properties", "magnetic property"),
            source_type="calculated",
            required_fields=(
                contracts["mat.magnetic_moment"], contracts["mat.magnetic_ordering"],
            ),
        ),
        NativeDeclaredConcept(
            concept_id="mat.elastic_properties",
            aliases=("elastic moduli", "bulk and shear moduli"),
            source_type="calculated",
            required_fields=(contracts["mat.bulk_modulus"], contracts["mat.shear_modulus"]),
        ),
        NativeDeclaredConcept(
            concept_id="mat.experimental_lattice_lengths",
            aliases=("lattice_lengths", "lattice lengths", "cell lengths"),
            source_type="experimental",
            required_fields=tuple(
                CapabilityFieldContract.from_field(fields[f"cod:{name}"])
                for name in ("_cod_a", "_cod_b", "_cod_c")
            ),
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
        ) for i in intents_by_name.values()),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={f"{key}.search": {
            g["name"]: tuple(g["field_names"]) for g in api["field_groups"]
        } for key, api in apis.items()},
        route_parameter_value_aliases={"arxiv.search": {"sortBy": {"latest": "submittedDate"}}},
    )
    rank = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        route_domains={f"{key}.search": (api["domain"],) for key, api in apis.items()},
        route_priorities={f"{key}.search": api.get("priority", 1) for key, api in apis.items()},
        web_route_ids=tuple(f"{key}.search" for key, api in apis.items() if api["domain"] == "web"),
    )
    return session, intents, rank
