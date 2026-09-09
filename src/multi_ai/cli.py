"""Command-line interface for Multi-AI Hub."""

from __future__ import annotations

import argparse
import re
import sys
from typing import List, Optional

from src.multi_ai.config import load_ai_config
from src.multi_ai.hub import MultiAIHub
from src.verify.ast_scanner import scan_source


def print_banner(title: str, char: str = "=") -> None:
    line = char * 60
    print(f"\n{line}")
    print(f"  {title}")
    print(f"{line}\n")


def cmd_status(hub: MultiAIHub) -> int:
    print_banner("Apart & Together — Multi-AI Hub Status")
    configs = load_ai_config()

    print(f"{'Provider':<12} | {'Display Name':<26} | {'Default Model':<28} | {'Status':<10}")
    print("-" * 84)

    active_count = 0
    for name, cfg in configs.items():
        status_str = "ACTIVE ✅" if cfg.is_active else "DISABLED ⚪"
        if cfg.is_active:
            active_count += 1
        print(f"{name:<12} | {cfg.display_name:<26} | {cfg.default_model:<28} | {status_str:<10}")

    print("-" * 84)
    print(f"Total Active Providers: {active_count} / {len(configs)}")
    if active_count == 0:
        print("\n💡 활성화된 AI가 없습니다. .env 파일이나 환경 변수를 설정해주세요.")
        print("   예시 템플릿: cp .env.example .env")
        print("   설정 가능 키: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY, OPENROUTER_API_KEY, OLLAMA_BASE_URL")
    return 0


def cmd_ask(hub: MultiAIHub, prompt: str, models: Optional[List[str]], system: Optional[str]) -> int:
    if not hub.active_names:
        print("❌ 활성화된 AI 프로바이더가 없습니다. .env 파일을 먼저 설정해주세요.")
        return 1

    targets = models if models else hub.active_names
    print_banner(f"Querying {len(targets)} AI models in parallel...")
    print(f"User Prompt: {prompt}\n")

    responses = hub.query_many(targets, prompt, system_prompt=system)

    for name, resp in responses.items():
        print(f"┌─ [{resp.provider.upper()} - {resp.model}] ({resp.latency_seconds:.2f}s) {'✅' if resp.success else '❌'}")
        if resp.success:
            print(resp.content)
        else:
            print(f"Error: {resp.error_message}")
        print("└" + "─" * 58 + "\n")

    return 0


def cmd_synth(hub: MultiAIHub, prompt: str, judge: Optional[str], system: Optional[str]) -> int:
    if not hub.active_names:
        print("❌ 활성화된 AI 프로바이더가 없습니다. .env 파일을 먼저 설정해주세요.")
        return 1

    print_banner("Multi-AI Consensus & Synthesis")
    print(f"Gathering opinions from {hub.active_names} and synthesizing...")

    res = hub.synthesize(prompt, judge_provider=judge, system_prompt=system)
    if res.success:
        print(f"[{res.provider.upper()} Synthesis Result - {res.latency_seconds:.2f}s]:\n")
        print(res.content)
        return 0
    else:
        print(f"Synthesis failed: {res.error_message}")
        return 1


