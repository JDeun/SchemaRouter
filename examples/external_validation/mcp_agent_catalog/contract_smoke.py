"""Focused contract smoke for the mcp-agent catalog composition."""

from __future__ import annotations

import unittest

from scripts.external_validation_mcp_agent import evaluate


class MCPAgentCatalogContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_retrieval_composition(self) -> None:
        result = await evaluate()

        summary = result["summary"]
        boundary = result["boundary"]
        conversion = result["schema_conversion"]

        self.assertEqual(summary["required_tool_recall"], 1.0)
        self.assertEqual(summary["unsupported_rejection"], 1.0)
        self.assertEqual(summary["task_completion_rate"], 1.0)
        self.assertEqual(
            conversion["input_schema_exact_matches"],
            conversion["input_schema_total"],
        )
        self.assertFalse(conversion["authority_metadata_fabricated"])
        self.assertFalse(boundary["execution_through_schemarouter"])
        self.assertTrue(boundary["mcp_agent_owns_lifecycle"])
        self.assertGreater(summary["mcp_tool_calls_via_mcp_agent"], 0)


if __name__ == "__main__":
    unittest.main()
