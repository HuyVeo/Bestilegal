"""
Multi-LLM Backend Factory.

Supports multiple LLM providers with automatic fallback:
- OpenAI (gpt-4o-mini, gpt-4.1-nano)
- Anthropic (claude-3-haiku)
- Google Gemini (gemini-2.0-flash)

Features:
- Provider rotation on failure
- Task-based model selection (cheap for rewriting, powerful for answering)
- Unified interface via LangChain BaseChatModel
"""

import logging
from typing import Optional, List, Literal
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel

from chatbot_viva.core import config
from chatbot_viva.core.tracing import get_langfuse_callback
from chatbot_viva.core.singleton import singleton

logger = logging.getLogger(__name__)

TaskType = Literal[
    "rewrite",       # Query rewriting (cheap, fast)
    "route",         # Intent classification (cheap, fast)
    "answer",        # Main answer generation (quality matters)
    "grade",         # Document grading (cheap)
    "finance",       # Financial analysis (quality matters)
    "property",      # Property analysis (quality matters)
    "stream",        # Streaming response (quality + streaming)
]


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    api_key: Optional[str]
    models: dict  # task_type -> model_name
    priority: int  # Lower = higher priority

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)


# Provider registry
def _build_providers() -> List[ProviderConfig]:
    """Build provider list from environment variables."""
    providers = []

    # Determine priority from LLM_PROVIDER setting
    preferred = getattr(config, "LLM_PROVIDER", "openai")
    provider_priority = {"openai": 10, "anthropic": 10, "google": 10, "gemini": 10}
    # Map "gemini" → "google" internally
    if preferred in ("gemini", "google"):
        provider_priority["google"] = 1
    elif preferred == "anthropic":
        provider_priority["anthropic"] = 1
    else:
        provider_priority["openai"] = 1

    # Use LLM_MODEL from config as the quality model for the preferred provider
    llm_model = config.LLM_MODEL

    # OpenAI
    openai_key = config.OPENAI_API_KEY
    if openai_key:
        openai_quality = llm_model if preferred == "openai" else "gpt-4.1-nano"
        cheap = config.OPENAI_MODEL_CHEAP
        quality = config.OPENAI_MODEL_QUALITY or openai_quality
        providers.append(
            ProviderConfig(
                name="openai",
                api_key=openai_key,
                models={
                    "rewrite": cheap, "route": cheap, "grade": cheap,
                    "answer": quality, "finance": quality,
                    "property": quality, "stream": quality,
                },
                priority=provider_priority["openai"],
            ))

    # Anthropic
    anthropic_key = config.ANTHROPIC_API_KEY
    if anthropic_key:
        anthropic_quality = llm_model if preferred == "anthropic" else "claude-3-haiku-20240307"
        cheap = config.ANTHROPIC_MODEL_CHEAP
        quality = config.ANTHROPIC_MODEL_QUALITY or anthropic_quality
        providers.append(
            ProviderConfig(
                name="anthropic",
                api_key=anthropic_key,
                models={
                    "rewrite": cheap, "route": cheap, "grade": cheap,
                    "answer": quality, "finance": quality,
                    "property": quality, "stream": quality,
                },
                priority=provider_priority["anthropic"],
            ))

    # Google Gemini
    google_key = config.GOOGLE_API_KEY
    if google_key:
        gemini_model = llm_model if preferred in ("gemini", "google") else "gemini-2.0-flash"
        cheap = config.GOOGLE_MODEL_CHEAP or gemini_model
        quality = config.GOOGLE_MODEL_QUALITY or gemini_model
        providers.append(
            ProviderConfig(
                name="google",
                api_key=google_key,
                models={
                    "rewrite": cheap, "route": cheap, "grade": cheap,
                    "answer": quality, "finance": quality,
                    "property": quality, "stream": quality,
                },
                priority=provider_priority["google"],
            ))

    providers.sort(key=lambda p: p.priority)
    return providers


def _create_llm_for_provider(
    provider: ProviderConfig,
    task: TaskType,
    temperature: float = 0,
    streaming: bool = False,
    **kwargs,
) -> BaseChatModel:
    """Create an LLM instance for a specific provider and task."""
    model_name = provider.models.get(task, provider.models.get("answer"))

    if provider.name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=provider.api_key,
            streaming=streaming,
            **kwargs,
        )

    if provider.name == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            api_key=provider.api_key,
            streaming=streaming,
            **kwargs,
        )

    if provider.name == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=provider.api_key,
            streaming=streaming,
            timeout=180,
            **kwargs,
        )

    raise ValueError(f"Unknown provider: {provider.name}")


