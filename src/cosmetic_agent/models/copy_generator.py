"""규정과 검토 기준 안에서 신규 광고 문구 후보를 생성한다."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..common.config import settings
from .generation_prompts import GENERATION_SYSTEM_PROMPT, build_generation_prompt


class GeneratedDraft(BaseModel):
    text: str = Field(min_length=1)
    tier: Literal["strong", "balanced", "safe"]
    rationale: str = ""
    used_evidence: list[str] = Field(default_factory=list)
    cited_ids: list[str] = Field(default_factory=list)


class GenerationOutput(BaseModel):
    candidates: list[GeneratedDraft] = Field(min_length=3, max_length=3)


class CopyGenerator:
    def __init__(self, llm: Any = None, model_name: str | None = None):
        self._llm = llm
        self.model_name = model_name or settings.OPENAI_MODEL_NAME

    @property
    def llm(self) -> Any:
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model_name,
                temperature=0.4,
                api_key=settings.OPENAI_API_KEY or None,
                base_url=settings.OPENAI_BASE_URL,
            ).with_structured_output(GenerationOutput)
        return self._llm

    def generate(self, **kwargs: Any) -> list[dict[str, Any]]:
        prompt = build_generation_prompt(**kwargs)
        output = self.llm.invoke([
            ("system", GENERATION_SYSTEM_PROMPT),
            ("human", prompt),
        ])
        if isinstance(output, dict):
            output = GenerationOutput.model_validate(output)
        by_tier = {candidate.tier: candidate for candidate in output.candidates}
        required = ("strong", "balanced", "safe")
        if set(by_tier) != set(required):
            raise ValueError("생성 결과에는 strong, balanced, safe 후보가 각각 하나씩 필요합니다.")
        return [by_tier[tier].model_dump() for tier in required]
