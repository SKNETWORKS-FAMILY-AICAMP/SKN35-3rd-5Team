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


def assistant_history_text(response: dict) -> str:
    """Keep conversational content and copy references without serializing tool metadata."""
    parts = [str(response.get("message") or "")[:2000]]
    review = response.get("review") or {}
    if review:
        result = review.get("result") or {}
        parts.append("검토한 문구: " + str(review.get("input_text") or "")[:1000])
        for label, key in (("검토 사유", "review_notes"), ("수정 제안", "suggestion"), ("필요한 확인", "next_test")):
            if result.get(key):
                parts.append(label + ": " + str(result[key])[:700])
    generation = response.get("generation") or {}
    citations = [*(response.get("citations") or []),
                 *((review.get("result") or {}).get("citations") or []),
                 *(generation.get("citations") or [])]
    for index, candidate in enumerate(generation.get("candidates", [])[:3], 1):
        parts.append(f"광고 후보 {index} ({candidate.get('status', '확인필요')}): " + str(candidate.get("text") or "")[:1000])
        candidate_review = (candidate.get("review") or {}).get("result") or {}
        notes = [*(candidate.get("notes") or []), candidate_review.get("review_notes"), candidate_review.get("next_test")]
        notes = list(dict.fromkeys(str(note) for note in notes if note))
        if notes:
            parts.append("검토 사유: " + " / ".join(notes)[:300])
        citations.extend(candidate_review.get("citations") or [])
    for citation in citations[:3]:
        parts.append(f"참고 규정 {citation.get('source', '')} {citation.get('article', '')}: "
                     + str(citation.get("content_snippet") or "")[:300])
    return "\n".join(part for part in parts if part)[:6000]


class ChatContext(BaseModel):
    ingredients: list[IngredientName] = Field(default_factory=list, max_length=100)
    channel: Literal["SNS", "상세페이지", "배너", "검색광고", "라이브커머스"] = "SNS"
    tone: str = Field(default="담백한", min_length=1, max_length=100)
    length: Literal["한 줄", "짧은 문단", "상세 설명"] = "짧은 문단"
    product_name: str = Field(default="나의 화장품", max_length=100)
    product_source: Literal["selected", "conversation"] = Field(default="selected", description="현재 주제가 선택 제품인지 대화에서 새로 설명한 제품인지. 서버가 결정")
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
