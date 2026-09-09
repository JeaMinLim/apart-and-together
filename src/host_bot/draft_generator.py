"""Acceptance criteria draft generator for free-form task descriptions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from src.multi_ai.hub import MultiAIHub


@dataclass
class AcceptanceCriteria:
    interface_spec: str
    test_cases: str
    notes: str

    def to_markdown(self) -> str:
        return (
            "### 📐 인터페이스 스펙\n"
            "```python\n"
            f"{self.interface_spec.strip()}\n"
            "```\n\n"
            "### 🧪 테스트 케이스\n"
            f"{self.test_cases.strip()}\n\n"
            "### 📝 비고 (보안 및 제약 사항)\n"
            f"{self.notes.strip()}\n"
        )


_SYSTEM_PROMPT = """You are a software architect defining machine-verifiable acceptance criteria for coding tasks.
Given a free-form coding goal, respond ONLY with a valid JSON object matching this exact schema:
{
  "interface_spec": "Python function or class signature with type annotations",
  "test_cases": "Numbered test cases covering normal, empty, and edge cases",
  "notes": "Security constraints, algorithmic complexity, or exception handling rules"
}
Do not wrap in markdown tags other than standard json. Output only the JSON."""


def _fallback_heuristic_criteria(raw_description: str) -> AcceptanceCriteria:
    """Generate a clean initial template when no external AI provider is configured."""
    words = re.findall(r"\w+", raw_description.lower())
    func_name = "_".join(words[:3]) if words else "process_task"
    func_name = re.sub(r"[^a-zA-Z0-9_]", "", func_name) or "process_task"

    return AcceptanceCriteria(
        interface_spec=f"def {func_name}(input_data: str) -> dict:\n    \"\"\"Process input according to specification.\"\"\"\n    pass",
        test_cases=(
            "1. 정상 입력값 처리: 유효한 데이터가 주어졌을 때 올바른 결과 반환\n"
            "2. 빈 입력값 처리: 빈 문자열이나 빈 컬렉션 입력 시 적절한 빈 결과 반환\n"
            "3. 엣지 케이스: 잘못된 형식의 입력 시 ValueError 발생"
        ),
        notes=(
            f"- 원본 요청: '{raw_description}'\n"
            "- AST 보안 감사 통과 필수 (eval, subprocess, os.system 사용 금지)\n"
            "- 타입 힌트 준수 및 예외 처리 철저"
        ),
    )


def generate_acceptance_criteria(
    raw_description: str,
    hub: Optional[MultiAIHub] = None,
    preferred_model: Optional[str] = None,
) -> AcceptanceCriteria:
    """Generate structured 3-part acceptance criteria from a free-form description."""
    if hub is None:
        hub = MultiAIHub()

    if not hub.active_names:
        return _fallback_heuristic_criteria(raw_description)

    target_provider = preferred_model or hub.active_names[0]
    prompt = f"Goal description:\n{raw_description}\n\nGenerate structured acceptance criteria JSON."

    resp = hub.query_single(target_provider, prompt, system_prompt=_SYSTEM_PROMPT)
    if not resp.success or not resp.content:
        return _fallback_heuristic_criteria(raw_description)

    content = resp.content.strip()
    # Strip optional markdown json fences
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        content = match.group(1).strip()

    try:
        data = json.loads(content)
        return AcceptanceCriteria(
            interface_spec=data.get("interface_spec", "def solve(): pass"),
            test_cases=data.get("test_cases", "1. 기본 테스트 통과"),
            notes=data.get("notes", "보안 제약 사항 준수"),
        )
    except Exception:
        return _fallback_heuristic_criteria(raw_description)
