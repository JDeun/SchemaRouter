"""Focused contract smoke for the mcp-agent external validation."""

from __future__ import annotations

import asyncio
import unittest

from scripts.external_validation_mcp_agent import evaluate


class MCPAgentCatalogRetrievalContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_agent_lifecycle_and_filtered_catalog(self) -> None:
        result = await evaluate()
        summary = result["summary"]
        boundary = result["boundary"]

        self.assertEqual(summary["required_tool_recall"], 1.0)
        self.assertEqual(summary["unsupported_rejection"], 1.0)
        self.assertEqual(summary["retrieval_task_success_rate"], 1.0)
        self.assertEqual(summary["mcp_tool_calls_during_evaluation"], 0)
        self.assertEqual(
            summary["input_schema_exact_matches"],
            summary["input_schema_total"],
        )
        self.assertFalse(boundary["execution_through_schemarouter"])
        self.assertEqual(boundary["lifecycle_owner"], "mcp-agent")


if __name__ == "__main__":
    unittest.main()
