"""Configuration and environment detection for Multi-AI providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ProviderConfig:
    name: str
    display_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: str = ""
    is_active: bool = False


def load_env_file(env_path: Optional[Path] = None) -> None:
    """Load key-value pairs from .env file into os.environ if not already set."""
    if env_path is None:
        env_path = Path(".env")
    if not env_path.is_file():
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ and val:
                    os.environ[key] = val
    except Exception:
        pass


def load_ai_config(env_path: Optional[Path] = None) -> Dict[str, ProviderConfig]:
    """Inspect environment variables and return configurations for all known providers."""
    load_env_file(env_path)

    configs: Dict[str, ProviderConfig] = {
        "openai": ProviderConfig(
            name="openai",
            display_name="ChatGPT (OpenAI)",
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            default_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        ),
        "anthropic": ProviderConfig(
            name="anthropic",
            display_name="Claude (Anthropic)",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            default_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        ),
        "gemini": ProviderConfig(
            name="gemini",
            display_name="Gemini (Google AI Studio)",
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
            default_model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
        ),
        "grok": ProviderConfig(
            name="grok",
            display_name="Grok (xAI)",
            api_key=os.getenv("XAI_API_KEY"),
            base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
            default_model=os.getenv("XAI_MODEL", "grok-2-latest"),
        ),
        "openrouter": ProviderConfig(
            name="openrouter",
            display_name="OpenRouter (All-in-One)",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
        ),
        "ollama": ProviderConfig(
            name="ollama",
            display_name="Local LLM (Ollama)",
            api_key="ollama",  # dummy key for local API
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            default_model=os.getenv("OLLAMA_MODEL", "llama3"),
        ),
    }

    # Evaluate active status
    for name, cfg in configs.items():
        if name == "ollama":
            # Ollama is considered active if OLLAMA_BASE_URL is explicitly set or server responds
            cfg.is_active = bool(os.getenv("OLLAMA_BASE_URL"))
        else:
            cfg.is_active = bool(cfg.api_key and cfg.api_key.strip())

    return configs


def get_active_providers(env_path: Optional[Path] = None) -> List[ProviderConfig]:
    """Return only providers that have valid keys configured."""
    all_configs = load_ai_config(env_path)
    return [cfg for cfg in all_configs.values() if cfg.is_active]
