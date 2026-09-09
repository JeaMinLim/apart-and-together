"""Shared local mailbox storage for subscription AI collaboration."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.verify.ast_scanner import scan_source


def _current_iso_time() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskResult:
    result_id: str
    submitted_by: str
    submitted_at: str
    content: str
    ast_audit_passed: Optional[bool] = None
    ast_audit_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskResult:
        return cls(**data)


@dataclass
class MailboxTask:
    task_id: str
    title: str
    task_type: str
    content: str
    author: str
    created_at: str
    status: str = "pending"  # "pending", "in_progress", "completed"
    results: List[TaskResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["results"] = [r.to_dict() for r in self.results]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MailboxTask:
        results_data = data.pop("results", [])
        task = cls(**data)
        task.results = [TaskResult.from_dict(r) for r in results_data]
        return task


def _extract_python_code_snippets(text: str) -> List[str]:
    """Extract python snippets from markdown code blocks or return text if looks like python."""
    blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if blocks:
        return [b.strip() for b in blocks if b.strip()]
    if any(keyword in text for keyword in ("import ", "def ", "class ", "return ")):
        return [text.strip()]
    return []


class MailboxStore:
    """Manages reading and writing tasks to a local JSON mailbox."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        if storage_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.storage_path = project_root / ".mailbox" / "tasks.json"
        else:
            self.storage_path = Path(storage_path)

        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.is_file():
            self._write_tasks_atomic({})

    def _read_tasks(self) -> Dict[str, MailboxTask]:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return {k: MailboxTask.from_dict(v) for k, v in raw_data.items()}
        except Exception:
            return {}

    def _write_tasks_atomic(self, tasks: Dict[str, MailboxTask]) -> None:
        raw_data = {k: v.to_dict() for k, v in tasks.items()}
        temp_dir = self.storage_path.parent
        # Atomic replacement via temporary file
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(raw_data, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name
        os.replace(temp_name, self.storage_path)

    def create_task(
        self,
        title: str,
        content: str,
        task_type: str = "code_review",
        author: str = "unknown",
    ) -> MailboxTask:
        tasks = self._read_tasks()
        # Generate readable ID: task-YYMMDD-sequence
        date_str = datetime.now().strftime("%Y%m%d")
        existing_today = [
            tid for tid in tasks
            if tid.startswith(f"task-{date_str}")
        ]
        seq = len(existing_today) + 1
        task_id = f"task-{date_str}-{seq:02d}"

        task = MailboxTask(
            task_id=task_id,
            title=title,
            task_type=task_type,
            content=content,
            author=author,
            created_at=_current_iso_time(),
            status="pending",
            results=[],
        )
        tasks[task_id] = task
        self._write_tasks_atomic(tasks)
        return task

    def get_task(self, task_id: str) -> Optional[MailboxTask]:
        tasks = self._read_tasks()
        return tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[MailboxTask]:
        tasks = self._read_tasks()
        out = list(tasks.values())
        if status:
            out = [t for t in out if t.status.lower() == status.lower()]
        if task_type:
            out = [t for t in out if t.task_type.lower() == task_type.lower()]
        # Sort descending by created_at
        out.sort(key=lambda t: t.created_at, reverse=True)
        return out

    def submit_result(
        self,
        task_id: str,
        content: str,
        contributor: str = "unknown",
        auto_audit: bool = True,
    ) -> TaskResult:
        tasks = self._read_tasks()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found in mailbox.")

        # Check Python code with AST security auditor if auto_audit enabled
        audit_passed: Optional[bool] = None
        audit_details: Optional[str] = None

        if auto_audit:
            snippets = _extract_python_code_snippets(content)
            if snippets:
                all_findings = []
                for idx, snip in enumerate(snippets, 1):
                    findings = scan_source(snip, file_path=f"<{contributor}_snippet_{idx}.py>")
                    all_findings.extend(findings)

                if not all_findings:
                    audit_passed = True
                    audit_details = "AST Security Audit: PASSED ✅ (No dangerous calls found)"
                else:
                    audit_passed = False
                    audit_details = (
                        f"AST Security Audit: FAILED ❌ ({len(all_findings)} violations detected):\n"
                        + "\n".join(f"- [{f.severity.value}] {f.rule_id} at line {f.line}: {f.message}" for f in all_findings)
                    )

        result_id = f"res-{len(task.results) + 1:02d}"
        res = TaskResult(
            result_id=result_id,
            submitted_by=contributor,
            submitted_at=_current_iso_time(),
            content=content,
            ast_audit_passed=audit_passed,
            ast_audit_details=audit_details,
        )

        task.results.append(res)
        if task.status == "pending":
            task.status = "in_progress"

        tasks[task_id] = task
        self._write_tasks_atomic(tasks)
        return res

    def update_status(self, task_id: str, status: str) -> Optional[MailboxTask]:
        tasks = self._read_tasks()
        task = tasks.get(task_id)
        if not task:
            return None
        task.status = status
        tasks[task_id] = task
        self._write_tasks_atomic(tasks)
        return task

    def clear(self) -> None:
        self._write_tasks_atomic({})