def _extract_python_code(text: str) -> str:
    """Extract python code block if wrapped in markdown backticks."""
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def cmd_code(hub: MultiAIHub, task: str, models: Optional[List[str]]) -> int:
    """Ask models to generate code, then audit their outputs with Phase 1 AST scanner."""
    if not hub.active_names:
        print("❌ 활성화된 AI 프로바이더가 없습니다. .env 파일을 먼저 설정해주세요.")
        return 1

    targets = models if models else hub.active_names
    prompt = (
        f"Write Python code to solve the following task. "
        f"Provide only the clean, safe Python code without dangerous shell or eval calls:\n\n{task}"
    )

    print_banner(f"Multi-AI Code Generation & AST Security Verification ({len(targets)} models)")
    responses = hub.query_many(targets, prompt)

    for name, resp in responses.items():
        print(f"==================================================")
        print(f"🤖 Model: {resp.provider.upper()} ({resp.model}) - {resp.latency_seconds:.2f}s")
        print(f"==================================================")

        if not resp.success:
            print(f"❌ Generation failed: {resp.error_message}\n")
            continue

        raw_code = _extract_python_code(resp.content)
        print("Generated Code:")
        print(raw_code)
        print("\n🛡️ Running Phase 1 AST Security Scan on generated code...")

        findings = scan_source(raw_code, file_path=f"<{name}_output.py>")
        if not findings:
            print("Audit Status: PASSED ✅ (No dangerous calls found)\n")
        else:
            print(f"Audit Status: FAILED ❌ ({len(findings)} security violations detected!)")
            for f in findings:
                print(f"  - [{f.severity.value}] {f.rule_id} at line {f.line}: {f.message} (Target: {f.target})")
            print("")

    return 0


def cmd_mailbox(args: argparse.Namespace) -> int:
    from src.mailbox.store import MailboxStore

    store = MailboxStore()
    action = args.mailbox_action

    if action == "list" or not action:
        tasks = store.list_tasks()
        print_banner("Apart & Together — Shared Mailbox Tasks")
        if not tasks:
            print("우편함이 비어 있습니다. (등록된 일감 없음)")
            return 0

        print(f"{'Task ID':<20} | {'Type':<14} | {'Status':<12} | {'Author':<14} | {'Title'}")
        print("-" * 84)
        for t in tasks:
            print(f"{t.task_id:<20} | {t.task_type:<14} | {t.status:<12} | {t.author:<14} | {t.title}")
        print("-" * 84)
        print(f"Total tasks: {len(tasks)}\n")
        return 0

    if action == "view":
        task = store.get_task(args.task_id)
        if not task:
            print(f"❌ 일감 '{args.task_id}'을(를) 찾을 수 없습니다.")
            return 1

        print_banner(f"Task Details: {task.task_id}")
        print(f"제목:     {task.title}")
        print(f"유형:     {task.task_type}")
        print(f"작성자:   {task.author}")
        print(f"생성일:   {task.created_at}")
        print(f"상태:     {task.status}\n")
        print("--- 내용 / 코드 ---")
        print(task.content)
        print("\n--- 제출된 피드백 / 결과 (" + str(len(task.results)) + "건) ---")
        if not task.results:
            print("아직 제출된 리뷰나 결과가 없습니다.")
        for r in task.results:
            audit = f" [보안감사: {r.ast_audit_details}]" if r.ast_audit_details else ""
            print(f"• [{r.result_id}] By {r.submitted_by} ({r.submitted_at}){audit}:")
            print(r.content)
            print("-" * 40)
        return 0

    if action == "post":
        task = store.create_task(
            title=args.title,
            content=args.content,
            task_type=args.type or "code_review",
            author=args.author or "cli_user",
        )
        print(f"📬 우편함에 새 일감이 등록되었습니다!")
        print(f"  ID: {task.task_id} ({task.title})")
        return 0

    if action == "clear":
        store.clear()
        print("🧹 공유 우편함의 모든 일감을 삭제했습니다.")
        return 0

    return 0


