from unittest.mock import Mock

import pytest

from cosmetic_agent.domain.chat import ChatContext, ChatRequest
from cosmetic_agent.domain.generation import GeneratedCandidate, GenerateResponse
from cosmetic_agent.domain.schemas import ExecutionTiming, ReviewResponse, ReviewResult
from cosmetic_agent.models.chatbot import ChatPlan, ChatService
from cosmetic_agent.models.copy_generator import GenerationUnavailable


def service(plan):
    reviewer, generator, llm = Mock(), Mock(), Mock()
    llm.invoke.return_value = plan
    return ChatService(reviewer, generator, llm)


def reviewed(text="판테놀 함유 크림"):
    return ReviewResponse(request_id="chat-test", input_text=text,
                          result=ReviewResult(status="판정", level=0, suggestion="판테놀을 담은 크림"),
                          timing=ExecutionTiming())


def test_review_uses_extracted_copy_and_preserves_trusted_evidence(sample_product):
    svc = service(ChatPlan(intent="review", context=ChatContext(), copy_text="판테놀 함유 크림"))
    svc.reviewer.review_single.return_value = reviewed()
    response = svc.chat(ChatRequest(message="이 문구 고쳐줘: 판테놀 함유 크림", product=sample_product))
    assert response.intent == "review"
    text, product = svc.reviewer.review_single.call_args.args
    assert text == "판테놀 함유 크림"
    assert product == sample_product
    assert response.context.last_copies == ["판테놀을 담은 크림"]
    svc.generator.generate.assert_not_called()


def test_generate_uses_resolved_context_and_no_implicit_evidence():
    svc = service(ChatPlan(intent="generate", context=ChatContext(
        ingredients=["판테놀"], product_name="테스트 크림", tone="발랄한", channel="배너", brief="두 번째 문구처럼 짧게"), reference_index=2))
    svc.generator.generate.return_value = GenerateResponse(candidates=[
        GeneratedCandidate(text="판테놀 함유 크림", status="확인필요")])
    previous = ChatContext(ingredients=["판테놀"], product_name="테스트 크림", last_copies=["후보 하나", "후보 둘"])
    response = svc.chat(ChatRequest(message="2번 더 짧고 발랄하게", context=previous))
    request = svc.generator.generate.call_args.args[0]
    assert request.ingredients == ["판테놀"]
    assert request.tone == "발랄한" and request.channel == "배너"
    assert request.product.name == "테스트 크림"
    assert request.product.owned_evidence == []
    assert "두 번째" in request.brief
    assert request.reference_copy == "후보 둘"
    assert response.context.last_copies == ["판테놀 함유 크림"]
    assert "후보 둘" in svc._llm.invoke.call_args.args[0][1][1]
    svc.reviewer.review_single.assert_not_called()


@pytest.mark.parametrize("intent, question", [("generate", "성분"), ("review", "광고 문구")])
def test_missing_inputs_ask_question_without_running_tools(intent, question):
    svc = service(ChatPlan(intent=intent, context=ChatContext()))
    response = svc.chat(ChatRequest(message="해주세요"))
    assert response.intent == "clarify" and question in response.message
    svc.reviewer.review_single.assert_not_called()
    svc.generator.generate.assert_not_called()


def test_clarification_does_not_store_invented_model_candidates():
    svc = service(ChatPlan(intent="clarify", context=ChatContext(last_copies=["날조"]), question="어떤 후보를 고칠까요?"))
    response = svc.chat(ChatRequest(message="고쳐줘", context=ChatContext(last_copies=["실제 후보"])))
    assert response.context.last_copies == ["실제 후보"]


def test_parser_failure_does_not_run_tools():
    svc = service(None)
    svc._llm.invoke.side_effect = RuntimeError("offline")
    with pytest.raises(GenerationUnavailable, match="해석하지 못"):
        svc.chat(ChatRequest(message="광고 생성"))
    svc.generator.generate.assert_not_called()


def test_review_failure_is_reported():
    svc = service(ChatPlan(intent="review", context=ChatContext(), copy_text="본문"))
    svc.reviewer.review_single.side_effect = RuntimeError("offline")
    with pytest.raises(GenerationUnavailable, match="검토에 실패"):
        svc.chat(ChatRequest(message="검토해줘"))


def test_invalid_candidate_reference_asks_before_execution():
    svc = service(ChatPlan(intent="review", context=ChatContext(), reference_index=3))
    response = svc.chat(ChatRequest(message="3번 검토", context=ChatContext(last_copies=["실제 후보"])))
    assert response.intent == "clarify"
    svc.reviewer.review_single.assert_not_called()


def test_candidate_review_uses_actual_previous_text():
    svc = service(ChatPlan(intent="review", context=ChatContext(), copy_text="모델이 변경한 본문", reference_index=1))
    svc.reviewer.review_single.return_value = reviewed()
    svc.chat(ChatRequest(message="1번 검토", context=ChatContext(last_copies=["실제 후보"])))
    assert svc.reviewer.review_single.call_args.args[0] == "실제 후보"
