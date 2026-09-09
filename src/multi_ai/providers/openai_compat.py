"""OpenAI-compatible provider implementation (OpenAI, Grok, OpenRouter, Ollama)."""

from __future__ import annotations

import time
from typing import Optional

import requests

from src.multi_ai.providers.base import BaseProvider, LLMResponse


class OpenAICompatProvider(BaseProvider):
    """Handles any endpoint adhering to the OpenAI /chat/completions specification."""

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        target_model = model or self.default_model
        endpoint = f"{self.base_url}/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Extra headers for OpenRouter if needed
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://github.com/JeaMinLim/apart-and-together"
            headers["X-Title"] = "Apart & Together Multi-AI"

        payload = {
            "model": target_model,
            "messages": messages,
        }

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
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens")

            return LLMResponse(
                provider=self.name,
                model=target_model,
                content=content.strip(),
                latency_seconds=latency,
                success=True,
                tokens_used=tokens,
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
