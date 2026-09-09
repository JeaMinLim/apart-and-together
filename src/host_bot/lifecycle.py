"""Task lifecycle state machine and SQLite store for Phase 2 Host AI Bot."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TaskState(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    SUBMITTED = "SUBMITTED"
    PASSED = "PASSED"
    RETRY_1 = "RETRY_1"
    REASSIGNED_1 = "REASSIGNED_1"
    RETRY_2 = "RETRY_2"
    REASSIGNED_2 = "REASSIGNED_2"
    FAILED_PERMANENTLY = "FAILED_PERMANENTLY"
    MERGED = "MERGED"


MAX_RETRIES_PER_WORKER = 1
MAX_REASSIGNMENTS = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:24] if s else "task"


@dataclass
class TaskRecord:
    task_id: str
    title: str
    slug: str
    raw_description: str
    interface_spec: Optional[str]
    test_cases: Optional[str]
    notes: Optional[str]
    creator: str
    current_worker: Optional[str]
    status: TaskState
    worker_retry_count: int
    reassign_count: int
    current_branch: Optional[str]
    base_branch: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class TaskLifecycleStore:
    """Manages task lifecycle transitions and persistence in a lightweight SQLite database."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.db_path = project_root / ".state" / "tasks.db"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    raw_description TEXT NOT NULL,
                    interface_spec TEXT,
                    test_cases TEXT,
                    notes TEXT,
                    creator TEXT NOT NULL,
                    current_worker TEXT,
                    status TEXT NOT NULL,
                    worker_retry_count INTEGER DEFAULT 0,
                    reassign_count INTEGER DEFAULT 0,
                    current_branch TEXT,
                    base_branch TEXT DEFAULT 'main',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    worker TEXT,
                    branch_name TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                )
                """
            )
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            title=row["title"],
            slug=row["slug"],
            raw_description=row["raw_description"],
            interface_spec=row["interface_spec"],
            test_cases=row["test_cases"],
            notes=row["notes"],
            creator=row["creator"],
            current_worker=row["current_worker"],
            status=TaskState(row["status"]),
            worker_retry_count=row["worker_retry_count"],
            reassign_count=row["reassign_count"],
            current_branch=row["current_branch"],
            base_branch=row["base_branch"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _log_event(
        self,
        conn: sqlite3.Connection,
        task_id: str,
        action: str,
        worker: Optional[str] = None,
        branch: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO task_events (task_id, worker, branch_name, action, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, worker, branch, action, details, _utc_now_iso()),
        )

    def create_draft(
        self,
        task_id: str,
        title: str,
        raw_description: str,
        creator: str,
    ) -> TaskRecord:
        """Create a new task draft in DRAFT status."""
        now = _utc_now_iso()
        slug = _slugify(title)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, title, slug, raw_description, creator,
                    status, worker_retry_count, reassign_count, base_branch, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'main', ?, ?)
                """,
                (task_id, title, slug, raw_description, creator, TaskState.DRAFT.value, now, now),
            )
            self._log_event(conn, task_id, "CREATE_DRAFT", details=f"Title: {title}")
            conn.commit()

        return self.get_task(task_id)  # type: ignore

    def set_acceptance_criteria(
        self,
        task_id: str,
        interface_spec: str,
        test_cases: str,
        notes: str,
    ) -> TaskRecord:
        """Attach AI-generated acceptance criteria to a task and transition to PENDING_APPROVAL."""
        now = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET interface_spec = ?, test_cases = ?, notes = ?,
                    status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    interface_spec,
                    test_cases,
                    notes,
                    TaskState.PENDING_APPROVAL.value,
                    now,
                    task_id,
                ),
            )
            self._log_event(conn, task_id, "SET_ACCEPTANCE_CRITERIA", details="Pending creator approval")
            conn.commit()

        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")
        return task

    def approve_task(self, task_id: str, approver: str) -> TaskRecord:
        """Approve task criteria (Fail-closed Gate). Transitions from PENDING_APPROVAL to OPEN."""
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")
        if task.status != TaskState.PENDING_APPROVAL:
            raise ValueError(f"Task '{task_id}' is in {task.status.value}, cannot approve.")
        if approver.lower() != task.creator.lower() and approver.lower() != "host":
            raise PermissionError(f"Approver '{approver}' is not the task creator ({task.creator}) or host.")

        now = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskState.OPEN.value, now, task_id),
            )
            self._log_event(conn, task_id, "APPROVE_TASK", worker=approver, details="Task approved and opened")
            conn.commit()

        return self.get_task(task_id)  # type: ignore

    def assign_worker(self, task_id: str, worker: str) -> TaskRecord:
        """Assign worker to open task and determine worker branch."""
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")
        if task.status not in (TaskState.OPEN, TaskState.REASSIGNED_1, TaskState.REASSIGNED_2):
            raise ValueError(f"Cannot assign worker to task in status '{task.status.value}'.")

        # Branch naming convention:
        # Initial: feat/<slug>-<worker>
        # Reassigned: previous branch name extended with new worker
        if task.current_branch:
            branch_name = f"{task.current_branch}-{worker}"
            base_branch = task.current_branch
        else:
            branch_name = f"feat/{task.slug}-{worker}"
            base_branch = "main"

        now = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET current_worker = ?, current_branch = ?, base_branch = ?,
                    status = ?, worker_retry_count = 0, updated_at = ?
                WHERE task_id = ?
                """,
                (worker, branch_name, base_branch, TaskState.ASSIGNED.value, now, task_id),
            )
            self._log_event(
                conn,
                task_id,
                "ASSIGN_WORKER",
                worker=worker,
                branch=branch_name,
                details=f"Base branch: {base_branch}",
            )
            conn.commit()

        return self.get_task(task_id)  # type: ignore

    def submit_pr(self, task_id: str, pr_number: int, branch_name: str) -> TaskRecord:
        """Record PR submission."""
        now = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, current_branch = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskState.SUBMITTED.value, branch_name, now, task_id),
            )
            self._log_event(conn, task_id, "SUBMIT_PR", branch=branch_name, details=f"PR #{pr_number}")
            conn.commit()

        return self.get_task(task_id)  # type: ignore

    def record_verification_pass(self, task_id: str) -> TaskRecord:
        """Mark task as passed verification."""
        now = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskState.PASSED.value, now, task_id),
            )
            self._log_event(conn, task_id, "PASS_VERIFICATION", details="All security and tests passed ✅")
            conn.commit()

        return self.get_task(task_id)  # type: ignore

    def record_verification_fail(
        self,
        task_id: str,
        reason: str,
        ast_violations: Optional[List[str]] = None,
    ) -> Tuple[TaskRecord, str, str]:
        """Handle verification failure by enforcing retry/reassignment limits.

        Returns:
            Tuple of (updated_task, action_type, context_message)
            action_type: 'RETRY' | 'REASSIGN' | 'PERMANENT_FAIL'
        """
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        now = _utc_now_iso()
        violations_text = "\n".join(ast_violations) if ast_violations else "None"
        fail_context = f"Reason: {reason}\nAST Violations: {violations_text}"

        # 1. Check if current worker can retry (Limit = 1)
        if task.worker_retry_count < MAX_RETRIES_PER_WORKER:
            new_retry = task.worker_retry_count + 1
            new_state = TaskState.RETRY_1 if task.reassign_count == 0 else TaskState.RETRY_2
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, worker_retry_count = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (new_state.value, new_retry, now, task_id),
                )
                self._log_event(
                    conn,
                    task_id,
                    "RETRY_GRANTED",
                    worker=task.current_worker,
                    details=f"Worker retry #{new_retry} granted: {reason}",
                )
                conn.commit()

            updated = self.get_task(task_id)
            msg = (
                f"⚠️ 1차 검증 실패: 작업자 @{task.current_worker}님에게 1회 재시도 기회가 부여되었습니다.\n"
                f"실패 원인:\n{fail_context}"
            )
            return updated, "RETRY", msg  # type: ignore

        # 2. Worker retry exhausted. Can we reassign? (Limit = 2)
        if task.reassign_count < MAX_REASSIGNMENTS:
            new_reassign = task.reassign_count + 1
            new_state = TaskState.REASSIGNED_1 if new_reassign == 1 else TaskState.REASSIGNED_2
            prev_worker = task.current_worker
            prev_branch = task.current_branch

            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, reassign_count = ?, worker_retry_count = 0,
                        current_worker = NULL, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (new_state.value, new_reassign, now, task_id),
                )
                self._log_event(
                    conn,
                    task_id,
                    "REASSIGN_TRIGGERED",
                    worker=prev_worker,
                    branch=prev_branch,
                    details=f"Reassignment #{new_reassign}. Previous worker retry failed.",
                )
                conn.commit()

            updated = self.get_task(task_id)
            msg = (
                f"🚨 재시도 검증 실패: @{prev_worker}님의 재시도가 실패하여 다른 참여자에게 과제가 재할당됩니다.\n"
                f"- 원본 브랜치: `{prev_branch}` (지우지 않고 보존됨)\n"
                f"- 새 참여자 지침: `{prev_branch}`에서 새 브랜치를 파서 이어서 작업하세요.\n"
                f"- 직전 실패 사유:\n{fail_context}"
            )
            return updated, "REASSIGN", msg  # type: ignore

        # 3. Both retries and reassignment limits reached -> Permanent Fail
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskState.FAILED_PERMANENTLY.value, now, task_id),
            )
            self._log_event(
                conn,
                task_id,
                "FAILED_PERMANENTLY",
                details="Max retry and reassignment limits reached. Task closed to prevent Denial-of-Wallet.",
            )
            conn.commit()

        updated = self.get_task(task_id)
        msg = (
            f"🛑 과제 영구 중단 ({TaskState.FAILED_PERMANENTLY.value}):\n"
            f"재시도(작업자당 1회) 및 재할당(최대 2회) 상한에 모두 도달했습니다.\n"
            f"자원 고갈(Denial-of-Wallet) 방지 원칙에 따라 과제가 자동 종료됩니다.\n"
            f"과제 수락 기준이나 인터페이스 스펙을 재검토해야 합니다."
        )
        return updated, "PERMANENT_FAIL", msg  # type: ignore

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Fetch a task by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def list_tasks(self, status: Optional[TaskState] = None) -> List[TaskRecord]:
        """List tasks, optionally filtered by status."""
        query = "SELECT * FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC"

        with self._get_conn() as conn:
            cursor = conn.execute(query, tuple(params))
            return [self._row_to_record(r) for r in cursor.fetchall()]
