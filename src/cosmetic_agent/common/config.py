"""
[common/config.py]
Pydantic Settings 기반의 환경변수 및 YAML 설정 로더.
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "cosmetic-ad-agent"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "cosmetic_ad_rules"
    QDRANT_API_KEY: str = ""

    # BM25
    BM25_INDEX_PATH: Path = Path("data/02_processed/bm25_index.pkl")

    # Judge Backend (rule / gpt / ft)
    JUDGE_BACKEND: Literal["rule", "gpt", "ft"] = "rule"
    FT_ADAPTER_PATH: Path = Path("finetune/adapters/qwen_ad_judge_v1")

    # LangSmith
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "cosmetic-ad-agent"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
