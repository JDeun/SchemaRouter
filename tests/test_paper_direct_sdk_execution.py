"""Public SDK direct execution refuses non-executable paper receipts before I/O."""
from unittest.mock import Mock

import pytest

from schemarouter.errors import PolicyViolationError
from schemarouter.field_routing_session import SchemaFieldRoutingSession


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [
    "requires_arguments", "requires_observation", "no_proven_hit",
    "over_k_unranked", "budget_unsatisfied", "ambiguous_paths",
])
async def test_direct_sdk_refuses_nonready_paper_receipts(monkeypatch, status):
    import schemarouter.paper_typed_tool_plan as paper

    session = object.__new__(SchemaFieldRoutingSession)
    session._router = Mock()
    session._index = Mock()
    monkeypatch.setattr(session, "_require_catalog", lambda: Mock())
    monkeypatch.setattr(
        paper, "compile_paper_typed_tool_plan",
        lambda *args, **kwargs: Mock(
            status=status, executable_authority=False, bindings=(), calls=(),
        ),
    )
    with pytest.raises(PolicyViolationError, match="one ready independent route"):
        await session.aexecute_direct("query", principal=Mock())
    session._router.execute.assert_not_called()
