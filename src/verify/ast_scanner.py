#!/usr/bin/env python3
"""AST-based static security auditor for submitted task code.

Inspects Python source code for dangerous builtins, arbitrary shell/process
execution, and unsafe system operations before host merge.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Finding:
    file_path: str
    line: int
    col: int
    severity: Severity
    rule_id: str
    message: str
    target: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


_DANGEROUS_BUILTINS: Dict[str, Tuple[Severity, str, str]] = {
    "eval": (Severity.CRITICAL, "SEC-EVAL-CALL", "Direct call to eval() can lead to arbitrary code execution."),
    "exec": (Severity.CRITICAL, "SEC-EXEC-CALL", "Direct call to exec() can lead to arbitrary code execution."),
    "compile": (Severity.HIGH, "SEC-COMPILE-CALL", "Dynamic code compilation via compile() is prohibited."),
    "__import__": (Severity.HIGH, "SEC-DYNAMIC-IMPORT", "Direct invocation of __import__() bypasses static review."),
}

_DANGEROUS_MODULE_ATTRS: Dict[str, Dict[str, Tuple[Severity, str, str]]] = {
    "os": {
        "system": (Severity.CRITICAL, "SEC-SHELL-EXEC", "Execution of arbitrary shell command via os.system()."),
        "popen": (Severity.CRITICAL, "SEC-SHELL-EXEC", "Execution of arbitrary command pipeline via os.popen()."),
        "spawnl": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnl()."),
        "spawnle": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnle()."),
        "spawnlp": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnlp()."),
        "spawnlpe": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnlpe()."),
        "spawnv": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnv()."),
        "spawnve": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnve()."),
        "spawnvp": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnvp()."),
        "spawnvpe": (Severity.CRITICAL, "SEC-PROCESS-SPAWN", "Spawning external process via os.spawnvpe()."),
        "execl": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execl()."),
        "execle": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execle()."),
        "execlp": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execlp()."),
        "execlpe": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execlpe()."),
        "execv": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execv()."),
        "execve": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execve()."),
        "execvp": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execvp()."),
        "execvpe": (Severity.CRITICAL, "SEC-PROCESS-EXEC", "Process replacement via os.execvpe()."),
    },
    "subprocess": {
        "Popen": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Spawning child process via subprocess.Popen()."),
        "call": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing process via subprocess.call()."),
        "check_call": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing process via subprocess.check_call()."),
        "check_output": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing process via subprocess.check_output()."),
        "run": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing process via subprocess.run()."),
        "getoutput": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing shell command via subprocess.getoutput()."),
        "getstatusoutput": (Severity.CRITICAL, "SEC-SUBPROCESS-CALL", "Executing shell command via subprocess.getstatusoutput()."),
    },
    "pty": {
        "spawn": (Severity.CRITICAL, "SEC-PTY-SPAWN", "Spawning pseudo-terminal shell via pty.spawn()."),
    },
    "shutil": {
        "rmtree": (Severity.HIGH, "SEC-DESTRUCTIVE-FS", "Destructive recursive directory removal via shutil.rmtree()."),
    },
    "socket": {
        "socket": (Severity.HIGH, "SEC-NETWORK-SOCKET", "Arbitrary network socket instantiation via socket.socket()."),
    },
    "importlib": {
        "import_module": (Severity.HIGH, "SEC-DYNAMIC-IMPORT", "Dynamic module loading via importlib.import_module()."),
    },
}


class CodeSecurityVisitor(ast.NodeVisitor):
    """AST visitor tracking imports and detecting dangerous calls."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.findings: List[Finding] = []
        # Maps local name -> (original_module, original_attr)
        # e.g., 'system' -> ('os', 'system')
        self.imported_funcs: Dict[str, Tuple[str, str]] = {}
        # Maps local module alias -> original_module
        # e.g., 'sp' -> 'subprocess'
        self.imported_modules: Dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            asname = alias.asname or name
            if name in _DANGEROUS_MODULE_ATTRS:
                self.imported_modules[asname] = name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module in _DANGEROUS_MODULE_ATTRS:
            danger_map = _DANGEROUS_MODULE_ATTRS[module]
            for alias in node.names:
                orig_name = alias.name
                local_name = alias.asname or orig_name
                if orig_name in danger_map:
                    self.imported_funcs[local_name] = (module, orig_name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # 1. Direct function call: name(...)
        if isinstance(func, ast.Name):
            func_name = func.id
            if func_name in _DANGEROUS_BUILTINS:
                sev, rule, msg = _DANGEROUS_BUILTINS[func_name]
                self.findings.append(Finding(
                    file_path=self.file_path,
                    line=node.lineno,
                    col=node.col_offset,
                    severity=sev,
                    rule_id=rule,
                    message=msg,
                    target=f"{func_name}()",
                ))
            elif func_name in self.imported_funcs:
                module, orig_name = self.imported_funcs[func_name]
                sev, rule, msg = _DANGEROUS_MODULE_ATTRS[module][orig_name]
                self.findings.append(Finding(
                    file_path=self.file_path,
                    line=node.lineno,
                    col=node.col_offset,
                    severity=sev,
                    rule_id=rule,
                    message=msg,
                    target=f"{func_name}() [{module}.{orig_name}]",
                ))

        # 2. Attribute call: obj.attr(...)
        elif isinstance(func, ast.Attribute):
            attr_name = func.attr
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id
                actual_module = self.imported_modules.get(obj_name, obj_name)
                if actual_module in _DANGEROUS_MODULE_ATTRS:
                    danger_map = _DANGEROUS_MODULE_ATTRS[actual_module]
                    if attr_name in danger_map:
                        sev, rule, msg = danger_map[attr_name]
                        self.findings.append(Finding(
                            file_path=self.file_path,
                            line=node.lineno,
                            col=node.col_offset,
                            severity=sev,
                            rule_id=rule,
                            message=msg,
                            target=f"{obj_name}.{attr_name}()",
                        ))

        self.generic_visit(node)


def scan_source(source_code: str, file_path: str = "<stdin>") -> List[Finding]:
    """Parse Python source code and return security audit findings."""
    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as err:
        return [Finding(
            file_path=file_path,
            line=err.lineno or 1,
            col=err.offset or 0,
            severity=Severity.CRITICAL,
            rule_id="SEC-SYNTAX-ERROR",
            message=f"Syntax error prevents AST security audit: {err.msg}",
            target="SyntaxError",
        )]
    visitor = CodeSecurityVisitor(file_path=file_path)
    visitor.visit(tree)
    return visitor.findings


def scan_file(file_path: Path) -> List[Finding]:
    """Read and scan a single Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [Finding(
            file_path=str(file_path),
            line=1,
            col=0,
            severity=Severity.HIGH,
            rule_id="SEC-READ-ERROR",
            message=f"Failed to read file for auditing: {exc}",
            target="IOError",
        )]
    return scan_source(content, str(file_path))


def collect_python_files(
    paths: List[str],
    recursive: bool = True,
    excludes: Optional[List[str]] = None,
) -> Set[Path]:
    """Resolve file/directory paths to Python files, ignoring hidden/venv and excluded directories."""
    collected: Set[Path] = set()
    ignored_patterns = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".tox", "build", "dist"}
    if excludes:
        ignored_patterns.update(excludes)

    for p_str in paths:
        p = Path(p_str)
        if p.is_file() and p.suffix == ".py":
            if not any(part in ignored_patterns for part in p.parts):
                collected.add(p.resolve())
        elif p.is_dir():
            iterator = p.rglob("*.py") if recursive else p.glob("*.py")
            for sub_p in iterator:
                if any(part in ignored_patterns for part in sub_p.parts):
                    continue
                collected.add(sub_p.resolve())
    return collected


def format_text_report(findings: List[Finding], scanned_count: int) -> str:
    """Format findings as a human-readable string."""
    passed = len(findings) == 0
    status_str = "PASSED ✅" if passed else "FAILED ❌"
    lines = [
        "==================================================",
        f"  Apart & Together — AST Security Auditor ({status_str})",
        "==================================================",
        f"Scanned files: {scanned_count}",
        f"Total violations: {len(findings)}",
    ]
    if findings:
        lines.append("\nViolations detected:")
        for f in findings:
            lines.append(f"  [{f.severity.value}] {f.file_path}:{f.line}:{f.col}")
            lines.append(f"    Rule:    {f.rule_id}")
            lines.append(f"    Target:  {f.target}")
            lines.append(f"    Message: {f.message}")
            lines.append("")
    return "\n".join(lines)


def format_github_report(findings: List[Finding]) -> str:
    """Format findings as GitHub Actions workflow commands."""
    lines = []
    for f in findings:
        cmd = "error" if f.severity in (Severity.CRITICAL, Severity.HIGH) else "warning"
        lines.append(f"::{cmd} file={f.file_path},line={f.line},col={f.col},title={f.rule_id}::{f.message} (target: {f.target})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static AST security auditor for apart-and-together collaborative code.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["."],
        help="Files or directories to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--fail-on",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default="HIGH",
        help="Minimum severity level that triggers non-zero exit code (default: HIGH)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Directory or file patterns to exclude from scanning (can be specified multiple times)",
    )

    args = parser.parse_args()

    py_files = collect_python_files(args.targets, excludes=args.exclude)
    if not py_files:
        if args.format == "json":
            print(json.dumps({"scanned_files": 0, "findings": [], "passed": True}))
        elif args.format == "text":
            print("No Python files found to scan.")
        return 0

    all_findings: List[Finding] = []
    for f_path in sorted(py_files):
        all_findings.extend(scan_file(f_path))

    # Determine pass/fail based on fail-on threshold
    severity_order = {
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    threshold = severity_order[Severity(args.fail_on)]
    blocking_findings = [f for f in all_findings if severity_order[f.severity] >= threshold]
    has_failed = len(blocking_findings) > 0

    if args.format == "json":
        output_data = {
            "scanned_files": len(py_files),
            "findings": [f.to_dict() for f in all_findings],
            "passed": not has_failed,
        }
        print(json.dumps(output_data, indent=2))
    elif args.format == "github":
        gh_lines = format_github_report(all_findings)
        if gh_lines:
            print(gh_lines)
        print(format_text_report(all_findings, len(py_files)))
    else:
        print(format_text_report(all_findings, len(py_files)))

    return 1 if has_failed else 0


if __name__ == "__main__":
    sys.exit(main())
