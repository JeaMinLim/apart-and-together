"""Unit tests for Multi-AI Hub."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.multi_ai.config import load_ai_config, load_env_file
from src.multi_ai.hub import MultiAIHub
from src.multi_ai.providers.anthropic import AnthropicProvider
from src.multi_ai.providers.base import LLMResponse
from src.multi_ai.providers.gemini import GeminiProvider
from src.multi_ai.providers.openai_compat import OpenAICompatProvider


class TestMultiAIConfig(unittest.TestCase):
    def test_load_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("OPENAI_API_KEY=test-sk-key\nGEMINI_API_KEY=test-gemini\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                load_env_file(env_file)
                self.assertEqual(os.environ.get("OPENAI_API_KEY"), "test-sk-key")
                self.assertEqual(os.environ.get("GEMINI_API_KEY"), "test-gemini")

    def test_load_ai_config_detects_active(self) -> None:
        mock_env = {
            "OPENAI_API_KEY": "sk-mock",
            "GEMINI_API_KEY": "gm-mock",
        }
        with patch.dict(os.environ, mock_env, clear=True):
            configs = load_ai_config(Path("/nonexistent/.env"))
            self.assertTrue(configs["openai"].is_active)
            self.assertTrue(configs["gemini"].is_active)
            self.assertFalse(configs["anthropic"].is_active)
            self.assertFalse(configs["grok"].is_active)


class TestProviders(unittest.TestCase):
    @patch("src.multi_ai.providers.openai_compat.http_post_json")
    def test_openai_compat_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            200,
            {
                "choices": [{"message": {"content": "Hello from OpenAI!"}}],
                "usage": {"total_tokens": 42},
            },
            "{}",
        )

        provider = OpenAICompatProvider(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o",
        )
        res = provider.complete("Hi")

        self.assertTrue(res.success)
        self.assertEqual(res.content, "Hello from OpenAI!")
        self.assertEqual(res.tokens_used, 42)
        self.assertEqual(res.model, "gpt-4o")

    @patch("src.multi_ai.providers.anthropic.http_post_json")
    def test_anthropic_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            200,
            {
                "content": [{"type": "text", "text": "Hello from Claude!"}],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            "{}",
        )

        provider = AnthropicProvider(
            name="anthropic",
            api_key="ant-test",
            base_url="https://api.anthropic.com/v1",
            default_model="claude-3-5-sonnet",
        )
        res = provider.complete("Hi")

        self.assertTrue(res.success)
        self.assertEqual(res.content, "Hello from Claude!")
        self.assertEqual(res.tokens_used, 30)

    @patch("src.multi_ai.providers.gemini.http_post_json")
    def test_gemini_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Hello from Gemini!"}]}}
                ],
                "usageMetadata": {"totalTokenCount": 25},
            },
            "{}",
        )

        provider = GeminiProvider(
            name="gemini",
            api_key="gem-test",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-1.5-pro",
        )
        res = provider.complete("Hi")

        self.assertTrue(res.success)
        self.assertEqual(res.content, "Hello from Gemini!")
        self.assertEqual(res.tokens_used, 25)


class TestMultiAIHub(unittest.TestCase):
    def test_hub_concurrent_query(self) -> None:
        mock_env = {
            "OPENAI_API_KEY": "sk-mock",
            "GEMINI_API_KEY": "gm-mock",
        }
        with patch.dict(os.environ, mock_env, clear=True):
            hub = MultiAIHub(Path("/nonexistent/.env"))
            self.assertEqual(set(hub.active_names), {"openai", "gemini"})

            # Mock providers' complete method
            hub.providers["openai"].complete = MagicMock(return_value=LLMResponse(
                provider="openai",
                model="gpt-4o",
                content="OpenAI solution",
                latency_seconds=0.1,
                success=True,
            ))
            hub.providers["gemini"].complete = MagicMock(return_value=LLMResponse(
                provider="gemini",
                model="gemini-1.5-pro",
                content="Gemini solution",
                latency_seconds=0.15,
                success=True,
            ))

            responses = hub.query_all("Solve problem")
            self.assertEqual(len(responses), 2)
            self.assertEqual(responses["openai"].content, "OpenAI solution")
            self.assertEqual(responses["gemini"].content, "Gemini solution")

    def test_hub_synthesize(self) -> None:
        mock_env = {
            "OPENAI_API_KEY": "sk-mock",
            "GEMINI_API_KEY": "gm-mock",
        }
        with patch.dict(os.environ, mock_env, clear=True):
            hub = MultiAIHub(Path("/nonexistent/.env"))

            hub.providers["openai"].complete = MagicMock(return_value=LLMResponse(
                provider="openai",
                model="gpt-4o",
                content="Answer A",
                latency_seconds=0.1,
                success=True,
            ))
            hub.providers["gemini"].complete = MagicMock(return_value=LLMResponse(
                provider="gemini",
                model="gemini-1.5-pro",
                content="Synthesized final answer",
                latency_seconds=0.2,
                success=True,
            ))

            result = hub.synthesize("Compare solutions", judge_provider="gemini")
            self.assertTrue(result.success)
            self.assertEqual(result.content, "Synthesized final answer")


if __name__ == "__main__":
    unittest.main()
