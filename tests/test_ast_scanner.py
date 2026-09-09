"""Unit tests for AST security auditor."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.verify.ast_scanner import Severity, main, scan_source


class TestASTScanner(unittest.TestCase):
    def test_safe_code_passes(self) -> None:
        code = """
def calculate_sum(a: int, b: int) -> int:
    return a + b

import json
data = json.loads('{"key": "value"}')
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 0)

    def test_detect_eval_and_exec(self) -> None:
        code = """
def unsafe_eval(user_input):
    return eval(user_input)

def unsafe_exec(script):
    exec(script)
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 2)
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC-EVAL-CALL", rule_ids)
        self.assertIn("SEC-EXEC-CALL", rule_ids)
        self.assertTrue(all(f.severity == Severity.CRITICAL for f in findings))

    def test_detect_os_system_direct_and_alias(self) -> None:
        code = """
import os
os.system("rm -rf /")

import os as operating_system
operating_system.popen("cat /etc/passwd")

from os import system as sys_call
sys_call("whoami")
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(f.rule_id == "SEC-SHELL-EXEC" for f in findings))
        self.assertTrue(all(f.severity == Severity.CRITICAL for f in findings))

    def test_detect_subprocess_calls(self) -> None:
        code = """
import subprocess
subprocess.run(["ls", "-la"])
subprocess.Popen(["bash"])

from subprocess import check_output
check_output(["id"])
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(f.rule_id == "SEC-SUBPROCESS-CALL" for f in findings))

    def test_detect_destructive_fs_and_socket(self) -> None:
        code = """
import shutil
shutil.rmtree("/tmp/target")

import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 2)
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC-DESTRUCTIVE-FS", rule_ids)
        self.assertIn("SEC-NETWORK-SOCKET", rule_ids)

    def test_detect_dynamic_import_and_compile(self) -> None:
        code = """
import importlib
mod = importlib.import_module("os")
__import__("sys")
c = compile("1 + 1", "<string>", "eval")
"""
        findings = scan_source(code)
        self.assertEqual(len(findings), 3)
        rule_ids = {f.rule_id for f in findings}
        self.assertIn("SEC-DYNAMIC-IMPORT", rule_ids)
        self.assertIn("SEC-COMPILE-CALL", rule_ids)

    def test_syntax_error_reported_as_finding(self) -> None:
        invalid_code = "def broken_syntax(:\n    pass"
        findings = scan_source(invalid_code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "SEC-SYNTAX-ERROR")
        self.assertEqual(findings[0].severity, Severity.CRITICAL)

    def test_cli_execution_clean_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            clean_file = Path(tmp_dir) / "clean.py"
            clean_file.write_text("x = 1 + 2\n", encoding="utf-8")

            with patch("sys.argv", ["ast_scanner.py", str(clean_file), "--format", "json"]):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    exit_code = main()
                    self.assertEqual(exit_code, 0)
                    data = json.loads(mock_stdout.getvalue())
                    self.assertTrue(data["passed"])
                    self.assertEqual(len(data["findings"]), 0)

    def test_cli_execution_dangerous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            danger_file = Path(tmp_dir) / "danger.py"
            danger_file.write_text("import os\nos.system('echo pwned')\n", encoding="utf-8")

            with patch("sys.argv", ["ast_scanner.py", str(danger_file), "--format", "json"]):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    exit_code = main()
                    self.assertEqual(exit_code, 1)
                    data = json.loads(mock_stdout.getvalue())
                    self.assertFalse(data["passed"])
                    self.assertEqual(len(data["findings"]), 1)
                    self.assertEqual(data["findings"][0]["rule_id"], "SEC-SHELL-EXEC")

    def test_cli_execution_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sub_dir = tmp_path / "ignored"
            sub_dir.mkdir()
            bad_file = sub_dir / "bad.py"
            bad_file.write_text("import os\nos.system('ls')\n", encoding="utf-8")

            with patch("sys.argv", ["ast_scanner.py", str(tmp_path), "--exclude", "ignored", "--format", "json"]):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    exit_code = main()
                    self.assertEqual(exit_code, 0)
                    data = json.loads(mock_stdout.getvalue())
                    self.assertTrue(data["passed"])
                    self.assertEqual(len(data["findings"]), 0)


if __name__ == "__main__":
    unittest.main()
