"""
[models/rule_judge.py]
규칙 사전만을 활용하는 베이스라인 판정 모델 (R0).
"""
from typing import Any
from .base import BaseJudgeModel
from ..domain.rules import RuleEngine


class RuleJudgeModel(BaseJudgeModel):
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def judge(
        self,
        copy_text: str,
        product_category: str,
        functional_type: str | None = None,
    ) -> dict[str, Any]:
        level, hits = self.rule_engine.check_banned_terms(copy_text, product_category)
        violation_type = hits[0].get("type", "없음") if hits else "없음"
        return {
            "model_level": level,
            "violation_type": violation_type,
            "claim_type": "일반",
            "confidence": 1.0,
        }
