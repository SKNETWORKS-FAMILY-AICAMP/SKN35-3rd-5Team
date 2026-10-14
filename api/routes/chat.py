from fastapi import APIRouter, HTTPException, Request

from cosmetic_agent.domain.chat import ChatRequest, ChatResponse
from cosmetic_agent.models.copy_generator import GenerationUnavailable

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    try:
        return request.app.state.chat_service.chat(req)
    except GenerationUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
