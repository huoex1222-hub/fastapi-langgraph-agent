"""LLM model registry with pre-initialized instances."""

from typing import (
    Any,
    Dict,
    List,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger

_TOKEN_LIMIT: Dict[str, Any] = {"max_completion_tokens": settings.MAX_TOKENS}
_API_KEY = SecretStr(settings.OPENAI_API_KEY)
_BASE_URL = settings.OPENAI_BASE_URL or None

# Built-in OpenAI registry. Kept as data so the same class can also build a
# registry for any OpenAI-compatible endpoint configured via LLM_MODELS.
_DEFAULT_MODELS: List[Dict[str, Any]] = [
    {
        "name": "gpt-5-mini",
        "model": "gpt-5-mini",
        "reasoning": {"effort": "low"},
    },
    {
        "name": "gpt-5.4",
        "model": "gpt-5",
        "reasoning": {"effort": "medium"},
    },
    {
        "name": "gpt-5.4-nano",
        "model": "gpt-5.4-nano",
        "reasoning": {"effort": "low"},
    },
    {
        "name": "gpt-5",
        "model": "gpt-5",
        "top_p": 0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
        "presence_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
        "frequency_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
    },
]


def _create_llm(model_name: str, **kwargs: Any) -> ChatOpenAI:
    """Create a ChatOpenAI instance for the active provider.

    OpenAI-specific kwargs (``reasoning``, ``max_completion_tokens``) are only
    sent to the official OpenAI endpoint; compatible providers use
    ``max_tokens`` instead.

    Args:
        model_name: Provider-specific model identifier.
        **kwargs: Optional overrides forwarded to ``ChatOpenAI``.

    Returns:
        Configured ``ChatOpenAI`` instance.
    """
    if _BASE_URL:
        kwargs.pop("reasoning", None)
        kwargs.pop("model_kwargs", None)
        kwargs.setdefault("max_tokens", settings.MAX_TOKENS)
        return ChatOpenAI(model=model_name, api_key=_API_KEY, base_url=_BASE_URL, **kwargs)

    return ChatOpenAI(model=model_name, api_key=_API_KEY, **kwargs)


def _build_registry() -> List[Dict[str, Any]]:
    """Build the model registry from env config or the built-in OpenAI list.

    Returns:
        List of ``{"name": str, "llm": ChatOpenAI}`` entries.
    """
    if settings.LLM_MODELS:
        if not _BASE_URL:
            logger.warning("custom_llm_models_without_base_url", models=settings.LLM_MODELS)
        return [{"name": name, "llm": _create_llm(name)} for name in settings.LLM_MODELS]

    entries: List[Dict[str, Any]] = []
    for spec in _DEFAULT_MODELS:
        model_kwargs = {key: value for key, value in spec.items() if key not in ("name", "model")}
        model_kwargs["model_kwargs"] = _TOKEN_LIMIT
        entries.append(
            {
                "name": spec["name"],
                "llm": ChatOpenAI(model=spec["model"], api_key=_API_KEY, **model_kwargs),
            }
        )
    return entries


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    LLMS: List[Dict[str, Any]] = _build_registry()

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        When kwargs are provided a fresh ChatOpenAI instance is returned with
        those overrides applied, leaving the shared registry entry untouched.

        Args:
            model_name: Name of the model to retrieve.
            **kwargs: Optional arguments to override default model configuration.

        Returns:
            BaseChatModel instance.

        Raises:
            ValueError: If model_name is not found in LLMS.
        """
        model_entry = next((e for e in cls.LLMS if e["name"] == model_name), None)

        if not model_entry:
            available = ", ".join(e["name"] for e in cls.LLMS)
            raise ValueError(f"model '{model_name}' not found in registry. available models: {available}")

        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return _create_llm(model_name, **kwargs)

        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Return all registered model names in order.

        Returns:
            List of model name strings.
        """
        return [e["name"] for e in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Return the model entry at a specific index, wrapping to 0 if out of range.

        Args:
            index: Index into LLMS.

        Returns:
            Model entry dict.
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]
