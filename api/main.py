"""
[api/main.py]
FastAPI 애플리케이션 진입점 및 수명주기(Lifespan) 관리.
"""
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, generate, health, review, search
from cosmetic_agent.common.logger import get_logger
from cosmetic_agent.models.copy_generator import CopyGenerationService
from cosmetic_agent.models.chatbot import ChatService

logger = get_logger("API")


def build_review_service():
    # API 계약 테스트에서는 모델/검색 인프라를 로드하지 않습니다.
    from cosmetic_agent.service import ReviewService
    return ReviewService()


def create_app(service_factory: Callable[[], Any] = build_review_service, generation_factory=CopyGenerationService, chat_factory=ChatService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("FastAPI 기동: 검토 서비스 로드 중...")
        app.state.review_service = service_factory()
        app.state.generation_service = generation_factory(app.state.review_service)
        app.state.chat_service = chat_factory(app.state.review_service, app.state.generation_service)
        logger.info("FastAPI 준비 완료")
        yield
        logger.info("FastAPI 종료 중...")

    app = FastAPI(
        title="화장품 광고 문구 심사 및 교정 에이전트 API",
        version="0.1.0",
        description="화장품 표시·광고 법령 및 식약처 지침 기반 컴플라이언스 AI 에이전트 API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(review.router)
    app.include_router(search.router)
    app.include_router(generate.router)
    app.include_router(chat.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
