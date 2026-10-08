"""
[domain/verifier.py]
LLM이 생성한 제안 문구의 숫자, 효능, 표현이 실제 보유 근거와 일치하는지 코드로 역검증하는 엔진.
"""
from typing import Any
import re


class CopyVerifier:
    """제안 문구 검증기"""

    def verify_suggestion(
        self,
        suggestion: str,
        owned_evidences: list[dict[str, Any]],
        banned_engine: Any,
    ) -> tuple[bool, str]:
        """제안 문구를 다각도로 검증합니다.

        1. 보유 근거에 없는 숫자(예: 87%, 4주)를 날조했는지 확인
        2. 제안 문구 자체에 금지어가 다시 포함되었는지 확인

        Returns:
            (is_valid, note)
        """
        # TODO (팀원 구현 영역):
        # 1. suggestion 내 숫자/퍼센트 정규식 추출
        # 2. owned_evidences의 value와 일치하는지 확인
        # 3. banned_engine.check_banned_terms 재검사
        return (True, "검증 통과")
