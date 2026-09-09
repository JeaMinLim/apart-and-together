"""Event dispatcher connecting external GitHub/CLI events to the Host AI Bot lifecycle."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.host_bot.draft_generator import AcceptanceCriteria, generate_acceptance_criteria
from src.host_bot.lifecycle import TaskLifecycleStore, TaskRecord, TaskState
from src.multi_ai.hub import MultiAIHub


class HostBotDispatcher:
    """Coordinates acceptance criteria drafting and state transitions upon events."""

    def __init__(
        self,
        store: Optional[TaskLifecycleStore] = None,
        hub: Optional[MultiAIHub] = None,
    ) -> None:
        self.store = store or TaskLifecycleStore()
        self.hub = hub or MultiAIHub()

    def handle_task_created(
        self,
        task_id: str,
        title: str,
        raw_description: str,
        creator: str,
    ) -> Tuple[TaskRecord, AcceptanceCriteria]:
        """Handle new free-form task creation: draft criteria and lock behind approval gate."""
        task = self.store.create_draft(task_id, title, raw_description, creator)
        criteria = generate_acceptance_criteria(raw_description, hub=self.hub)

        updated_task = self.store.set_acceptance_criteria(
            task_id=task.task_id,
            interface_spec=criteria.interface_spec,
            test_cases=criteria.test_cases,
            notes=criteria.notes,
        )
        return updated_task, criteria

    def handle_task_approved(self, task_id: str, approver: str) -> TaskRecord:
        """Handle creator/host approval gate."""
        return self.store.approve_task(task_id, approver)

    def handle_worker_assigned(self, task_id: str, worker: str) -> TaskRecord:
        """Handle assigning worker and determining branch."""
        return self.store.assign_worker(task_id, worker)

    def handle_pr_submitted(self, task_id: str, pr_number: int, branch_name: str) -> TaskRecord:
        """Handle PR submission."""
        return self.store.submit_pr(task_id, pr_number, branch_name)

    def handle_verification_result(
        self,
        task_id: str,
        passed: bool,
        failure_reason: str = "",
        ast_violations: Optional[List[str]] = None,
    ) -> Tuple[TaskRecord, str, str]:
        """Handle Phase 1 verification outcome."""
        if passed:
            task = self.store.record_verification_pass(task_id)
            return (
                task,
                "PASS",
                "🎉 모든 안전성(AST 보안) 및 적합성(테스트) 검증을 통과했습니다! PR 병합이 승인되었습니다.",
            )
        return self.store.record_verification_fail(
            task_id=task_id,
            reason=failure_reason,
            ast_violations=ast_violations,
        )
