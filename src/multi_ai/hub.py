"""MultiAIHub: Concurrent orchestrator for multiple AI providers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from src.multi_ai.config import ProviderConfig, load_ai_config
from src.multi_ai.providers.anthropic import AnthropicProvider
from src.multi_ai.providers.base import BaseProvider, LLMResponse
from src.multi_ai.providers.gemini import GeminiProvider
from src.multi_ai.providers.openai_compat import OpenAICompatProvider


def build_provider(cfg: ProviderConfig) -> BaseProvider:
    """Instantiate the appropriate BaseProvider for a configuration."""
    if cfg.name == "anthropic":
        return AnthropicProvider(
            name=cfg.name,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            default_model=cfg.default_model,
        )
    if cfg.name == "gemini":
        return GeminiProvider(
            name=cfg.name,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            default_model=cfg.default_model,
        )
    # Default to OpenAI-compatible (openai, grok, openrouter, ollama)
    return OpenAICompatProvider(
        name=cfg.name,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        default_model=cfg.default_model,
    )


class MultiAIHub:
    """Manages concurrent execution and synthesis across registered AI providers."""

    def __init__(self, env_path: Optional[Path] = None) -> None:
        self.configs = load_ai_config(env_path)
        self.providers: Dict[str, BaseProvider] = {
            name: build_provider(cfg)
            for name, cfg in self.configs.items()
            if cfg.is_active
        }

    @property
    def active_names(self) -> List[str]:
        return list(self.providers.keys())

    def get_provider(self, name: str) -> Optional[BaseProvider]:
        return self.providers.get(name.lower())

    def query_single(
        self,
        provider_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        provider = self.get_provider(provider_name)
        if not provider:
            return LLMResponse(
                provider=provider_name,
                model=model or "unknown",
                content="",
                latency_seconds=0.0,
                success=False,
                error_message=f"Provider '{provider_name}' is not configured or missing API key.",
            )
        return provider.complete(prompt, system_prompt=system_prompt, model=model, timeout=timeout)

    def query_many(
        self,
        provider_names: List[str],
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Dict[str, LLMResponse]:
        """Query specified providers concurrently and return results dictionary."""
        results: Dict[str, LLMResponse] = {}
        valid_targets = [name for name in provider_names if name in self.providers]

        if not valid_targets:
            return results

        with ThreadPoolExecutor(max_workers=len(valid_targets)) as executor:
            future_to_name = {
                executor.submit(
                    self.providers[name].complete,
                    prompt,
                    system_prompt,
                    None,
                    timeout,
                ): name
                for name in valid_targets
            }

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    results[name] = LLMResponse(
                        provider=name,
                        model=self.providers[name].default_model,
                        content="",
                        latency_seconds=0.0,
                        success=False,
                        error_message=str(exc),
                    )
        return results

    def query_all(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Dict[str, LLMResponse]:
        """Query all active providers in parallel."""
        return self.query_many(self.active_names, prompt, system_prompt=system_prompt, timeout=timeout)

    def synthesize(
        self,
        prompt: str,
        judge_provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Query all active models, then have the judge provider synthesize the best answer."""
        responses = self.query_all(prompt, system_prompt=system_prompt)
        successful = {k: v for k, v in responses.items() if v.success and v.content}

        if not successful:
            return LLMResponse(
                provider="hub",
                model="synthesis",
                content="",
                latency_seconds=0.0,
                success=False,
                error_message="All providers failed or no active providers available.",
            )

        # If only one provider succeeded, return it directly
        if len(successful) == 1:
            return next(iter(successful.values()))

        # Determine judge provider
        judge_name = judge_provider or next(iter(successful.keys()))
        judge = self.get_provider(judge_name) or next(iter(self.providers.values()))

        synthesis_prompt = (
            f"Original user prompt:\n{prompt}\n\n"
            f"Here are responses from different AI models:\n\n"
        )
        for name, r in successful.items():
            synthesis_prompt += f"--- [{name.upper()} ({r.model})] ---\n{r.content}\n\n"

        synthesis_prompt += (
            "Review the above answers, identify agreements and complementary insights, "
            "correct any discrepancies, and provide a single superior, well-structured final answer."
        )

        return judge.complete(
            prompt=synthesis_prompt,
            system_prompt="You are an expert synthesizer combining insights from multiple AI models into a unified response.",
        )
