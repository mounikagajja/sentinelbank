from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from backend.app.core.config import get_settings

settings = get_settings()

TEMPERATURE = 0.0


class LLMConfigError(RuntimeError):
    pass


def build_groq() -> BaseChatModel:
    from langchain_groq import ChatGroq

    if not settings.groq_api_key:
        raise LLMConfigError("GROQ_API_KEY is not set. Add it to .env or set LLM_PROVIDER=ollama.")
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=TEMPERATURE,
        max_retries=2,
        timeout=30,
    )


def build_ollama() -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=TEMPERATURE,
    )


BUILDERS = {"groq": build_groq, "ollama": build_ollama}


@lru_cache
def get_llm() -> BaseChatModel:
    builder = BUILDERS.get(settings.llm_provider)
    if builder is None:
        raise LLMConfigError(
            f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Use one of {sorted(BUILDERS)}."
        )
    return builder()
