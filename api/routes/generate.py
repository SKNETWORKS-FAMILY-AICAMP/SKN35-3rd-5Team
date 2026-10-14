"""검토 기준 기반 신규 광고 문구 생성 API."""

from fastapi import APIRouter, Request

from cosmetic_agent.domain.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/generate", tags=["Generate"])


@router.post("", response_model=GenerateResponse)
def generate_copy(req: GenerateRequest, request: Request):
    return request.app.state.review_service.generate_copy(req)
