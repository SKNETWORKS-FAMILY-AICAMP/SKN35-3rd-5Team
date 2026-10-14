from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from cosmetic_agent.domain.generation import GenerateRequest
from cosmetic_agent.domain.schemas import ExecutionTiming, ReviewResponse, ReviewResult
from cosmetic_agent.models.copy_generator import (
    CopyGenerationService,
    GenerationUnavailable,
)


def request():
    return GenerateRequest(ingredients=["판테놀", " 글리세린 ", "판테놀"], product={
        "product_id": "P1", "name": "크림", "category": "일반", "owned_evidence": [],
    })


def reviewer(status="판정", level=0):
    service = Mock(spec=["review_single"])
    service.review_single.return_value = ReviewResponse(
        request_id="test", input_text="판테놀 함유 크림", result=ReviewResult(status=status, level=level),
        timing=ExecutionTiming(),
    )
    return service


def test_request_validation():
    assert request().ingredients == ["판테놀", "글리세린"]
    for ingredients in ([], [" "], ["가" * 101], ["가"] * 101):
        with pytest.raises(ValidationError):
            GenerateRequest(ingredients=ingredients, product=request().product)


def test_no_substantiation_sent_and_each_unique_candidate_reviewed():
    llm = Mock()
    llm.invoke.return_value = {"candidates": ["판테놀 함유 크림", "글리세린을 담은 크림", "판테놀 함유 크림"]}
    service = reviewer()
    response = CopyGenerationService(service, llm).generate(request())
    assert [c.status for c in response.candidates] == ["검토통과", "검토통과"]
    assert service.review_single.call_count == 2
    prompt = llm.invoke.call_args.args[0]
    assert '"owned_evidence": []' in prompt[1][1]
    assert '"ingredients": ["판테놀", "글리세린"]' in prompt[1][1]


@pytest.mark.parametrize("text", ["아토피 치료 크림", "4주 만에 보습력 42% 개선", "피부 미백 크림"])
def test_unsafe_draft_excluded_before_review(text):
    llm = Mock()
    llm.invoke.return_value = {"candidates": [text]}
    service = reviewer()
    response = CopyGenerationService(service, llm).generate(request())
    assert response.candidates[0].status == "제외"
    assert response.candidates[0].notes
    service.review_single.assert_not_called()


def test_deferred_review_never_marked_passed():
    llm = Mock()
    llm.invoke.return_value = {"candidates": ["판테놀 함유 크림"]}
    response = CopyGenerationService(reviewer("판단보류", None), llm).generate(request())
    assert response.candidates[0].status == "확인필요"
    assert "검토를 통과한 문구가 없습니다" in response.warnings[-1]


def test_review_failure_preserves_draft_without_approval():
    llm = Mock()
    llm.invoke.return_value = {"candidates": ["판테놀 함유 크림"]}
    service = reviewer()
    service.review_single.side_effect = RuntimeError("offline")
    response = CopyGenerationService(service, llm).generate(request())
    assert response.candidates[0].status == "확인필요"


def test_model_failure_does_not_fabricate_fallback():
    llm = Mock()
    llm.invoke.side_effect = RuntimeError("secret upstream detail")
    with pytest.raises(GenerationUnavailable, match="AI 문구 생성에 실패") as error:
        CopyGenerationService(reviewer(), llm).generate(request())
    assert "secret" not in str(error.value)


def test_attention_style_retains_verification_and_adds_creative_direction():
    llm = Mock()
    llm.invoke.return_value = {"candidates": ["오늘 루틴의 주인공은? 판테놀 함유 크림.", "주름을 지우는 기적의 크림"]}
    req = request().model_copy(update={"tone": "눈길 끄는"})
    service = reviewer()
    response = CopyGenerationService(service, llm).generate(req)
    assert response.candidates[0].status == "검토통과"
    assert response.candidates[1].status == "제외"
    service.review_single.assert_called_once()
    system = llm.invoke.call_args.args[0][0][1]
    assert "질문형 도입" in system
    assert "모르는 성분의 효과를 추측하지 않는다" in system


@pytest.mark.parametrize("text", [
    "판테놀이 듬뿍 들어간 크림", "글리세린이 풍부한 크림",
    "피부에 깊이 스며드는 크림", "부드러운 수분을 선물하는 크림",
])
def test_attention_copy_does_not_invent_amount_or_sensory_facts(text):
    llm = Mock()
    llm.invoke.return_value = {"candidates": [text]}
    service = reviewer()
    response = CopyGenerationService(service, llm).generate(request())
    assert response.candidates[0].status == "제외"
    service.review_single.assert_not_called()
