"""Unit tests for Apart & Together MCP server."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.mcp_server import MCPServer
from src.multi_ai.providers.base import LLMResponse


class TestMCPServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MCPServer()

    def test_initialize(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "apart-and-together-mcp")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_ping(self) -> None:
        msg = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
        resp = self.server.process_message(msg)
        self.assertEqual(resp, {"jsonrpc": "2.0", "id": 2, "result": {}})

    def test_tools_list(self) -> None:
        msg = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        self.assertIn("audit_code_security", tool_names)
        self.assertIn("ask_other_ais", tool_names)
        self.assertIn("synthesize_with_other_ais", tool_names)
        self.assertIn("get_multi_ai_status", tool_names)

    def test_audit_code_clean(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "audit_code_security",
                "arguments": {"code": "def add(a, b):\n    return a + b\n"},
            },
        }
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        content_text = resp["result"]["content"][0]["text"]
        self.assertIn("PASSED ✅", content_text)
        self.assertFalse(resp["result"]["isError"])

    def test_audit_code_dangerous(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "audit_code_security",
                "arguments": {"code": "import os\nos.system('rm -rf /')\n"},
            },
        }
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        content_text = resp["result"]["content"][0]["text"]
        self.assertIn("FAILED ❌", content_text)
        self.assertIn("SEC-SHELL-EXEC", content_text)

    def test_get_multi_ai_status(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_multi_ai_status",
                "arguments": {},
            },
        }
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        content_text = resp["result"]["content"][0]["text"]
        self.assertIn("Multi-AI Hub Status", content_text)

    def test_unknown_tool(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "non_existent_tool",
                "arguments": {},
            },
        }
        resp = self.server.process_message(msg)
        self.assertIsNotNone(resp)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("Unknown tool", resp["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
