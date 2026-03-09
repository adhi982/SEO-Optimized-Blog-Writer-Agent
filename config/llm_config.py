import time
from typing import Literal, Union

from crewai import LLM as CrewAILLM
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI

from config.settings import settings


# ── 429 retry wrapper ─────────────────────────────────────────────────────────

class _RetryOnRateLimitLLM:
    """
    Transparent wrapper around any LangChain BaseChatModel.
    On HTTP 429 / RESOURCE_EXHAUSTED it waits (with exponential backoff)
    and retries up to `max_retries` times before re-raising.
    """
    _MAX_RETRIES = 4
    _BASE_WAIT = 15  # seconds

    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    def invoke(self, messages, **kwargs):
        wait = self._BASE_WAIT
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                return self._llm.invoke(messages, **kwargs)
            except Exception as exc:
                msg = str(exc)
                if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < self._MAX_RETRIES:
                    print(f"[LLM] Rate-limited. Waiting {wait}s before retry {attempt + 1}/{self._MAX_RETRIES}…")
                    time.sleep(wait)
                    wait = min(wait * 2, 120)
                else:
                    raise

    # Forward all other attribute access to the underlying LLM
    def __getattr__(self, name):
        return getattr(self._llm, name)

LLMProvider = Literal["gemini", "groq", "mistral"]

# LiteLLM model string prefixes used by CrewAI
_CREWAI_PREFIXES = {
    "gemini": "gemini",
    "groq": "groq",
    "mistral": "mistral",
}

_CREWAI_API_KEYS = {
    "gemini": "gemini_api_key",
    "groq": "groq_api_key",
    "mistral": "mistral_api_key",
}


def get_llm(
    provider: LLMProvider,
    model: str,
    temperature: float = 0.7,
) -> "_RetryOnRateLimitLLM":
    """Factory — returns a LangChain LLM wrapped with 429 retry logic."""
    if provider == "gemini":
        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=settings.gemini_api_key,
        )
    elif provider == "groq":
        llm = ChatGroq(
            model=model,
            temperature=temperature,
            groq_api_key=settings.groq_api_key,
        )
    elif provider == "mistral":
        llm = ChatMistralAI(
            model=model,
            temperature=temperature,
            mistral_api_key=settings.mistral_api_key,
        )
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Choose from: gemini, groq, mistral.")
    return _RetryOnRateLimitLLM(llm)


def get_crewai_llm(
    provider: LLMProvider,
    model: str,
    temperature: float = 0.7,
) -> CrewAILLM:
    """Factory — returns a CrewAI-native LLM (used by CrewAI Agent instances)."""
    prefix = _CREWAI_PREFIXES[provider]
    api_key_attr = _CREWAI_API_KEYS[provider]
    api_key = getattr(settings, api_key_attr, "")
    model_string = f"{prefix}/{model}"
    return CrewAILLM(model=model_string, temperature=temperature, api_key=api_key)


# ── LangChain helpers (LangGraph nodes) ──────────────────────────────────────

def get_research_llm(temperature: float = 0.3) -> BaseChatModel:
    """Gemini — large context, strong reasoning."""
    return get_llm(settings.research_llm_provider, settings.research_llm_model, temperature)


def get_writing_llm(temperature: float = 0.7) -> BaseChatModel:
    """Mistral — strong creative writing."""
    return get_llm(settings.writing_llm_provider, settings.writing_llm_model, temperature)


def get_qa_llm(temperature: float = 0.2) -> BaseChatModel:
    """Groq/Llama — fast inference for QA passes."""
    return get_llm(settings.qa_llm_provider, settings.qa_llm_model, temperature)


# ── CrewAI helpers (CrewAI Agent constructors) ────────────────────────────────

def get_crewai_research_llm(temperature: float = 0.2) -> CrewAILLM:
    return get_crewai_llm(settings.research_llm_provider, settings.research_llm_model, temperature)


def get_crewai_writing_llm(temperature: float = 0.7) -> CrewAILLM:
    return get_crewai_llm(settings.writing_llm_provider, settings.writing_llm_model, temperature)


def get_crewai_qa_llm(temperature: float = 0.2) -> CrewAILLM:
    return get_crewai_llm(settings.qa_llm_provider, settings.qa_llm_model, temperature)
