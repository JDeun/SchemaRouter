"""Focused contract test for the OpenAI Agents SDK external validation."""

from __future__ import annotations

import unittest

from scripts.external_validation_openai_agents import evaluate


class OpenAIAgentsMCPFilterContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_dynamic_filter_boundary(self) -> None:
        result = await evaluate()

        summary = result["summary"]
        boundary = result["boundary"]

        self.assertEqual(summary["required_tool_recall"], 1.0)
        self.assertEqual(summary["unsupported_rejection"], 1.0)
        self.assertEqual(summary["retrieval_task_success_rate"], 1.0)
        self.assertTrue(summary["approval_policy_preserved"])
        self.assertTrue(summary["input_guardrail_preserved"])
        self.assertTrue(summary["output_guardrail_preserved"])
        self.assertEqual(summary["mcp_tool_calls_during_evaluation"], 0)
        self.assertFalse(boundary["execution_through_schemarouter"])


if __name__ == "__main__":
    unittest.main()
