"""
[models/rule_judge.py]
규칙 사전만을 활용하는 베이스라인 판정 모델 (R0).
LLM 호출 없이 금지 표현(2) / 실증·수치·비교(1) / 없음(0)을 판정합니다.
"""
from typing import Any

from ..domain.rules import RuleEngine
from .base import BaseJudgeModel


class RuleJudgeModel(BaseJudgeModel):
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def judge(
        self,
        copy_text: str,
        product_category: str,
        functional_type: str | None = None,
        owned_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.judge_product(copy_text, {
            "category": product_category,
            "functional_type": functional_type,
            "owned_evidence": owned_evidence or [],
        })

    def judge_product(self, copy_text: str, product: dict[str, Any]) -> dict[str, Any]:
        """보유 근거(owned_evidence)까지 보고 판정합니다. 워크플로·평가는 이 진입점을 씁니다."""
        report = self.rule_engine.evaluate(copy_text, product)
        matched = ", ".join(f"'{h['matched']}'({h['type']})" for h in report["hits"]) or "없음"
        return {
            "model_level": report["level"],
            "violation_type": report["violation_type"],
            "claim_type": report["claim_type"],
            # 규칙은 결정론적이지만 '못 잡은 것'을 보장하지 않으므로 적발 없음(0)은 낮게 둔다
            "confidence": 1.0 if report["hits"] else 0.5,
            "rationale": f"규칙 매칭: {matched}",
            "basis_ids": report["basis_ids"],
            "next_test": report["next_test"],
            "rule_hits": report["hits"],
        }
