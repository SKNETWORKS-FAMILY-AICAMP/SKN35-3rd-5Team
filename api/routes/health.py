"""
[api/routes/health.py]
시스템 상태 및 의존성 헬스체크 라우트.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "cosmetic-ad-agent",
        "version": "0.1.0",
    }
