"""통합 챗봇의 요청, 대화 맥락, 실행 결과."""
from typing import Literal

from pydantic import BaseModel, Field

from .generation import GenerateResponse, IngredientName
from .schemas import ProductCard, RequiredText, ReviewResponse


class ChatContext(BaseModel):
    ingredients: list[IngredientName] = Field(default_factory=list, max_length=100)
    channel: Literal["SNS", "상세페이지", "배너"] = "SNS"
    tone: Literal["담백한", "감성적인", "발랄한", "눈길 끄는"] = "담백한"
    product_name: str = Field(default="나의 화장품", max_length=100)
    brief: str = Field(default="", max_length=1000)
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
    intent: Literal["review", "generate", "clarify"]
    message: str
    context: ChatContext
    review: ReviewResponse | None = None
    generation: GenerateResponse | None = None
