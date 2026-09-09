"""Base provider interfaces and response dataclasses."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


def http_post_json(
    url: str,
    json_payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: float = 60.0,
) -> Tuple[int, Optional[Dict[str, Any]], str]:
    """Execute an HTTP POST request sending and receiving JSON via standard library urllib."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    data = json.dumps(json_payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            body_text = resp.read().decode("utf-8")
            try:
                parsed_json = json.loads(body_text)
            except Exception:
                parsed_json = None
            return status_code, parsed_json, body_text
    except urllib.error.HTTPError as err:
        body_text = err.read().decode("utf-8", errors="replace")
        try:
            parsed_json = json.loads(body_text)
        except Exception:
            parsed_json = None
        return err.code, parsed_json, body_text


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
