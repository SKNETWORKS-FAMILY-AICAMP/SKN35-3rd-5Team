"""통합 챗봇의 요청, 대화 맥락, 실행 결과."""
from typing import Literal

from pydantic import BaseModel, Field

from .generation import IngredientName
from .schemas import (
    Citation,
    GenerateResponse,
    ProductCard,
    RequiredText,
    ReviewResponse,
)


class ChatContext(BaseModel):
    ingredients: list[IngredientName] = Field(default_factory=list, max_length=100)
    channel: Literal["SNS", "상세페이지", "배너", "검색광고", "라이브커머스"] = "SNS"
    tone: str = Field(default="담백한", min_length=1, max_length=100)
    length: Literal["한 줄", "짧은 문단", "상세 설명"] = "짧은 문단"
    product_name: str = Field(default="나의 화장품", max_length=100)
    brief: str = Field(default="", max_length=2000)
    product_description: str = Field(default="", max_length=2000)
    last_copies: list[str] = Field(default_factory=list, max_length=3)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class ChatRequest(BaseModel):
    message: RequiredText = Field(max_length=5000)
    context: ChatContext = Field(default_factory=ChatContext)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    product: ProductCard = Field(default_factory=lambda: ProductCard(
        product_id="chat_draft", name="나의 화장품", category="일반"))


class ChatResponse(BaseModel):
    intent: Literal["review", "generate", "clarify", "answer"]
    message: str
    context: ChatContext
    review: ReviewResponse | None = None
    generation: GenerateResponse | None = None
    citations: list[Citation] = Field(default_factory=list)
