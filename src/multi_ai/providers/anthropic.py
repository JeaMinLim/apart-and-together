"""Anthropic Claude provider implementation."""

from __future__ import annotations

import time
from typing import Optional

import requests

from src.multi_ai.providers.base import BaseProvider, LLMResponse


class AnthropicProvider(BaseProvider):
    """Handles the Anthropic Messages API (/v1/messages)."""

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        target_model = model or self.default_model
        endpoint = f"{self.base_url}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": target_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.perf_counter()
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            latency = time.perf_counter() - start_time

            if resp.status_code != 200:
                return LLMResponse(
                    provider=self.name,
                    model=target_model,
                    content="",
                    latency_seconds=latency,
                    success=False,
                    error_message=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )

            data = resp.json()
            content_blocks = data.get("content", [])
            text_pieces = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            content = "".join(text_pieces).strip()

            usage = data.get("usage", {})
            total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            return LLMResponse(
                provider=self.name,
                model=target_model,
                content=content,
                latency_seconds=latency,
                success=True,
                tokens_used=total_tokens or None,
            )
        except Exception as exc:
            latency = time.perf_counter() - start_time
            return LLMResponse(
                provider=self.name,
                model=target_model,
                content="",
                latency_seconds=latency,
                success=False,
                error_message=str(exc),
            )
