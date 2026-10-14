"""제안 문구 검증기 단위 테스트.

예시 문구는 법령·지침 원문의 표현을 바탕으로 새로 작성했으며 골든셋 문항을 쓰지 않는다.
"""
import pytest

from cosmetic_agent.domain.verifier import CopyVerifier

HUMAN_TEST = {"test_type": "인체적용시험", "item": "피부 보습 개선", "value": "8주 사용 후 수분량 35% 증가", "institute": "OO연구원"}
SURVEY = {"test_type": "소비자 조사", "item": "사용감 만족도", "value": "사용자 88% 만족", "institute": "OO리서치"}


@pytest.fixture(scope="module")
def verifier():
    return CopyVerifier()


def codes(verifier, text, evidences=(), **kwargs):
    return {issue.code for issue in verifier.inspect(text, list(evidences), **kwargs)}


def test_safe_general_copy_passes(verifier):
    passed, note = verifier.verify_suggestion("촉촉한 사용감으로 피부를 부드럽게 가꿔줍니다", [], None)
    assert passed, note


@pytest.mark.parametrize("text", [
    "피부 염증을 치료해 주는 크림",
    "세포 재생을 돕는 앰플",
    "혈액순환을 촉진하는 마사지 오일",
    "피부과 전용 진정 젤",
    "보톡스처럼 팽팽하게",
    "업계 최고의 보습 크림",
    "엑소좀 함유 세럼",
])
def test_forbidden_expressions_fail(verifier, text):
    assert "금지표현" in codes(verifier, text)


def test_plant_exosome_is_allowed(verifier):
    # 관리지침 별표1: 식물 등 인체 외에서 유래한 경우는 제외
    assert "금지표현" not in codes(verifier, "식물 엑소좀을 담은 토너")


def test_temporary_itch_relief_by_moisture_is_allowed(verifier):
    # 관리지침 별표1: 보습을 통한 건조 기인 가려움의 '일시적' 완화는 제외
    text = "보습으로 건조함에 의한 가려움을 일시적으로 덜어 줍니다"
    assert "금지표현" not in codes(verifier, text)
    assert "금지표현" in codes(verifier, "가려움을 말끔히 없애 줍니다")


def test_general_product_cannot_claim_functional_effect(verifier):
    assert "기능성오인" in codes(verifier, "칙칙한 피부 미백에 도움", product_category="일반")


def test_functional_product_within_and_outside_its_scope(verifier):
    kwargs = {"product_category": "기능성", "functional_type": "주름 개선"}
    assert not codes(verifier, "피부의 주름 개선에 도움을 줍니다", **kwargs)
    assert "범위이탈" in codes(verifier, "주름 개선과 미백을 한 번에", **kwargs)


def test_acne_wording_follows_functional_review(verifier):
    general = {"product_category": "일반"}
    functional = {"product_category": "기능성", "functional_type": "여드름성 피부 완화"}
    assert "금지표현" in codes(verifier, "여드름을 잡아주는 클렌저", **functional)
    assert not codes(verifier, "여드름성 피부 완화에 도움을 주는 바디워시", **functional)
    assert "기능성오인" in codes(verifier, "여드름성 피부 완화에 도움을 주는 바디워시", **general)


def test_substantiation_needs_matching_test_evidence(verifier):
    text = "피지 분비 조절에 도움을 주는 토너"
    assert "실증필요" in codes(verifier, text, [HUMAN_TEST])
    sebum = {"test_type": "인체적용시험", "item": "피지 분비량 변화", "value": "4주 후 감소"}
    assert "실증필요" not in codes(verifier, text, [sebum])


def test_survey_cannot_substantiate_efficacy(verifier):
    # 실증규정 제3조 제3항: 소비자 조사는 효능 주장의 직접 근거가 아니다
    survey_on_sebum = {"test_type": "소비자 조사", "item": "피지 조절 만족도", "value": "90% 만족"}
    assert "실증필요" in codes(verifier, "피지 분비 조절에 도움", [survey_on_sebum])


def test_numbers_must_come_from_owned_evidence(verifier):
    assert not codes(verifier, "8주 사용 후 수분량 35% 증가 (인체적용시험)", [HUMAN_TEST])
    assert "숫자날조" in codes(verifier, "8주 사용 후 수분량 50% 증가", [HUMAN_TEST])
    # '24주' 근거가 '4주' 주장을 뒷받침하지 않는다
    long_test = {"test_type": "인체적용시험", "item": "보습", "value": "24주 관찰"}
    assert "숫자날조" in codes(verifier, "4주 만에 촉촉", [long_test])


def test_survey_number_must_be_labeled_as_satisfaction(verifier):
    assert "조사결과오용" in codes(verifier, "피부결이 88% 좋아졌어요", [SURVEY])
    assert not codes(verifier, "사용자 88%가 사용감에 만족했어요 (외부 소비자 조사)", [SURVEY])


def test_unchanged_copy_fails_when_original_given(verifier):
    passed, note = verifier.verify_suggestion("피부 장벽 강화", [], None, original="피부 장벽 강화 ")
    assert not passed and "미수정" in note


def test_empty_suggestion_fails(verifier):
    assert verifier.verify_suggestion("  ", [], None)[0] is False


