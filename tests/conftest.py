"""
[tests/conftest.py]
Pytest 공통 픽스처 (가짜 모델, 샘플 제품 데이터 등).
"""
import pytest
from cosmetic_agent.domain.schemas import ProductCard, OwnedEvidence


@pytest.fixture
def sample_product() -> ProductCard:
    return ProductCard(
        product_id="PROD_TEST_001",
        name="테스트 수분 크림",
        category="일반",
        owned_evidence=[
            OwnedEvidence(
                test_type="인체적용시험",
                item="보습 개선",
                value="4주 40% 개선",
                institute="시험원",
            )
        ],
    )
