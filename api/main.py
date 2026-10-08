"""
[api/main.py]
FastAPI 애플리케이션 진입점 및 수명주기(Lifespan) 관리.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cosmetic_agent.service import ReviewService
from cosmetic_agent.common.logger import get_logger
from api.routes import health, review, search

logger = get_logger("API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 기동 시 싱글톤 서비스 1회 생성 (그래프, DB 클라이언트 등 재사용)
    logger.info("FastAPI 기동: ReviewService 싱글톤 객체 로드 중...")
    app.state.review_service = ReviewService()
    logger.info("FastAPI 준비 완료")
    yield
    logger.info("FastAPI 종료 중...")


def create_app() -> FastAPI:
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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
