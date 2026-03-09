from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM API Keys ─────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""

    # ── Search API ───────────────────────────────────────────────────────────
    serpapi_key: str = ""

    # ── LLM Defaults ─────────────────────────────────────────────────────────
    research_llm_provider: Literal["gemini", "groq", "mistral"] = "gemini"
    research_llm_model: str = "gemini-2.0-flash"

    writing_llm_provider: Literal["gemini", "groq", "mistral"] = "mistral"
    writing_llm_model: str = "mistral-large-latest"

    qa_llm_provider: Literal["gemini", "groq", "mistral"] = "groq"
    qa_llm_model: str = "llama-3.3-70b-versatile"

    # ── Output ───────────────────────────────────────────────────────────────
    output_dir: str = "output"


settings = Settings()
