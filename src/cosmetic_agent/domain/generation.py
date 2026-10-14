"""성분 기반 광고 생성 요청과 검토 결과 계약."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .schemas import ProductCard, ReviewResponse

IngredientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class GenerateRequest(BaseModel):
    ingredients: list[IngredientName] = Field(min_length=1, max_length=100)
    product: ProductCard
    channel: Literal["SNS", "상세페이지", "배너"] = "SNS"
    tone: Literal["담백한", "감성적인", "발랄한", "눈길 끄는"] = "담백한"
    brief: str = Field(default="", max_length=1000, description="추가 작성 요청. 제품 사실·실증의 근거로 사용하지 않음")
    reference_copy: str = Field(default="", max_length=1000, description="다듬을 이전 후보. 새로운 제품 사실의 근거가 아님")

    @model_validator(mode="after")
    def normalize(self):
        self.ingredients = list(dict.fromkeys(self.ingredients))
        if self.product.category == "기능성" and not (self.product.functional_type or "").strip():
            raise ValueError("기능성 제품은 심사·보고받은 기능성 유형을 입력해야 합니다.")
        return self


class GeneratedCandidate(BaseModel):
    text: str
    status: Literal["검토통과", "확인필요", "제외"]
    notes: list[str] = Field(default_factory=list)
    review: ReviewResponse | None = None


class GenerateResponse(BaseModel):
    candidates: list[GeneratedCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = "자동 검토는 법률 준수를 보장하지 않습니다. 성분 함유 사실과 실증 자료, 최종 광고 맥락을 확인한 뒤 사용하세요."
