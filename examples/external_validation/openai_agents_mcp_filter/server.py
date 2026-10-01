"""Deterministic local MCP server for the OpenAI Agents SDK validation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("SchemaRouterOpenAIAgentsValidation")


def _record_call(name: str) -> None:
    target = os.environ.get("SCHEMAROUTER_OPENAI_AGENTS_CALL_LOG")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"tool": name}) + "\n")


@mcp.tool()
def weather_lookup(city: str) -> dict[str, Any]:
    """Get current weather temperature and conditions for a city."""
    _record_call("weather_lookup")
    return {"city": city, "temperature": 20, "conditions": "clear"}


@mcp.tool()
def stock_quote(symbol: str) -> dict[str, Any]:
    """Get the latest stock market price for a ticker symbol."""
    _record_call("stock_quote")
    return {"symbol": symbol, "price": 100.0}


@mcp.tool()
def currency_convert(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> dict[str, Any]:
    """Convert money between ISO currency codes."""
    _record_call("currency_convert")
    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": amount,
    }


@mcp.tool()
def flight_status(flight_number: str) -> dict[str, Any]:
    """Get airline flight departure, arrival, and delay status."""
    _record_call("flight_status")
    return {"flight_number": flight_number, "status": "on_time"}


@mcp.tool()
def hotel_search(city: str) -> dict[str, Any]:
    """Find hotel and lodging options in a destination city."""
    _record_call("hotel_search")
    return {"city": city, "hotels": ["Example Hotel"]}


@mcp.tool()
def restaurant_search(city: str) -> dict[str, Any]:
    """Find restaurant and dining options in a city."""
    _record_call("restaurant_search")
    return {"city": city, "restaurants": ["Example Restaurant"]}


@mcp.tool()
def package_track(tracking_id: str) -> dict[str, Any]:
    """Track a parcel or shipment by tracking identifier."""
    _record_call("package_track")
    return {"tracking_id": tracking_id, "shipment_status": "in_transit"}


@mcp.tool()
def calendar_lookup(date: str) -> dict[str, Any]:
    """List calendar events for a date."""
    _record_call("calendar_lookup")
    return {"date": date, "events": []}


@mcp.tool()
def issue_search(query: str) -> dict[str, Any]:
    """Search software project issues and bug reports."""
    _record_call("issue_search")
    return {"query": query, "issues": []}


@mcp.tool()
def paper_search(query: str) -> dict[str, Any]:
    """Search research papers and scientific abstracts."""
    _record_call("paper_search")
    return {"query": query, "papers": []}


@mcp.tool()
def material_band_gap(formula: str) -> dict[str, Any]:
    """Get the electronic band gap for a material or chemical formula."""
    _record_call("material_band_gap")
    return {"formula": formula, "band_gap": 1.12}


@mcp.tool()
def delete_record(record_id: str) -> dict[str, Any]:
    """Delete an archived record by identifier."""
    _record_call("delete_record")
    return {"record_id": record_id, "deleted": True}


if __name__ == "__main__":
    mcp.run(transport="stdio")
