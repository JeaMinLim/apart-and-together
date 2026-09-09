"""Unit tests for the Shared Mailbox system."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.mailbox.store import MailboxStore
from src.mcp_server import MCPServer


class TestMailboxStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "tasks.json"
        self.store = MailboxStore(self.store_path)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_create_and_get_task(self) -> None:
        task = self.store.create_task(
            title="Review DB Schema",
            content="CREATE TABLE users (id INT PRIMARY KEY);",
            task_type="code_review",
            author="claude-desktop",
        )
        self.assertTrue(task.task_id.startswith("task-"))
        self.assertEqual(task.title, "Review DB Schema")
        self.assertEqual(task.status, "pending")

        fetched = self.store.get_task(task.task_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Review DB Schema")

    def test_list_tasks_filter(self) -> None:
        self.store.create_task("T1", "Content 1", task_type="code_review")
        self.store.create_task("T2", "Content 2", task_type="question")

        all_tasks = self.store.list_tasks()
        self.assertEqual(len(all_tasks), 2)

        review_tasks = self.store.list_tasks(task_type="code_review")
        self.assertEqual(len(review_tasks), 1)
        self.assertEqual(review_tasks[0].title, "T1")

    def test_submit_result_with_clean_code(self) -> None:
        task = self.store.create_task("Write add function", "Please write add(a, b)")
        clean_code = "```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```"

        res = self.store.submit_result(task.task_id, clean_code, contributor="cursor-pro")
        self.assertEqual(res.result_id, "res-01")
        self.assertEqual(res.submitted_by, "cursor-pro")
        self.assertTrue(res.ast_audit_passed)
        self.assertIn("PASSED ✅", res.ast_audit_details or "")

        # Task status should update to in_progress
        updated_task = self.store.get_task(task.task_id)
        self.assertEqual(updated_task.status, "in_progress")
        self.assertEqual(len(updated_task.results), 1)

    def test_submit_result_with_dangerous_code(self) -> None:
        task = self.store.create_task("Run command", "Run bash command")
        danger_code = "```python\nimport os\nos.system('rm -rf /')\n```"

        res = self.store.submit_result(task.task_id, danger_code, contributor="bad-actor")
        self.assertFalse(res.ast_audit_passed)
        self.assertIn("FAILED ❌", res.ast_audit_details or "")
        self.assertIn("SEC-SHELL-EXEC", res.ast_audit_details or "")


class TestMailboxMCPIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "mcp_tasks.json"
        self.server = MCPServer(self.store_path)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_mcp_mailbox_flow(self) -> None:
        # 1. Claude posts task
        post_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "post_task_to_mailbox",
                "arguments": {
                    "title": "Optimizing CSV loader",
                    "content": "def load(): pass",
                    "author": "claude-desktop",
                },
            },
        }
        resp = self.server.process_message(post_msg)
        self.assertFalse(resp["result"]["isError"])
        post_text = resp["result"]["content"][0]["text"]
        self.assertIn("Task successfully posted", post_text)

        # 2. Cursor lists pending tasks
        list_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_pending_tasks",
                "arguments": {},
            },
        }
        resp = self.server.process_message(list_msg)
        list_text = resp["result"]["content"][0]["text"]
        self.assertIn("Optimizing CSV loader", list_text)

        # 3. Cursor submits review
        tasks = self.server.mailbox.list_tasks()
        task_id = tasks[0].task_id

        submit_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "submit_task_result",
                "arguments": {
                    "task_id": task_id,
                    "result_content": "Consider using pandas or csv.DictReader for speed.",
                    "contributor": "cursor-pro",
                },
            },
        }
        resp = self.server.process_message(submit_msg)
        self.assertFalse(resp["result"]["isError"])
        self.assertIn("submitted successfully", resp["result"]["content"][0]["text"])

        # 4. Claude gets completed reviews
        get_res_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_completed_task_results",
                "arguments": {"task_id": task_id},
            },
        }
        resp = self.server.process_message(get_res_msg)
        results_text = resp["result"]["content"][0]["text"]
        self.assertIn("From: cursor-pro", results_text)
        self.assertIn("csv.DictReader", results_text)


if __name__ == "__main__":
    unittest.main()