def test_banned_engine_hits_are_respected(verifier):
    class FakeEngine:
        def check_banned_terms(self, text, category):
            return 2, [{"term": "가짜", "basis_id": "TEST_ID"}]

    passed, note = verifier.verify_suggestion("촉촉한 크림", [], FakeEngine())
    assert not passed and "TEST_ID" in note


def test_in_house_survey_number_cannot_be_used(verifier):
    # 실증규정 제5조 1호: 조사기관은 사업자와 독립적이어야 한다
    in_house = {"test_type": "자사 설문", "item": "사용감 만족도", "value": "만족도 83%", "institute": "사내"}
    assert "조사결과오용" in codes(verifier, "사용감 만족도 83% (자사 조사)", [in_house])


def test_survey_number_must_stay_with_surveyed_item(verifier):
    survey = {"test_type": "소비자 조사", "item": "피부 탄력감 만족도", "value": "2주차 만족도 77%", "institute": "OO리서치"}
    kwargs = {"product_category": "기능성", "functional_type": "주름 개선"}
    assert "조사결과오용" in codes(verifier, "주름 개선에 도움, 만족도 77%", [survey], **kwargs)
    assert not codes(verifier, "주름 개선에 도움, 2주차 탄력감 만족도 77%", [survey], **kwargs)


def test_banned_engine_receives_functional_type(verifier):
    class FunctionalAwareEngine:
        def check_banned_terms(self, text, category, functional_type=None):
            # 심사받은 기능성 효능이면 금지어가 아니다
            if functional_type and "탈모" in functional_type:
                return 0, []
            return 2, [{"term": "탈모", "basis_id": "TEST_ID"}]

    kwargs = {"product_category": "기능성", "functional_type": "탈모 증상 완화"}
    passed, note = verifier.verify_suggestion("탈모 증상의 완화에 도움을 주는 샴푸", [], FunctionalAwareEngine(), **kwargs)
    assert passed, note


def test_reversed_word_order_and_sensitive_skin_claims_need_evidence(verifier):
    assert "실증필요" in codes(verifier, "손상된 모발을 부드럽게 가꿔요")
    assert "실증필요" in codes(verifier, "민감한 피부도 안심하고 쓰는 크림")
    patch = {"test_type": "인체적용시험", "item": "피부 자극 (첩포 시험)", "value": "무자극 판정"}
    assert "실증필요" not in codes(verifier, "민감한 피부도 안심하고 쓰는 크림", [patch])


def test_number_units_do_not_swallow_following_words(verifier):
    # '100 세럼'의 '세'는 나이 단위가 아니고, '4주차'는 4주로 본다
    assert "숫자날조" not in codes(verifier, "히알루론산 캡슐 100 세럼")
    weeks = {"test_type": "인체적용시험", "item": "보습", "value": "4주 사용 후 42% 개선"}
    assert not codes(verifier, "4주차 보습 42% 개선 (인체적용시험)", [weeks])


def test_ranking_badge_is_exclusive_claim(verifier):
    assert "금지표현" in codes(verifier, "판매랭킹 TOP.1")


def test_functional_product_cannot_promise_removal(verifier):
    # 미백 기능성은 '미백에 도움'까지. 기미가 사라진다는 소멸·즉효 표현은 심사 범위 밖
    kwargs = {"product_category": "기능성", "functional_type": "피부 미백"}
    assert "금지표현" in codes(verifier, "바르기만 해도 기미가 싹 사라지는 미백 앰플", **kwargs)
    assert not codes(verifier, "피부의 미백에 도움을 주는 앰플", **kwargs)
    assert "금지표현" in codes(verifier, "깊은 주름이 사라지는 세럼",
                              product_category="기능성", functional_type="주름 개선")


@pytest.mark.parametrize("name", [
    "비스-피이지/피피지-18/6다이메티콘",  # PEG/PPG 한글 표기의 '피지'
    "리놀레아미도프로필피지-다이모늄클로라이드포스페이트",
    "카복시메틸람노사이드",  # 화학명 속 '카복시'
    "하이드롤라이즈드콜라겐",  # 콜라겐 함유 사실
    "폴리글리세릴-3세틸에터",  # '3세'는 나이가 아님
    "인체중간엽줄기세포배양액",  # '인체중간엽'의 '체중'
])
def test_ingredient_names_do_not_trigger_claim_rules(verifier, name):
    # 식약처 원료사전 성분명 2,000개 대량 점검에서 찾은 오탐. 인체 유래 오인 판단은 따로 본다.
    issues = verifier.inspect(f"{name} 함유", [])
    if name.startswith("인체"):  # 진짜 인체 유래 성분은 보수적으로 거는 것이 맞다
        issues = [i for i in issues if "인체유래" not in i.basis_id]
    assert not issues, issues


def test_claims_still_caught_after_ingredient_exceptions(verifier):
    assert "실증필요" in codes(verifier, "피지 조절 효과로 보송한 피부")
    assert "실증필요" in codes(verifier, "콜라겐 생성을 촉진하는 크림")
    assert "금지표현" in codes(verifier, "카복시 테라피 효과를 집에서")
    assert "금지표현" in codes(verifier, "체중 감량을 돕는 바디 크림")
    assert "금지표현" in codes(verifier, "인체 줄기세포 엑소좀 앰플")
    assert not codes(verifier, "연어정소엑소좀 함유")  # 인체 외 유래를 밝힘