def cmd_bot(args: argparse.Namespace, hub: MultiAIHub) -> int:
    from src.host_bot.dispatcher import HostBotDispatcher
    from src.host_bot.draft_generator import generate_acceptance_criteria
    from src.host_bot.lifecycle import TaskLifecycleStore

    store = TaskLifecycleStore()
    dispatcher = HostBotDispatcher(store=store, hub=hub)
    action = args.bot_action

    if action == "draft":
        print_banner("Apart & Together — Host AI Draft Generator")
        context = f"{args.goal}\n{args.description}" if getattr(args, "description", None) else args.goal
        criteria = generate_acceptance_criteria(raw_description=context, hub=hub)
        print(criteria.to_markdown())
        return 0

    if action == "create":
        task, criteria = dispatcher.handle_task_created(
            task_id=args.task_id,
            title=args.title,
            raw_description=args.goal,
            creator=args.creator or "host",
        )
        print_banner(f"Task Created & Criteria Drafted: {task.task_id}")
        print(f"상태: {task.status.value} (등록자 승인 대기 중 - Fail-closed)")
        print("\n" + criteria.to_markdown())
        print("\n승인 명령어: ./bin/multi-ai bot approve " + task.task_id)
        return 0

    if action == "approve":
        approver = args.approver or "host"
        try:
            task = dispatcher.handle_task_approved(args.task_id, approver=approver)
            print(f"✅ 과제 '{task.task_id}' 승인 완료! 상태: {task.status.value} (참여자 배정 가능)")
            return 0
        except Exception as exc:
            print(f"❌ 승인 실패: {exc}")
            return 1

    if action == "assign":
        try:
            task = dispatcher.handle_worker_assigned(args.task_id, worker=args.worker)
            print(f"👤 작업자 배정 완료: @{task.current_worker}")
            print(f"  - 작업 브랜치: `{task.current_branch}`")
            print(f"  - 베이스 브랜치: `{task.base_branch}`")
            print(f"  - 상태: {task.status.value}")
            return 0
        except Exception as exc:
            print(f"❌ 배정 실패: {exc}")
            return 1

    if action == "pass":
        try:
            task, action_type, msg = dispatcher.handle_verification_result(args.task_id, passed=True)
            print(f"🎉 {msg}")
            print(f"  - 과제 '{task.task_id}' 상태: {task.status.value}")
            return 0
        except Exception as exc:
            print(f"❌ 오류: {exc}")
            return 1

    if action == "fail":
        reason = args.reason or "단위 테스트 불일치"
        try:
            task, action_type, msg = dispatcher.handle_verification_result(
                args.task_id,
                passed=False,
                failure_reason=reason,
            )
            print_banner(f"Verification Failed — Action: {action_type}")
            print(msg)
            print(f"\n과제 현재 상태: {task.status.value} (재시도: {task.worker_retry_count}/1, 재할당: {task.reassign_count}/2)")
            return 0
        except Exception as exc:
            print(f"❌ 오류: {exc}")
            return 1

    if action == "list" or not action:
        tasks = store.list_tasks()
        print_banner("Apart & Together — Host Bot Tracked Tasks")
        if not tasks:
            print("현재 추적 중인 과제가 없습니다.")
            return 0

        print(f"{'Task ID':<18} | {'Status':<18} | {'Worker':<12} | {'Retries':<8} | {'Reassign':<8} | {'Title'}")
        print("-" * 88)
        for t in tasks:
            worker = t.current_worker or "-"
            print(f"{t.task_id:<18} | {t.status.value:<18} | {worker:<12} | {t.worker_retry_count:<8} | {t.reassign_count:<8} | {t.title}")
        print("-" * 88)
        print(f"Total tracked tasks: {len(tasks)}\n")
        return 0

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apart & Together — Multi-AI Hub CLI: Bundle and query multiple AIs.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: status
    subparsers.add_parser("status", help="Show active AI providers and API key status")

    # Command: ask
    ask_parser = subparsers.add_parser("ask", help="Query multiple AIs in parallel and compare responses")
    ask_parser.add_argument("prompt", type=str, help="Prompt to send to models")
    ask_parser.add_argument("--models", type=str, help="Comma-separated model names (e.g. openai,gemini,claude)")
    ask_parser.add_argument("--system", type=str, help="Optional system instruction")

    # Command: synth
    synth_parser = subparsers.add_parser("synth", help="Query multiple AIs and synthesize a single consensus answer")
    synth_parser.add_argument("prompt", type=str, help="Prompt to send to models")
    synth_parser.add_argument("--judge", type=str, help="Provider to perform synthesis (default: first active)")
    synth_parser.add_argument("--system", type=str, help="Optional system instruction")

    # Command: code
    code_parser = subparsers.add_parser("code", help="Generate code with multiple AIs and verify with AST security auditor")
    code_parser.add_argument("task", type=str, help="Coding task specification")
    code_parser.add_argument("--models", type=str, help="Comma-separated model names")

    # Command: mailbox
    mb_parser = subparsers.add_parser("mailbox", help="Manage shared local mailbox for subscription AIs")
    mb_sub = mb_parser.add_subparsers(dest="mailbox_action", help="Mailbox actions")
    mb_sub.add_parser("list", help="List all mailbox tasks")
    view_p = mb_sub.add_parser("view", help="View task details and reviews")
    view_p.add_argument("task_id", type=str, help="Task ID to inspect")
    post_p = mb_sub.add_parser("post", help="Post a new task to the mailbox")
    post_p.add_argument("title", type=str, help="Task title")
    post_p.add_argument("content", type=str, help="Task content or code")
    post_p.add_argument("--type", type=str, default="code_review", help="Task type (default: code_review)")
    post_p.add_argument("--author", type=str, default="cli_user", help="Author name")
    mb_sub.add_parser("clear", help="Clear all tasks from the mailbox")

    # Command: bot (Phase 2 Host AI Bot)
    bot_parser = subparsers.add_parser("bot", help="Phase 2 Host AI Bot: Draft generator & lifecycle state machine")
    bot_sub = bot_parser.add_subparsers(dest="bot_action", help="Host bot actions")
    draft_p = bot_sub.add_parser("draft", help="Generate 3-part acceptance criteria draft from free-form goal")
    draft_p.add_argument("goal", type=str, help="Free-form coding goal")
    draft_p.add_argument("--description", type=str, default="", help="Optional detailed requirements or context")
    bot_sub.add_parser("list", help="List all tracked tasks with lifecycle status")
    create_p = bot_sub.add_parser("create", help="Create new task and generate draft criteria")
    create_p.add_argument("task_id", type=str, help="Task ID (e.g. task-01)")
    create_p.add_argument("title", type=str, help="Task title")
    create_p.add_argument("goal", type=str, help="Free-form goal")
    create_p.add_argument("--creator", type=str, default="host", help="Task creator")
    approve_p = bot_sub.add_parser("approve", help="Approve draft criteria (fail-closed gate)")
    approve_p.add_argument("task_id", type=str, help="Task ID to approve")
    approve_p.add_argument("--approver", type=str, default="host", help="Approver identity")
    assign_p = bot_sub.add_parser("assign", help="Assign worker and compute branch name")
    assign_p.add_argument("task_id", type=str, help="Task ID")
    assign_p.add_argument("worker", type=str, help="Worker username")
    pass_p = bot_sub.add_parser("pass", help="Record verification pass")
    pass_p.add_argument("task_id", type=str, help="Task ID")
    fail_p = bot_sub.add_parser("fail", help="Record verification fail (triggers retry/reassignment)")
    fail_p.add_argument("task_id", type=str, help="Task ID")
    fail_p.add_argument("--reason", type=str, default="Test failed", help="Failure reason")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    hub = MultiAIHub()

    if args.command == "status":
        return cmd_status(hub)

    if args.command == "ask":
        models = [m.strip().lower() for m in args.models.split(",")] if args.models else None
        return cmd_ask(hub, args.prompt, models, args.system)

    if args.command == "synth":
        return cmd_synth(hub, args.prompt, args.judge, args.system)

    if args.command == "code":
        models = [m.strip().lower() for m in args.models.split(",")] if args.models else None
        return cmd_code(hub, args.task, models)

    if args.command == "mailbox":
        return cmd_mailbox(args)

    if args.command == "bot":
        return cmd_bot(args, hub)

    return 0


if __name__ == "__main__":
    sys.exit(main())
