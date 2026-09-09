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

    return 0


if __name__ == "__main__":
    sys.exit(main())
