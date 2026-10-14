from fastapi import APIRouter, HTTPException, Request

from cosmetic_agent.domain.generation import GenerateRequest, GenerateResponse
from cosmetic_agent.domain.schemas import GenerateRequest as ProjectGenerateRequest
from cosmetic_agent.domain.schemas import GenerateResponse as ProjectGenerateResponse
from cosmetic_agent.models.copy_generator import GenerationUnavailable

router = APIRouter(prefix="/generate", tags=["Generate"])


@router.post("", response_model=GenerateResponse | ProjectGenerateResponse)
def generate_copy(req: GenerateRequest | ProjectGenerateRequest, request: Request):
    # kgm 성분 기반 요청과 dev 제품·실증 기반 요청의 계약을 모두 유지한다.
    if isinstance(req, ProjectGenerateRequest):
        return request.app.state.review_service.generate_copy(req)
    try:
        return request.app.state.generation_service.generate(req)
    except GenerationUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
