"""
[common/config.py]
경민님 로컬 환경(C:\\SKN35_kim\\SKN35-3rd-5Team) 전용 절대 경로 및 환경변수 설정 로더.
"""
from pathlib import Path
from typing import Literal
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. 경민님 전용 프로젝트 루트 경로 (기본값: C:\SKN35_kim\SKN35-3rd-5Team)
DEFAULT_ROOT = Path("C:/SKN35_kim/SKN35-3rd-5Team")
PROJECT_ROOT: Path = Path(os.getenv("PROJECT_ROOT", str(DEFAULT_ROOT))).resolve()

# 2. 전용 하위 디렉토리 절대 경로
DATA_DIR: Path = PROJECT_ROOT / "data"
ASSETS_DIR: Path = DATA_DIR / "assets"
PROCESSED_DIR: Path = DATA_DIR / "02_processed"
GOLDEN_SET_DIR: Path = DATA_DIR / "golden_set"


class Settings(BaseSettings):
    # App & API
    PROJECT_NAME: str = "cosmetic-ad-agent"
    PROJECT_ROOT_PATH: Path = PROJECT_ROOT
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"

    # OpenAI & NVIDIA API
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    OPENAI_MODEL_NAME: str = "openai/gpt-oss-20b"
    OPENAI_EMBEDDING_MODEL: str = "nvidia/nemotron-3-embed-1b"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "cosmetic_ad_rules"
    QDRANT_API_KEY: str = ""

    # Assets & Indexes 파일 절대 경로 (경민님 전용 로컬 경로 체계)
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
