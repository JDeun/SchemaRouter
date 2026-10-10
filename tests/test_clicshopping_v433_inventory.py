"""Fail closed on ClicShopping upstream contract and authorization drift."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.validate_clicshopping_v433_inventory import (
    DEFAULT_INVENTORY,
    validate_inventory,
)


def inventory() -> dict:
    return json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))


def test_accurate_public_source_inventory_passes() -> None:
    assert validate_inventory(inventory()) == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x["endpoints"]["customerOrders"]["page_source"].update(
            present=True
        ),
        lambda x: x["endpoints"]["CustomersProducts"]["write_actions"].append(
            "delete_product"
        ),
        lambda x: x["endpoints"]["ChatRagBI"].update(response_contract="no typed error"),
        lambda x: x["overlap_actions"].update(count=5),
        lambda x: x["comparison"].update(status="official_scored"),
        lambda x: x["comparison"].update(live_requests=1),
    ],
)
def test_source_misrepresentation_fails_closed(mutation) -> None:
    data = deepcopy(inventory())
    mutation(data)
    assert validate_inventory(data)