class LLMFactory:
    """
    Factory for creating LLM instances with automatic fallback.

    Usage:
        factory = get_llm_factory()
        llm = factory.create("answer", temperature=0.3)
        llm = factory.create("rewrite")  # cheaper model
    """

    def __init__(self):
        self._providers = _build_providers()
        if not self._providers:
            raise RuntimeError(
                "No LLM providers configured. Set at least one of: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
            )
        primary = self._providers[0]
        logger.info(
            "LLMFactory initialized with %d providers. "
            "Primary: %s",
            len(self._providers), primary.name,
        )

    @property
    def providers(self) -> List[ProviderConfig]:
        return self._providers

    @property
    def primary_provider(self) -> ProviderConfig:
        return self._providers[0]

    def create(
        self,
        task: TaskType = "answer",
        temperature: float = None,
        streaming: bool = False,
        preferred_provider: str = None,
        **kwargs,
    ) -> BaseChatModel:
        """
        Create an LLM instance with fallback across providers.

        Args:
            task: Task type to select appropriate model tier.
            temperature: LLM temperature. Defaults based on task.
            streaming: Whether to enable streaming.
            preferred_provider: Force a specific provider name.
            **kwargs: Additional kwargs passed to the LLM constructor.

        Returns:
            BaseChatModel instance.
        """
        if temperature is None:
            temperature = self._default_temperature(task)

        logger.info("Creating LLM: task=%s, temp=%.1f, stream=%s", task, temperature, streaming)

        # Inject Langfuse callback if available
        langfuse_cb = get_langfuse_callback()
        if langfuse_cb:
            existing_callbacks = kwargs.get("callbacks", []) or []
            kwargs["callbacks"] = existing_callbacks + [langfuse_cb]

        # Determine provider order
        if preferred_provider:
            providers = [
                p for p in self._providers if p.name == preferred_provider]
            providers += [p for p in self._providers if p.name !=
                          preferred_provider]
        else:
            providers = self._providers

        errors = []
        for provider in providers:
            if not provider.is_available:
                continue
            try:
                llm = _create_llm_for_provider(
                    provider, task, temperature, streaming, **kwargs
                )
                logger.debug("Created %s LLM for task=%s", provider.name, task)
                return llm
            except ImportError as e:
                logger.warning(
                    "Provider %s import failed: %s",
                    provider.name, e,
                )
                errors.append((provider.name, str(e)))
            except Exception as e:
                logger.warning(
                    "Provider %s creation failed: %s",
                    provider.name, e,
                )
                errors.append((provider.name, str(e)))

        raise RuntimeError(
            f"All LLM providers failed for task '{task}': {errors}"
        )

    def create_with_fallback(
        self,
        task: TaskType = "answer",
        temperature: float = None,
        streaming: bool = False,
        **kwargs,
    ) -> "FallbackLLM":
        """
        Create an LLM wrapper that automatically retries with other providers
        on invocation failure (not just creation failure).

        Returns:
            FallbackLLM that wraps multiple providers.
        """
        if temperature is None:
            temperature = self._default_temperature(task)

        llms = []
        for provider in self._providers:
            if not provider.is_available:
                continue
            try:
                llm = _create_llm_for_provider(
                    provider, task, temperature, streaming, **kwargs
                )
                llms.append((provider.name, llm))
            except (ImportError, Exception) as e:
                logger.warning(
                    "Skipping %s: %s", provider.name, e
                )

        if not llms:
            raise RuntimeError("No LLM providers available")

        return FallbackLLM(llms)

    def _default_temperature(self, task: TaskType) -> float:
        """Get default temperature based on task type."""
        defaults = {
            "rewrite": 0,
            "route": 0,
            "grade": 0,
            "answer": max(config.TEMPERATURE, 0.25),
            "finance": max(config.TEMPERATURE, 0.4),
            "property": max(config.TEMPERATURE, 0.4),
            "stream": config.TEMPERATURE,
        }
        return defaults.get(task, config.TEMPERATURE)


class FallbackLLM:
    """
    Wrapper that tries multiple LLMs in order on invocation failure.
    Implements the same interface as BaseChatModel for invoke/stream.
    """

    def __init__(self, llms: List[tuple]):
        """llms: List of (provider_name, llm_instance) tuples."""
        self._llms = llms
        # Expose the primary LLM's attributes for compatibility
        self._primary = llms[0][1] if llms else None

    def invoke(self, *args, **kwargs):
        errors = []
        for name, llm in self._llms:
            try:
                return llm.invoke(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "[FallbackLLM] %s failed: %s", name, e
                )
                errors.append((name, str(e)))
        raise RuntimeError(
            "All providers failed: %s" % errors
        )

    def stream(self, *args, **kwargs):
        errors = []
        has_yielded = False
        for name, llm in self._llms:
            try:
                for chunk in llm.stream(*args, **kwargs):
                    has_yielded = True
                    yield chunk
                return
            except Exception as e:
                logger.warning(
                    "[FallbackLLM] %s stream failed: %s",
                    name, e,
                )
                errors.append((name, str(e)))
                # If we already yielded chunks, don't try fallback
                # (would result in duplicate/mixed content)
                if has_yielded:
                    logger.error(
                        "Stream failed mid-response from %s, cannot fallback safely", name
                    )
                    return
        raise RuntimeError(
            "All providers failed for streaming: %s" % errors
        )

    def bind_tools(self, *args, **kwargs):
        """Bind tools to primary LLM (tools usually provider-specific)."""
        if self._primary:
            return self._primary.bind_tools(*args, **kwargs)
        raise RuntimeError("No primary LLM available")

    def __getattr__(self, name):
        """Proxy unknown attributes to primary LLM."""
        if self._primary:
            return getattr(self._primary, name)
        raise AttributeError(f"No primary LLM: {name}")


@singleton
def get_llm_factory() -> LLMFactory:
    """Get or create the global LLMFactory singleton (thread-safe)."""
    logger.info("Initializing LLM Factory...")
    factory = LLMFactory()
    logger.info(
        "LLM Factory ready with %d providers",
        len(factory.providers),
    )
    return factory
