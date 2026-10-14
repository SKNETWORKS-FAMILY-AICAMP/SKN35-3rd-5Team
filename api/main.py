"""
[api/main.py]
FastAPI 애플리케이션 진입점 및 수명주기(Lifespan) 관리.
"""
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from qdrant_client.http.exceptions import ResponseHandlingException

from api.routes import chat, generate, health, review, search
from cosmetic_agent.common.logger import get_logger
from cosmetic_agent.generation.service import UnifiedGenerationService
from cosmetic_agent.models.chatbot import ChatService

logger = get_logger("API")


def build_review_service():
    # API 계약 테스트에서는 모델/검색 인프라를 로드하지 않습니다.
    from cosmetic_agent.service import ReviewService
    return ReviewService()


def create_app(service_factory: Callable[[], Any] = build_review_service, generation_factory=UnifiedGenerationService, chat_factory=ChatService) -> FastAPI:
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

    @app.exception_handler(ResponseHandlingException)
    async def search_database_unavailable(request, exc):
        # 연결 오류의 원문에는 서버 주소 등이 포함될 수 있으므로 전달하지 않는다.
        logger.warning("Qdrant 검색 DB 연결 실패: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "code": "SEARCH_DATABASE_UNAVAILABLE",
                "detail": "검색 DB(Qdrant)에 연결하지 못했습니다. 팀 공유 DB 연결 설정과 서버 실행 상태를 확인해 주세요.",
            },
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
