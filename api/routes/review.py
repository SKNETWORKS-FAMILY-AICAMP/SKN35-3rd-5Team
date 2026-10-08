"""
[api/routes/review.py]
광고 문구 검토 API 엔드포인트.
"""
from fastapi import APIRouter, Request
from cosmetic_agent.domain.schemas import (
    ReviewRequest,
    BulkReviewRequest,
    ReviewResponse,
)

router = APIRouter(prefix="/review", tags=["Review"])


@router.post("", response_model=ReviewResponse)
async def review_single_copy(req: ReviewRequest, request: Request):
    """단일 광고 문구 검토 엔드포인트"""
    service = request.app.state.review_service
    return service.review_single(req.copy_text, req.product)


@router.post("/bulk", response_model=list[ReviewResponse])
async def review_bulk_copies(req: BulkReviewRequest, request: Request):
    """상세페이지 전체 일괄 검토 엔드포인트"""
    service = request.app.state.review_service
    return service.review_bulk(req.full_text, req.product)
