"""
[models/ft_judge.py]
QLoRA로 파인튜닝된 경량 LLM(Qwen 계열) 어댑터 서빙 모델 (R3/R4).
"""
from pathlib import Path
from typing import Any
from .base import BaseJudgeModel


class FineTunedJudgeModel(BaseJudgeModel):
    def __init__(self, adapter_path: Path):
        self.adapter_path = adapter_path
        # TODO (팀원 구현 영역):
        # 4bit QLoRA 모델 및 토크나이저 로드

    def judge(
        self,
        copy_text: str,
        product_category: str,
        functional_type: str | None = None,
    ) -> dict[str, Any]:
        # TODO (팀원 구현 영역):
        # 파인튜닝 프롬프트 인퍼런스 및 결과 파싱
        return {
            "model_level": 0,
            "violation_type": "없음",
            "claim_type": "일반",
            "confidence": 0.95,
        }
