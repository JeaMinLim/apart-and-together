"""Base provider interfaces and response dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    provider: str
    model: str
    content: str
    latency_seconds: float
    success: bool
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None

    def summary(self) -> str:
        if self.success:
            return f"[{self.provider} ({self.model}) - {self.latency_seconds:.2f}s]"
        return f"[{self.provider} ({self.model}) - FAILED: {self.error_message}]"


class BaseProvider(ABC):
    """Abstract base class for all AI providers."""

    def __init__(self, name: str, api_key: Optional[str], base_url: Optional[str], default_model: str) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.default_model = default_model

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """Send a completion request to the provider."""
        raise NotImplementedError
