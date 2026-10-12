"""
[common/config.py]
프로젝트 공통 환경설정 및 Pydantic Settings 로더.
로컬/개인별 설정(API 키, 커스텀 엔드포인트 등)은 .env 파일에서 덮어씁니다.
"""
from pathlib import Path
from typing import Literal
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. 프로젝트 루트 자동 탐색 (현재 파일 기준 4단계 상위 폴더: src/cosmetic_agent/common/config.py -> 루트)
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROJECT_ROOT: Path = Path(os.getenv("PROJECT_ROOT", str(DEFAULT_ROOT))).resolve()

# 2. 데이터 하위 디렉토리 기본 경로
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

    # OpenAI & LLM API (기본값: 표준 OpenAI, 커스텀/NVIDIA 사용자는 .env에서 오버라이드)
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "cosmetic_ad_rules_v2"
    QDRANT_API_KEY: str = ""

    # Assets & Indexes 파일 기본 경로
    BM25_INDEX_PATH: Path = PROCESSED_DIR / "bm25_index.pkl"
    BANNED_TERMS_PATH: Path = ASSETS_DIR / "banned_terms.json"
    CLAIM_LADDER_PATH: Path = ASSETS_DIR / "claim_ladder.json"
    FUNCTIONAL_CLAIMS_PATH: Path = ASSETS_DIR / "functional_claims.json"
    TERM_MAP_PATH: Path = ASSETS_DIR / "term_map.json"
    MOCK_PRODUCTS_PATH: Path = ASSETS_DIR / "mock_products.json"
    DEV_SET_PATH: Path = GOLDEN_SET_DIR / "dev.jsonl"
    HOLDOUT_SET_PATH: Path = GOLDEN_SET_DIR / "holdout.jsonl"

    # 공공데이터포털 (화장품 원료성분정보 등)
    DATA_GO_KR_API_KEY: str = ""

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

