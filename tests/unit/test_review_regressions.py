"""독립 검증(규칙 감사·레드팀)에서 찾은 오탐·미탐 회귀 테스트. 문장은 감사용으로 새로 쓴 것이며 골든셋 문항이 아니다."""
import pytest

from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.verifier import CopyVerifier

GENERAL = {"category": "일반", "functional_type": None, "owned_evidence": []}


@pytest.fixture(scope="module")
def engine():
    return RuleEngine()


@pytest.fixture(scope="module")
def verifier():
    return CopyVerifier()


def passes(verifier, engine, text, product=GENERAL):
    return verifier.verify_suggestion(text, product.get("owned_evidence", []), engine,
                                      product_category=product["category"],
                                      functional_type=product.get("functional_type"))[0]


@pytest.mark.parametrize("ftype, text", [
    ("피부장벽 기능 회복(가려움 개선)", "피부장벽의 기능을 회복하여 가려움 등의 개선에 도움을 줍니다"),
    ("튼살 붉은 선 완화", "튼살로 인한 붉은 선을 엷게 하는 데 도움을 줍니다"),
])
def test_new_functional_types_can_use_their_own_review_wording(verifier, engine, ftype, text):
    product = {"category": "기능성", "functional_type": ftype, "owned_evidence": []}
    assert engine.evaluate(text, product)["level"] == 0
    assert passes(verifier, engine, text, product)


@pytest.mark.parametrize("text", [
    "각질 내 수분을 채워 촉촉하게", "사용 시 주의사항을 꼭 확인하세요", "제약사 기술력으로 만든 크림",
    "하루 2회 사용하세요", "10분 후 헹궈내세요", "구매 후 30일 이내 환불", "판테놀 5% 함유",
    "브랜드의 DNA를 담은 크림", "얼굴 윤곽을 또렷하게 표현하는 하이라이터", "피지와 노폐물을 깨끗이 씻어내는 폼",
    "영양모발 케어 트리트먼트", "효과 감소 염려 없는 제형", "출근템으로 딱, 찐 촉촉함",
])
def test_ordinary_words_are_not_false_positives(verifier, engine, text):
    assert passes(verifier, engine, text)


@pytest.mark.parametrize("text", [
    "투명한 성분, 확실한 주름 개선", "눈가 주름이 확연히 줄어듭니다", "펌핑 한 번으로 되찾는 탄력",
    "피부톤 걱정 끝", "탈모가 걱정된다면? 이 샴푸가 답입니다", "3초 만에 촉촉", "이건 진짜 인생템",
])
def test_exaggeration_and_restoration_are_blocked(verifier, engine, text):
    assert not passes(verifier, engine, text)


def test_general_product_cannot_claim_collagen_increase_even_with_in_vitro_data(verifier, engine):
    product = {"category": "일반", "functional_type": None, "owned_evidence": [
        {"test_type": "인체외시험", "item": "콜라겐 생성", "value": "섬유아세포 콜라겐 생성 18% 증가 (in vitro)"}]}
    assert not passes(verifier, engine, "인체외시험 콜라겐 생성 18% 증가! 탄탄한 피부의 시작.", product)
