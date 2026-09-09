"""Unit tests for Phase 2 Host AI Bot and lifecycle state machine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.host_bot.dispatcher import HostBotDispatcher
from src.host_bot.draft_generator import AcceptanceCriteria, generate_acceptance_criteria
from src.host_bot.lifecycle import (
    MAX_REASSIGNMENTS,
    MAX_RETRIES_PER_WORKER,
    TaskLifecycleStore,
    TaskState,
)


class TestDraftGenerator(unittest.TestCase):
    def test_acceptance_criteria_to_markdown(self) -> None:
        criteria = AcceptanceCriteria(
            interface_spec="def parse_csv(path: str) -> list[dict]: pass",
            test_cases="1. Case 1\n2. Case 2",
            notes="No eval() allowed",
        )
        md = criteria.to_markdown()
        self.assertIn("인터페이스 스펙", md)
        self.assertIn("테스트 케이스", md)
        self.assertIn("보안 및 제약 사항", md)
        self.assertIn("def parse_csv", md)

    def test_generate_acceptance_criteria_fallback(self) -> None:
        criteria = generate_acceptance_criteria("CSV 파서 구현 필요")
        self.assertTrue(len(criteria.interface_spec) > 0)
        self.assertTrue(len(criteria.test_cases) > 0)
        self.assertTrue(len(criteria.notes) > 0)


class TestTaskLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "tasks.db"
        self.store = TaskLifecycleStore(self.db_path)
        self.dispatcher = HostBotDispatcher(store=self.store)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_full_success_flow(self) -> None:
        # 1. Create task
        task, criteria = self.dispatcher.handle_task_created(
            task_id="task-01",
            title="CSV Parser",
            raw_description="Parse CSV files into dictionaries",
            creator="jimin",
        )
        self.assertEqual(task.status, TaskState.PENDING_APPROVAL)
        self.assertIsNotNone(task.interface_spec)

        # 2. Cannot assign before approval (Fail-closed gate)
        with self.assertRaises(ValueError):
            self.dispatcher.handle_worker_assigned("task-01", "seoyeon")

        # 3. Creator approves
        task = self.dispatcher.handle_task_approved("task-01", approver="jimin")
        self.assertEqual(task.status, TaskState.OPEN)

        # 4. Assign worker
        task = self.dispatcher.handle_worker_assigned("task-01", "seoyeon")
        self.assertEqual(task.status, TaskState.ASSIGNED)
        self.assertEqual(task.current_worker, "seoyeon")
        self.assertEqual(task.current_branch, "feat/csv-parser-seoyeon")
        self.assertEqual(task.base_branch, "main")

        # 5. Submit PR
        task = self.dispatcher.handle_pr_submitted("task-01", pr_number=10, branch_name=task.current_branch)
        self.assertEqual(task.status, TaskState.SUBMITTED)

        # 6. Verification Pass
        task, action, msg = self.dispatcher.handle_verification_result("task-01", passed=True)
        self.assertEqual(task.status, TaskState.PASSED)
        self.assertEqual(action, "PASS")

    def test_retry_and_reassignment_limits(self) -> None:
        # 1. Create and open task
        self.dispatcher.handle_task_created("task-02", "Data Aggregator", "Aggregate numbers", "jimin")
        self.dispatcher.handle_task_approved("task-02", "jimin")

        # Worker 1: seoyeon
        self.dispatcher.handle_worker_assigned("task-02", "seoyeon")

        # 1st Fail -> RETRY_1 (worker retry granted)
        task, action, msg = self.dispatcher.handle_verification_result("task-02", passed=False, failure_reason="Assertion failed")
        self.assertEqual(action, "RETRY")
        self.assertEqual(task.status, TaskState.RETRY_1)
        self.assertEqual(task.worker_retry_count, 1)

        # 2nd Fail (retry also failed) -> REASSIGNED_1
        task, action, msg = self.dispatcher.handle_verification_result("task-02", passed=False, failure_reason="Still failing")
        self.assertEqual(action, "REASSIGN")
        self.assertEqual(task.status, TaskState.REASSIGNED_1)
        self.assertEqual(task.reassign_count, 1)
        self.assertEqual(task.worker_retry_count, 0)
        self.assertIn("feat/data-aggregator-seoyeon", msg)

        # Worker 2: dohyun
        task = self.dispatcher.handle_worker_assigned("task-02", "dohyun")
        self.assertEqual(task.current_branch, "feat/data-aggregator-seoyeon-dohyun")
        self.assertEqual(task.base_branch, "feat/data-aggregator-seoyeon")

        # Worker 2: 1st Fail -> RETRY_2
        task, action, _ = self.dispatcher.handle_verification_result("task-02", passed=False)
        self.assertEqual(action, "RETRY")
        self.assertEqual(task.status, TaskState.RETRY_2)

        # Worker 2: 2nd Fail -> REASSIGNED_2 (final reassignment)
        task, action, _ = self.dispatcher.handle_verification_result("task-02", passed=False)
        self.assertEqual(action, "REASSIGN")
        self.assertEqual(task.status, TaskState.REASSIGNED_2)
        self.assertEqual(task.reassign_count, 2)

        # Worker 3: minjun
        task = self.dispatcher.handle_worker_assigned("task-02", "minjun")
        self.assertEqual(task.current_branch, "feat/data-aggregator-seoyeon-dohyun-minjun")

        # Worker 3: 1st Fail -> RETRY_2
        task, action, _ = self.dispatcher.handle_verification_result("task-02", passed=False)
        self.assertEqual(action, "RETRY")

        # Worker 3: 2nd Fail -> FAILED_PERMANENTLY (Denial-of-Wallet prevention)
        task, action, msg = self.dispatcher.handle_verification_result("task-02", passed=False)
        self.assertEqual(action, "PERMANENT_FAIL")
        self.assertEqual(task.status, TaskState.FAILED_PERMANENTLY)
        self.assertIn("FAILED_PERMANENTLY", msg)


if __name__ == "__main__":
    unittest.main()
