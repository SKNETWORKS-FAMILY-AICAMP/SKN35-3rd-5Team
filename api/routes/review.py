"""
[api/routes/review.py]
광고 문구 검토 API 엔드포인트.
"""
from fastapi import APIRouter, Request, HTTPException
from api.text import MAX_SENTENCES, split_sentences
from cosmetic_agent.domain.schemas import (
    ReviewRequest,
    BulkReviewRequest,
    ReviewResponse,
)

router = APIRouter(prefix="/review", tags=["Review"])


@router.post("", response_model=ReviewResponse)
def review_single_copy(req: ReviewRequest, request: Request):
    """단일 광고 문구 검토 엔드포인트"""
    service = request.app.state.review_service
    return service.review_single(req.copy_text, req.product)


@router.post("/bulk", response_model=list[ReviewResponse])
def review_bulk_copies(req: BulkReviewRequest, request: Request):
    """줄바꿈 및 문장부호로 분리해 입력 순서대로 검토 (최대 100문장).

    제품 카드와 보유 시험 자료는 모든 문장에 동일하게 전달됩니다.
    """
    sentences = split_sentences(req.full_text)
    if not sentences:
        raise HTTPException(status_code=422, detail="검토할 문장이 없습니다.")
    if len(sentences) > MAX_SENTENCES:
        raise HTTPException(status_code=422, detail=f"한 번에 최대 {MAX_SENTENCES}문장까지 검토할 수 있습니다.")
    service = request.app.state.review_service
    return [service.review_single(sentence, req.product) for sentence in sentences]
