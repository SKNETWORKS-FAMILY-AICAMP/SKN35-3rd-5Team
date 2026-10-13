"""
[models/gpt_judge.py]
GPT Few-shot 기반의 판정 모델 (기준선 R1/R2).
"""
from typing import Any
from .base import BaseJudgeModel


class GPTJudgeModel(BaseJudgeModel):
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        self.model_name = model_name
        self.temperature = temperature
        # TODO (팀원 구현 영역):
        # ChatOpenAI with_structured_output 초기화

    def judge(
        self,
        copy_text: str,
        product_category: str,
        functional_type: str | None = None,
    ) -> dict[str, Any]:
        # TODO (팀원 구현 영역):
        # Few-shot 프롬프트 조립 후 정형 출력(Pydantic) 파싱
        return {
            "model_level": 0,
            "violation_type": "없음",
            "claim_type": "일반",
            "confidence": 0.9,
        }
