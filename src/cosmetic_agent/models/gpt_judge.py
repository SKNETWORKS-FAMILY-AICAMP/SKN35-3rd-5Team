"""
[models/gpt_judge.py]
GPT 기반 사전 판정 모델 (R1 zero-shot / R2 few-shot). 최종 판정은 RAG 근거와 함께 워크플로에서 확정한다.

- with_structured_output(JudgeOutput)으로 출력 형식을 강제한다.
- 프롬프트는 models/judge_prompts.py 에 있다.
- 호출·파싱 실패는 그대로 예외로 올린다. 실패를 '가능(0)'으로 꾸며 통과시키지 않는다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..common.config import settings
from .base import BaseJudgeModel
from .judge_prompts import (
    JUDGE_PROMPT_VERSION_FEW,
    JUDGE_PROMPT_VERSION_ZERO,
    JUDGE_SYSTEM_PROMPT,  # noqa: F401  (하위 호환: 기존 import 경로 유지)
    build_judge_messages,
)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_level: Literal[0, 1, 2]
    violation_type: Literal["의약품오인", "범위이탈", "기능성오인", "실증필요", "비교광고", "소비자오인", "없음"]
    claim_type: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_label(self) -> JudgeOutput:
        if (self.model_level == 0) != (self.violation_type == "없음"):
            raise ValueError("level and violation_type are inconsistent")
        return self


class GPTJudgeModel(BaseJudgeModel):
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        *,
        llm: Any = None,
        few_shot: bool = False,
    ):
        """
        Args:
            few_shot: False 면 R1(zero-shot), True 면 R2(few-shot)
            llm: 테스트용 주입. None 이면 첫 호출 때 ChatOpenAI 를 만든다.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.few_shot = few_shot
        self._llm = llm

    @property
    def prompt_version(self) -> str:
        return JUDGE_PROMPT_VERSION_FEW if self.few_shot else JUDGE_PROMPT_VERSION_ZERO

    @property
    def llm(self) -> Any:
        if self._llm is None:
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("your_"):
                raise ValueError("OPENAI_API_KEY is not configured in .env")
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model_name, temperature=self.temperature,
                api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL,
                timeout=30, max_retries=1,
            ).with_structured_output(JudgeOutput, method="json_schema")
        return self._llm

    def judge(self, copy_text: str, product_category: str, functional_type: str | None = None) -> dict[str, Any]:
        return self.judge_product(copy_text, {
            "category": product_category, "functional_type": functional_type, "owned_evidence": [],
        })

    def judge_product(self, copy_text: str, product: dict[str, Any]) -> dict[str, Any]:
        # 허용 필드만 보낸다 (평가 라벨·메모는 모델에 가지 않음)
        output = self.llm.invoke(build_judge_messages(copy_text, product, few_shot=self.few_shot))
        # API/파싱 실패는 예외로 올라간다. 성공한 0을 지어내지 않는다.
        result = JudgeOutput.model_validate(output).model_dump()
        result["prompt_version"] = self.prompt_version
        return result
