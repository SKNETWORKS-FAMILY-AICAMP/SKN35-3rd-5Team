"""
[models/base.py]
판정 모델 추상 기반 클래스(Interface).
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseJudgeModel(ABC):
    @abstractmethod
    def judge(
        self,
        copy_text: str,
        product_category: str,
        functional_type: str | None = None,
    ) -> dict[str, Any]:
        """문구를 판정하여 판정 수준 및 위반 유형을 반환합니다.

        Returns:
            {
                "model_level": int (0: 가능, 1: 조건부, 2: 불가),
                "violation_type": str,
                "claim_type": str,
                "confidence": float
            }
        """
        pass
