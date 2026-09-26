from schemarouter.aggregation import SourceRecord, aggregate_records, canonical_identity


def test_document_records_with_same_doi_merge_into_one_entity() -> None:
    records = [
        SourceRecord(
            provider="crossref",
            entity_kind="document",
            identifiers={"doi": "https://doi.org/10.1000/ABC"},
            fields={"title": "A paper", "year": 2026},
        ),
        SourceRecord(
            provider="openalex",
            entity_kind="document",
            identifiers={"doi": "10.1000/abc"},
            fields={"title": "A paper", "cited_by_count": 12},
        ),
    ]

    entities = aggregate_records(records)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.providers == ["crossref", "openalex"]
    assert entity.fields["title"].mode == "deduplicate"
    assert entity.fields["title"].value == "A paper"
    assert len(entity.fields["title"].observations) == 2
    assert entity.fields["title"].agreement is True
    assert entity.fields["cited_by_count"].value == 12


def test_material_values_are_preserved_as_independent_observations() -> None:
    records = [
        SourceRecord(
            provider="materials-project",
            entity_kind="material",
            identifiers={"canonical_material_id": "gaas-zincblende"},
            fields={"density": 5.32},
            field_units={"density": "g/cm^3"},
            qualifiers={"method": "computed"},
        ),
        SourceRecord(
            provider="cod",
            entity_kind="material",
            identifiers={"formula": "GaAs"},
            fields={"density": 5.41},
            field_units={"density": "g/cm^3"},
            qualifiers={"method": "experimental"},
        ),
    ]

    entities = aggregate_records(records)

    assert len(entities) == 1
    density = entities[0].fields["density"]
    assert density.mode == "preserve_observations"
    assert density.value is None
    assert [item.value for item in density.observations] == [5.32, 5.41]
    assert density.agreement is False


def test_same_scientific_value_with_same_context_reports_agreement() -> None:
    records = [
        SourceRecord(
            provider="a",
            entity_kind="chemical",
            identifiers={"inchikey": "XYZ"},
            fields={"mass": 10.0},
            field_units={"mass": "g"},
            qualifiers={"temperature": "298 K"},
        ),
        SourceRecord(
            provider="b",
            entity_kind="chemical",
            identifiers={"inchikey": "XYZ"},
            fields={"mass": 10.0},
            field_units={"mass": "g"},
            qualifiers={"temperature": "298 K"},
        ),
    ]

    mass = aggregate_records(records)[0].fields["mass"]
    assert mass.agreement is True
    assert len(mass.observations) == 2


def test_document_without_identifier_is_not_fuzzy_merged_by_title() -> None:
    left = SourceRecord(
        provider="arxiv",
        entity_kind="document",
        fields={"title": "Same title"},
    )
    right = SourceRecord(
        provider="openalex",
        entity_kind="document",
        fields={"title": "Same title"},
    )

    assert canonical_identity(left) != canonical_identity(right)
    assert len(aggregate_records([left, right])) == 2


def test_field_mode_can_override_entity_default() -> None:
    records = [
        SourceRecord(
            provider="crossref",
            entity_kind="document",
            identifiers={"doi": "10.1/example"},
            fields={"citation_count": 10},
        ),
        SourceRecord(
            provider="openalex",
            entity_kind="document",
            identifiers={"doi": "10.1/example"},
            fields={"citation_count": 13},
        ),
    ]

    field = aggregate_records(
        records,
        field_modes={"citation_count": "preserve_observations"},
    )[0].fields["citation_count"]

    assert field.mode == "preserve_observations"
    assert [item.value for item in field.observations] == [10, 13]
    assert field.agreement is False


def test_identity_resolution_is_transitive_across_identifier_types() -> None:
    records = [
        SourceRecord(
            provider="crossref",
            entity_kind="document",
            identifiers={"doi": "10.1000/paper"},
            fields={"title": "Paper"},
        ),
        SourceRecord(
            provider="openalex",
            entity_kind="document",
            identifiers={"doi": "10.1000/paper", "arxiv": "2609.12345"},
            fields={"cited_by_count": 5},
        ),
        SourceRecord(
            provider="arxiv",
            entity_kind="document",
            identifiers={"arxiv": "arXiv:2609.12345"},
            fields={"abstract": "Abstract"},
        ),
    ]

    entities = aggregate_records(records)

    assert len(entities) == 1
    assert entities[0].providers == ["crossref", "openalex", "arxiv"]
    assert entities[0].canonical_key == "document:doi:10.1000/paper"



def test_material_formula_alone_does_not_define_canonical_identity() -> None:
    records = [
        SourceRecord(
            provider="provider_a",
            entity_kind="material",
            identifiers={"formula": "SiO2"},
            fields={"band_gap": 8.9},
        ),
        SourceRecord(
            provider="provider_b",
            entity_kind="material",
            identifiers={"formula": "SiO2"},
            fields={"band_gap": 5.5},
        ),
    ]

    assert len(aggregate_records(records)) == 2


def test_material_records_merge_on_explicit_structure_identity() -> None:
    records = [
        SourceRecord(
            provider="provider_a",
            entity_kind="material",
            identifiers={"structure_id": "shared-structure", "formula": "SiO2"},
            fields={"density": 2.65},
        ),
        SourceRecord(
            provider="provider_b",
            entity_kind="material",
            identifiers={"structure_id": "shared-structure", "formula": "SiO2"},
            fields={"density": 2.66},
        ),
    ]

    entities = aggregate_records(records)

    assert len(entities) == 1
    assert len(entities[0].fields["density"].observations) == 2


def test_chemical_formula_alone_does_not_merge_isomers() -> None:
    records = [
        SourceRecord(
            provider="provider_a",
            entity_kind="chemical",
            identifiers={"formula": "C2H6O"},
            fields={"name": "ethanol"},
        ),
        SourceRecord(
            provider="provider_b",
            entity_kind="chemical",
            identifiers={"formula": "C2H6O"},
            fields={"name": "dimethyl ether"},
        ),
    ]

    assert len(aggregate_records(records)) == 2
