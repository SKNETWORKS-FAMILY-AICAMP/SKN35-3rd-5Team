"""
[domain/schemas.py]
Pydantic 기반의 결과 계약 모델 및 요청/응답 스키마.
"""
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, StringConstraints, model_validator

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OwnedEvidence(BaseModel):
    """보유 근거 스키마"""
    test_type: RequiredText = Field(description="시험 종류 (예: 인체적용시험, 시험성적서 등)")
    item: RequiredText = Field(description="시험 항목 (예: 피부 겉보습 개선)")
    value: Optional[str] = Field(default=None, description="수치 및 결과 (예: 42% 개선)")
    institute: Optional[str] = Field(default=None, description="시험 기관")
    source_kind: Literal["provided_report", "public_brand_summary"] = "provided_report"
    source_url: str | None = None
    conditions: str | None = None
    report_available: bool | None = None


class ProductCard(BaseModel):
    """제품 카드 스키마"""
    product_id: RequiredText
    name: RequiredText
    category: Literal["일반", "기능성"]
    functional_type: Optional[str] = None
    key_ingredients: list[str] = Field(default_factory=list, description="주요 성분 (예: 나이아신아마이드, 판테놀)")
    owned_evidence: list[OwnedEvidence] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list, description="제공된 전성분명. 효능 시험 근거와 구분")
    ingredient_source: Optional[str] = None


class Citation(BaseModel):
    """근거 법령/지침 조항 스키마"""
    chunk_id: str = Field(description="청크 고유 ID (예: LAW_시행규칙_별표5-2가)")
    source: str = Field(description="출처 법령/규정명 (예: 화장품법 시행규칙)")
    article: str = Field(description="조항 번호 (예: 별표5 제2호 가목)")
    authority: Literal[1, 2, 3, 4] = Field(description="1 법령 · 2 고시 · 3 지침 · 4 사례")
    content_snippet: Optional[str] = None


class ReviewResult(BaseModel):
    """
    [결과 계약 모델]
    판정 결과가 비즈니스 규칙을 엄격히 준수하는지 model_validator로 강제합니다.
    """
    status: Literal["판정", "판단보류"]
    level: Optional[Literal[0, 1, 2]] = Field(
        default=None, description="0 가능 · 1 조건부 · 2 불가 (판단보류 시 None)"
    )
    violation_type: Literal[
        "의약품오인", "범위이탈", "기능성오인", "실증필요", "비교광고", "소비자오인", "없음"
    ] = "없음"
    claim_type: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    suggestion: Optional[str] = Field(default=None, description="현재 보유 근거 기준 최선의 문구")
    next_test: Optional[str] = Field(default=None, description="상위 표현을 위해 필요한 추가 시험")
    review_notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_business_contracts(self) -> "ReviewResult":
        # 규칙 1: 판정 상태에서 조건부(1) 또는 불가(2)이면 반드시 근거 조항(citations)이 있어야 함
        if self.status == "판정" and self.level is not None and self.level > 0:
            if not self.citations:
                raise ValueError("조건부(1) 또는 불가(2) 판정 시 반드시 1개 이상의 근거 조항(citation)이 존재해야 합니다.")

        # 규칙 2: 조건부(1) 판정 시 반드시 필요한 시험(next_test)이 기재되어야 함
        if self.status == "판정" and self.level == 1:
            if not self.next_test or not self.next_test.strip():
                raise ValueError("조건부(1) 판정 시 추가로 요구되는 시험(next_test) 안내가 필수입니다.")

        return self


class ReviewRequest(BaseModel):
    """단일 문구 검토 요청 스키마"""
    copy_text: RequiredText = Field(max_length=5000, description="검토할 단일 광고 문구 (최대 5,000자)")
    product: ProductCard = Field(description="대상 제품 정보")


class BulkReviewRequest(BaseModel):
    """상세페이지 일괄 검토 요청 스키마"""
    full_text: RequiredText = Field(max_length=50000, description="상세페이지 전체 텍스트 (최대 50,000자, 100문장)")
    product: ProductCard = Field(description="대상 제품 정보")


class ExecutionTiming(BaseModel):
    retrieval_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0


class ReviewResponse(BaseModel):
    """단일 문구 검토 응답 스키마"""
    request_id: str
    input_text: str
    result: ReviewResult
    timing: ExecutionTiming
    # 문구 제안 후보 (화면의 '근거 최대 · 균형 · 가장 안전' 탭). result.suggestion 은 그중 검증을 통과한 것.
    candidates: list[str] = Field(default_factory=list, description="강한 순서의 제안 후보")
    rejected_notes: list[str] = Field(default_factory=list, description="검증에서 탈락한 후보의 사유 (후보 순서)")
    used_evidence: list[str] = Field(default_factory=list, description="후보에 사용한 보유 근거")
    # 후보 비교표: text, tier, chosen, verified, verify_note, removed_risky, kept_risky,
    # evidence_numbers, changes(원문 대비 변경점), hypothesis(A/B 가설), target_metric
    candidate_details: list[dict] = Field(default_factory=list, description="후보별 검증 결과·변경점·A/B 가설")
    # A/B 실험 초안: primary_metric, control(가장 안전 후보), variants(가설 포함), excluded, note
    experiment: dict = Field(default_factory=dict, description="A/B 실험 초안 (검증 통과 후보만)")


class GenerateRequest(BaseModel):
    """검토 기준을 사용한 광고 문구 생성 요청."""
    instruction: RequiredText = Field(max_length=2000, description="생성 목적과 요청사항")
    product: ProductCard
    channel: Literal["상세페이지", "SNS", "배너", "검색광고", "라이브커머스"] = "상세페이지"
    tone: RequiredText = "고급스러운"
    length: Literal["한 줄", "짧은 문단", "상세 설명"] = "한 줄"
    keywords: list[str] = Field(default_factory=list, max_length=10)


class GeneratedCandidate(BaseModel):
    text: RequiredText
    tier: Literal["strong", "balanced", "safe"]
    rationale: str = ""
    used_evidence: list[str] = Field(default_factory=list)
    cited_ids: list[str] = Field(default_factory=list)
    verified: bool = True
    verify_note: str = "검증 통과"


class GenerateResponse(BaseModel):
    request_id: str
    status: Literal["생성완료", "생성보류"]
    product_id: str
    candidates: list[GeneratedCandidate] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timing: ExecutionTiming
    mock: bool = False
