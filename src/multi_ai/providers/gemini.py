"""Google Gemini REST provider implementation."""

from __future__ import annotations

import time
from typing import Optional

import requests

from src.multi_ai.providers.base import BaseProvider, LLMResponse


class GeminiProvider(BaseProvider):
    """Handles Google Gemini REST generateContent API."""

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        target_model = model or self.default_model
        # Strip prefixes like 'models/' if already included
        clean_model = target_model.replace("models/", "")
        endpoint = f"{self.base_url}/models/{clean_model}:generateContent"

        params = {}
        if self.api_key:
            params["key"] = self.api_key

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }

        start_time = time.perf_counter()
        try:
            resp = requests.post(endpoint, params=params, json=payload, timeout=timeout)
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
            candidates = data.get("candidates", [])
            content = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                content = "".join(p.get("text", "") for p in parts).strip()

            usage = data.get("usageMetadata", {})
            tokens = usage.get("totalTokenCount")

            return LLMResponse(
                provider=self.name,
                model=target_model,
                content=content,
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
