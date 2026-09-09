#!/usr/bin/env python3
"""Model Context Protocol (MCP) server for Apart & Together.

Allows subscription-based AIs (Claude Desktop, Cursor, etc.) to communicate
with the Multi-AI Hub and Phase 1 AST security auditor via standard stdio JSON-RPC.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.multi_ai.config import load_ai_config
from src.multi_ai.hub import MultiAIHub
from src.verify.ast_scanner import scan_source

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "apart-and-together-mcp"
SERVER_VERSION = "0.3.0"

_TOOLS = [
    {
        "name": "get_multi_ai_status",
        "description": "Check the status of configured AI providers in Apart & Together (ChatGPT, Claude, Gemini, Grok, OpenRouter, Ollama).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ask_other_ais",
        "description": "Query other AI models (e.g. Gemini, ChatGPT, Grok, OpenRouter) concurrently and return their answers for cross-checking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The question or instruction to send to other AI models.",
                },
                "models": {
                    "type": "string",
                    "description": "Optional comma-separated list of providers to query (e.g. 'gemini,openai'). Defaults to all active providers.",
                },
                "system": {
                    "type": "string",
                    "description": "Optional system instruction.",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "synthesize_with_other_ais",
        "description": "Query all active AI models and synthesize their responses into a single cohesive, high-quality answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to ask all models.",
                },
                "judge": {
                    "type": "string",
                    "description": "Optional provider name to perform final synthesis (e.g. 'gemini').",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "audit_code_security",
        "description": "Run Phase 1 AST security auditor on Python code to verify safety before merging (detects eval, exec, os.system, subprocess, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to audit for dangerous calls.",
                },
            },
            "required": ["code"],
        },
    },
]


def log_debug(msg: str) -> None:
    sys.stderr.write(f"[{SERVER_NAME}] {msg}\n")
    sys.stderr.flush()


class MCPServer:
    def __init__(self) -> None:
        self.hub = MultiAIHub()

    def handle_tool_get_status(self) -> str:
        configs = load_ai_config()
        lines = ["=== Apart & Together — Multi-AI Hub Status ==="]
        active_count = 0
        for name, cfg in configs.items():
            status = "ACTIVE ✅" if cfg.is_active else "DISABLED ⚪"
            if cfg.is_active:
                active_count += 1
            lines.append(f"- {cfg.display_name} ({name}): {status} [model: {cfg.default_model}]")
        lines.append(f"\nTotal active providers: {active_count} / {len(configs)}")
        if active_count == 0:
            lines.append("Tip: Configure your API keys in the repository .env file.")
        return "\n".join(lines)

    def handle_tool_ask(self, args: Dict[str, Any]) -> str:
        prompt = args.get("prompt", "")
        models_raw = args.get("models")
        system = args.get("system")

        if not self.hub.active_names:
            return "❌ No active AI providers configured in .env. Please set API keys (e.g. GEMINI_API_KEY)."

        targets = (
            [m.strip().lower() for m in models_raw.split(",")]
            if models_raw
            else self.hub.active_names
        )

        responses = self.hub.query_many(targets, prompt, system_prompt=system)
        output_lines = [f"=== Queried {len(targets)} AI Models in Parallel ==="]
        for name, r in responses.items():
            header = f"\n--- [{name.upper()} ({r.model})] ({r.latency_seconds:.2f}s) ---"
            output_lines.append(header)
            if r.success:
                output_lines.append(r.content)
            else:
                output_lines.append(f"Error: {r.error_message}")
        return "\n".join(output_lines)

    def handle_tool_synth(self, args: Dict[str, Any]) -> str:
        prompt = args.get("prompt", "")
        judge = args.get("judge")

        if not self.hub.active_names:
            return "❌ No active AI providers configured in .env."

        res = self.hub.synthesize(prompt, judge_provider=judge)
        if res.success:
            return f"=== Synthesized Consensus ({res.provider} - {res.latency_seconds:.2f}s) ===\n\n{res.content}"
        return f"❌ Synthesis failed: {res.error_message}"

    def handle_tool_audit(self, args: Dict[str, Any]) -> str:
        code = args.get("code", "")
        findings = scan_source(code, file_path="<submitted_code.py>")

        if not findings:
            return "🛡️ AST Security Audit: PASSED ✅\nNo dangerous functions, shell executions, or unauthorized imports found."

        lines = [
            f"🛡️ AST Security Audit: FAILED ❌ ({len(findings)} security violation(s) detected!)",
            "",
        ]
        for f in findings:
            lines.append(f"  • [{f.severity.value}] {f.rule_id} at line {f.line}:{f.col}")
            lines.append(f"    Target:  {f.target}")
            lines.append(f"    Message: {f.message}")
            lines.append("")
        lines.append("Action required: Remove or refactor the dangerous calls to meet safety verification criteria.")
        return "\n".join(lines)

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "get_multi_ai_status":
                text = self.handle_tool_get_status()
            elif name == "ask_other_ais":
                text = self.handle_tool_ask(args)
            elif name == "synthesize_with_other_ais":
                text = self.handle_tool_synth(args)
            elif name == "audit_code_security":
                text = self.handle_tool_audit(args)
            else:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: '{name}'"}],
                    "isError": True,
                }
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Tool execution exception: {exc}"}],
                "isError": True,
            }

    def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        # Handle notifications (no response needed)
        if method == "notifications/initialized":
            log_debug("Client initialized.")
            return None

        # Handle ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        # Handle initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            }

        # Handle tools/list
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": _TOOLS,
                },
            }

        # Handle tools/call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = self.execute_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            }

        # Unsupported method
        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        return None

    def run_stdio(self) -> None:
        log_debug(f"Starting {SERVER_NAME} v{SERVER_VERSION} stdio transport...")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as err:
                log_debug(f"JSON decode error: {err}")
                continue

            resp = self.process_message(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def main() -> None:
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
