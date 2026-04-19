"""Unified LLM client with Claude API and prompt caching."""

from __future__ import annotations

import os
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader

from src.utils.cache import FileCache
from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)

# Project root directory (where pyproject.toml lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Jinja2 template environment
_template_env: Environment | None = None


def get_template_env() -> Environment:
    global _template_env
    if _template_env is None:
        _template_env = Environment(
            loader=FileSystemLoader(PROJECT_ROOT / "templates" / "prompts"),
            keep_trailing_newline=True,
        )
    return _template_env


def render_template(name: str, **kwargs) -> str:
    """Render a Jinja2 prompt template."""
    env = get_template_env()
    template = env.get_template(name)
    return template.render(**kwargs)


class LLMClient:
    """Claude API client with prompt caching and cost tracking."""

    # Pricing per million tokens (Claude Sonnet 4)
    PRICING = {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
        "cache_write": 3.75 / 1_000_000,
        "cache_read": 0.30 / 1_000_000,
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        cache_dir: Path | None = None,
    ):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.file_cache = FileCache(cache_dir) if cache_dir else None

    @with_retry(
        max_attempts=3,
        min_wait=2.0,
        max_wait=30.0,
        retry_on=(anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError),
    )
    def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.8,
        use_cache: bool = True,
    ) -> tuple[str, float]:
        """Generate text using Claude API.

        Args:
            system: System prompt text.
            user: User prompt text.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            use_cache: Whether to use file cache and prompt caching.

        Returns:
            Tuple of (generated_text, cost_usd).
        """
        # Check file cache first
        if use_cache and self.file_cache:
            cached = self.file_cache.get(self.model, system, user)
            if cached is not None:
                log.info("llm_cache_hit", model=self.model)
                return cached, 0.0

        # Build messages with prompt caching on system prompt
        system_messages = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        log.info("llm_request", model=self.model, user_len=len(user))

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_messages,
            messages=[{"role": "user", "content": user}],
        )

        text = response.content[0].text
        cost = self._calculate_cost(response.usage)

        log.info(
            "llm_response",
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=round(cost, 4),
        )

        # Save to file cache
        if use_cache and self.file_cache:
            self.file_cache.set(self.model, system, user, value=text)

        return text, cost

    def _calculate_cost(self, usage) -> float:
        """Calculate cost from API usage stats."""
        cost = 0.0
        cost += getattr(usage, "input_tokens", 0) * self.PRICING["input"]
        cost += getattr(usage, "output_tokens", 0) * self.PRICING["output"]
        cost += getattr(usage, "cache_creation_input_tokens", 0) * self.PRICING["cache_write"]
        cost += getattr(usage, "cache_read_input_tokens", 0) * self.PRICING["cache_read"]
        return cost
