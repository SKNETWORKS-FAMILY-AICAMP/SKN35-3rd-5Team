"""규정과 검토 기준 안에서 신규 광고 문구 후보를 생성한다."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..common.config import settings
from ..domain.copy_knowledge import build_generation_knowledge
from .copy_suggester import find_functional_ceiling, load_claim_assets
from .generation_prompts import GENERATION_SYSTEM_PROMPT, build_generation_prompt
from .prompts import build_claim_menu


class GeneratedDraft(BaseModel):
    text: str = Field(min_length=1)
    tier: Literal["strong", "balanced", "safe"]
    rationale: str = ""
    used_evidence: list[str] = Field(default_factory=list)
    cited_ids: list[str] = Field(default_factory=list)
    market_reference_ids: list[str] = Field(default_factory=list)
    market_application: str = ""
    ingredient_reference_ids: list[str] = Field(default_factory=list)
    ingredient_application: str = ""
    headline: str = ""
    supporting_copy: str = ""
    creative_reference_ids: list[str] = Field(default_factory=list)
    creative_application: str = ""
    evidence_reference_ids: list[str] = Field(default_factory=list)


class GenerationOutput(BaseModel):
    candidates: list[GeneratedDraft] = Field(min_length=3, max_length=6)


class CopyGenerator:
    def __init__(self, llm: Any = None, model_name: str | None = None):
        self._llm = llm
        self.model_name = model_name or settings.GENERATION_MODEL_NAME or settings.OPENAI_MODEL_NAME
        self.functional_ceilings, self.claim_ladder = load_claim_assets()

    @property
    def llm(self) -> Any:
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model_name,
                # 다양성은 재료·각도로 확보하고, 안전성은 생성 뒤 검증기·판정이 막는다
                temperature=0.8,
                api_key=settings.OPENAI_API_KEY or None,
                base_url=settings.OPENAI_BASE_URL,
            ).with_structured_output(GenerationOutput)
        return self._llm

    def generate(self, **kwargs: Any) -> list[dict[str, Any]]:
        product = kwargs.get("product") or {}
        if "claim_menu" not in kwargs:
            # 문구 제안과 같은 방식으로 '쓸 수 있는 표현 상한'을 계산해 준다
            kwargs["claim_menu"] = build_claim_menu(
                copy_text=" ".join(filter(None, [kwargs.get("instruction", ""), *kwargs.get("keywords", [])])),
                product=product,
                owned_evidence=product.get("owned_evidence", []),
                claim_ladder=self.claim_ladder,
                functional_ceiling=find_functional_ceiling(product.get("functional_type"), self.functional_ceilings),
            )
        if "knowledge" not in kwargs:
            kwargs["knowledge"] = build_generation_knowledge(product, kwargs.get("channel", ""))
        prompt = build_generation_prompt(**kwargs)
        output = self.llm.invoke([
            ("system", GENERATION_SYSTEM_PROMPT),
            ("human", prompt),
        ])
        if isinstance(output, dict):
            output = GenerationOutput.model_validate(output)
        required = ("strong", "balanced", "safe")
        if not set(required) <= {candidate.tier for candidate in output.candidates}:
            raise ValueError("생성 결과에는 strong, balanced, safe 후보가 각각 하나 이상 필요합니다.")
        # 후보를 넉넉히(최대 6개) 받아, 검증을 통과한 것 중 끌림 순위로 3개를 고른다 (generation/nodes.py)
        order = {tier: i for i, tier in enumerate(required)}
        ranked = sorted(output.candidates, key=lambda c: order[c.tier])
        # 화면에는 헤드라인·설명이 따로 나가므로 세 필드 모두 정리한다
        return [dict(c.model_dump(), text=clean_copy(c.text), headline=clean_copy(c.headline),
                     supporting_copy=clean_copy(c.supporting_copy)) for c in ranked]


def clean_copy(text: str) -> str:
    """광고 문구에 섞여 나오는 마크다운 강조·무대 지시([제품을 보여주며])·이스케이프 줄바꿈을 지운다."""
    text = text.replace("\\n", "\n").replace("**", "")
    # 라이브커머스 무대 지시([제품을 보여주며], [감탄하며])만 지운다. [NEW]·[1+1 기획] 같은 표기는 남긴다
    text = re.sub(r"\[[^\]\n]{0,30}(?:며|면서|하고|보여|들고|감탄|웃|카메라|화면|진행자|손짓)[^\]\n]{0,10}\]", "", text)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)  # 마크다운 제목. 해시태그(#보습)는 공백이 없어 남는다
    text = re.sub(r"\n{2,}", "\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()
