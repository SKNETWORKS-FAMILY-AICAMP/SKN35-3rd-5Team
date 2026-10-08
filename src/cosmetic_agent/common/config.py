"""
[common/config.py]
Pydantic Settings 기반의 환경변수 및 절대 경로 설정 로더.
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 경로 (어느 디렉토리에서 실행해도 항상 고정된 절대 경로 기준 제공)
# src/cosmetic_agent/common/config.py -> parents[3] = 프로젝트 루트 (레포지토리 최상위)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

# 주요 디렉토리 경로
DATA_DIR: Path = PROJECT_ROOT / "data"
ASSETS_DIR: Path = DATA_DIR / "assets"
PROCESSED_DIR: Path = DATA_DIR / "02_processed"
GOLDEN_SET_DIR: Path = DATA_DIR / "golden_set"


class Settings(BaseSettings):
    # App & API
    PROJECT_NAME: str = "cosmetic-ad-agent"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "cosmetic_ad_rules"
    QDRANT_API_KEY: str = ""

    # Assets & Indexes 파일 절대 경로
    BM25_INDEX_PATH: Path = PROCESSED_DIR / "bm25_index.pkl"
    BANNED_TERMS_PATH: Path = ASSETS_DIR / "banned_terms.json"
    CLAIM_LADDER_PATH: Path = ASSETS_DIR / "claim_ladder.json"
    FUNCTIONAL_CLAIMS_PATH: Path = ASSETS_DIR / "functional_claims.json"
    TERM_MAP_PATH: Path = ASSETS_DIR / "term_map.json"
    MOCK_PRODUCTS_PATH: Path = ASSETS_DIR / "mock_products.json"
    DEV_SET_PATH: Path = GOLDEN_SET_DIR / "dev.jsonl"
    HOLDOUT_SET_PATH: Path = GOLDEN_SET_DIR / "holdout.jsonl"

    # Judge Backend (rule / gpt / ft)
    JUDGE_BACKEND: Literal["rule", "gpt", "ft"] = "rule"
    FT_ADAPTER_PATH: Path = PROJECT_ROOT / "finetune" / "adapters" / "qwen_ad_judge_v1"

    # LangSmith
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "cosmetic-ad-agent"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
