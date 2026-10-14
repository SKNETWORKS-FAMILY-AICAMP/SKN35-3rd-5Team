from fastapi import APIRouter, HTTPException, Request

from cosmetic_agent.domain.schemas import GenerateRequest, GenerateResponse
from cosmetic_agent.models.copy_generator import GenerationUnavailable

router = APIRouter(prefix="/generate", tags=["Generate"])


@router.post("", response_model=GenerateResponse)
def generate_copy(req: GenerateRequest, request: Request):
    try:
        return request.app.state.generation_service.generate(req)
    except GenerationUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
