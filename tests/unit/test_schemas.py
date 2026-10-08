"""
[tests/unit/test_schemas.py]
Pydantic 결과 계약 검증 단위 테스트.
"""
import pytest
from cosmetic_agent.domain.schemas import ReviewResult, Citation


def test_conditional_result_requires_next_test():
    """조건부(1) 판정 시 next_test가 없으면 에러가 발생하는지 검증"""
    with pytest.raises(ValueError, match="next_test"):
        ReviewResult(
            status="판정",
            level=1,
            violation_type="소비자오인",
            citations=[
                Citation(
                    chunk_id="TEST_01",
                    source="규정",
                    article="1조",
                    authority=1,
                )
            ],
            next_test="",  # 비어있으므로 검증 실패해야 함
        )


def test_violation_result_requires_citations():
    """불가(2) 판정 시 근거 조항(citations)이 비어있으면 에러가 발생하는지 검증"""
    with pytest.raises(ValueError, match="citation"):
        ReviewResult(
            status="판정",
            level=2,
            violation_type="의약품오인",
            citations=[],  # 비어있으므로 검증 실패해야 함
        )
