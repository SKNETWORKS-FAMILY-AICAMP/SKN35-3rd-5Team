"""
[domain/rules.py]
금지 표현 사전 및 표현 사다리를 기반으로 한 결정론적(Deterministic) 규칙 매칭 엔진.
"""
from pathlib import Path
from typing import Any
import json
import re


class RuleEngine:
    def __init__(
        self,
        banned_terms_path: Path = Path("data/assets/banned_terms.json"),
        claim_ladder_path: Path = Path("data/assets/claim_ladder.json"),
        functional_claims_path: Path = Path("data/assets/functional_claims.json"),
    ):
        self.banned_terms = self._load_json(banned_terms_path)
        self.claim_ladder = self._load_json(claim_ladder_path)
        self.functional_claims = self._load_json(functional_claims_path)

    @staticmethod
    def _load_json(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def check_banned_terms(self, text: str, product_category: str) -> tuple[int, list[dict[str, Any]]]:
        """금지 표현 사전과 정규식 매칭하여 규칙 수준과 적발 항목을 반환합니다.

        Returns:
            (rule_level, hits)
            rule_level: 0 (적발 없음) 또는 2 (불가 표현 발견)
        """
        hits: list[dict[str, Any]] = []
        # TODO (팀원 구현 영역):
        # 1. self.banned_terms의 pattern 정규식을 text에 매칭
        # 2. product_category(일반/기능성)와 scope 대조
        # 3. 매칭된 경우 hits에 추가하고 level=2 반환
        return (0, hits)

    def get_ladder_ceiling(self, claim_keyword: str) -> dict[str, Any]:
        """표현 사다리에서 해당 키워드의 허용 단계별 요건을 조회합니다."""
        # TODO (팀원 구현 영역):
        return {}
