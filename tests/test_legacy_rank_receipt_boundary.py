"""Research ranking receipts must stay distinct from installed paper receipts."""
from dataclasses import asdict, fields
from typing import get_args, get_type_hints

import pytest

from schemarouter import IndexedNativeFieldResult, NativeIndexedGraphResult
from scripts.research_legacy_g5_rank import NativeIndexedGraphResult as HistoricalGraphResult
from scripts.research_legacy_posting_rank import IndexedNativeFieldResult as HistoricalFieldResult


@pytest.mark.parametrize(
    ("product", "historical", "kwargs"),
    [
        (
            IndexedNativeFieldResult,
            HistoricalFieldResult,
            {"registry_version": 1, "index_snapshot_id": "snapshot", "requested_k": 5,
             "qualified_count": 7, "candidates": ()},
        ),
        (
            NativeIndexedGraphResult,
            HistoricalGraphResult,
            {"registry_version": 1, "index_snapshot_id": "snapshot", "requested_k": 5,
             "qualified_path_count": 7, "candidates": ()},
        ),
    ],
)
def test_historical_abstention_remains_a_distinct_non_product_receipt(
    product, historical, kwargs,
):
    receipt = historical(
        status="ranker_abstained_unverified", experimental_ranked=True, **kwargs,
    )
    assert type(receipt) is historical
    assert not isinstance(receipt, product)
    wire = asdict(receipt)
    assert wire["status"] == "ranker_abstained_unverified"
    assert wire["experimental_ranked"] is True
    assert historical(**wire) == receipt
    assert tuple(field.name for field in fields(historical) if field.name != "experimental_ranked") == (
        tuple(field.name for field in fields(product))
    )
    assert "ranker_abstained_unverified" in get_args(get_type_hints(historical)["status"])
    assert "ranker_abstained_unverified" not in get_args(get_type_hints(product)["status"])
    with pytest.raises(TypeError):
        product(**wire)
    assert not receipt.deterministic_paper_ranked
