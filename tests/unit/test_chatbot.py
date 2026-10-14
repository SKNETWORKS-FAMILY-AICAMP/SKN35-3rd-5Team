from unittest.mock import Mock

import pytest

from cosmetic_agent.domain.chat import ChatContext, ChatRequest
from cosmetic_agent.domain.schemas import (
    ExecutionTiming,
    GeneratedCandidate,
    GenerateResponse,
    ReviewResponse,
    ReviewResult,
)
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
    svc.generator.generate.return_value = GenerateResponse(request_id="test", status="생성완료", product_id="P1", timing=ExecutionTiming(), candidates=[
        GeneratedCandidate(text="판테놀 함유 크림", tier="safe", status="확인필요")])
    previous = ChatContext(ingredients=["판테놀"], product_name="테스트 크림", last_copies=["후보 하나", "후보 둘"])
    response = svc.chat(ChatRequest(message="2번 더 짧고 발랄하게", context=previous))
    request = svc.generator.generate.call_args.args[0]
    assert request.ingredients == ["판테놀"]
    assert request.tone == "발랄한" and request.channel == "배너"
    assert request.product.name == "테스트 크림"
    assert request.product.owned_evidence == []
    assert "두 번째" in request.instruction
    assert request.reference_copy == "후보 둘"
    assert response.context.last_copies == ["판테놀 함유 크림"]
    assert "후보 둘" in svc._llm.invoke.call_args.args[0][1][1]
    svc.reviewer.review_single.assert_not_called()


def test_review_without_text_asks_for_required_input():
    svc = service(ChatPlan(intent="review", context=ChatContext()))
    response = svc.chat(ChatRequest(message="해주세요"))
    assert response.intent == "clarify" and "광고 문구" in response.message
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


@pytest.mark.parametrize("intent, question", [("generate", ""), ("clarify", "성분이 무엇인가요?")])
def test_sunscreen_request_generates_without_asking_for_ingredients(intent, question):
    svc = service(ChatPlan(intent=intent, question=question, context=ChatContext(
        product_name="선크림", product_description="자외선 차단 선크림 광고")))
    svc.generator.generate.return_value = GenerateResponse(
        request_id="sunscreen", status="생성완료", product_id="chat_draft", timing=ExecutionTiming(),
        candidates=[GeneratedCandidate(text="햇살 있는 하루, 외출 준비의 선케어 루틴.", tier="safe")])
    response = svc.chat(ChatRequest(message="자외선 차단하는 선크림 관련해서 만들어줘봐"))
    assert response.intent == "generate"
    sent = svc.generator.generate.call_args.args[0]
    assert sent.ingredients == [] and sent.product.owned_evidence == []
    assert sent.product.category == "일반" and sent.product.functional_type is None
    assert "선크림" in sent.instruction
    assert response.generation.candidates


def test_short_followup_defaults_to_first_candidate_without_clarification():
    svc = service(ChatPlan(intent="generate", context=ChatContext(tone="유머러스한", length="한 줄")))
    svc.generator.generate.return_value = GenerateResponse(
        request_id="followup", status="생성완료", product_id="chat_draft", timing=ExecutionTiming())
    svc.chat(ChatRequest(message="더 짧고 웃기게", context=ChatContext(last_copies=["이전 후보", "다른 후보"])))
    sent = svc.generator.generate.call_args.args[0]
    assert sent.reference_copy == "이전 후보" and sent.tone == "유머러스한" and sent.length == "한 줄"


def test_capability_conversation_does_not_treat_it_as_ad_review():
    svc = service(ChatPlan(intent="answer", context=ChatContext(), question="성분을 몰라도 제품 설명만으로 광고 초안을 만들 수 있어요."))
    response = svc.chat(ChatRequest(message="성분 몰라도 되지?"))
    assert response.intent == "answer"
    svc.generator.generate.assert_not_called()
    svc.reviewer.review_single.assert_not_called()


def test_new_topic_with_same_placeholder_name_does_not_reuse_old_copy():
    svc = service(ChatPlan(intent="generate", new_topic=True, reference_index=1,
                           context=ChatContext(brief="립밤의 브랜드 소개", product_description="립밤")))
    svc.generator.generate.return_value = GenerateResponse(
        request_id="new", status="생성완료", product_id="chat_draft", timing=ExecutionTiming())
    old = ChatContext(ingredients=["판테놀"], product_description="선크림", brief="20대 선크림 SNS 광고", last_copies=["이전 선크림 광고"])
    svc.chat(ChatRequest(message="이번엔 립밤 소개 글을 써줘", context=old))
    sent = svc.generator.generate.call_args.args[0]
    assert sent.reference_copy == ""
    assert sent.ingredients == []
    assert sent.product_description == "립밤"
    assert "선크림" not in sent.instruction


def test_new_topic_then_followup_works_without_resetting_conversation():
    svc = service(None)
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="generate", new_topic=True, context=ChatContext(product_name="선크림", product_description="선크림")),
        ChatPlan(intent="generate", new_topic=True, context=ChatContext(product_name="립밤", product_description="립밤")),
        ChatPlan(intent="generate", context=ChatContext(product_name="립밤", product_description="립밤", length="한 줄")),
    ]
    svc.generator.generate.side_effect = [
        GenerateResponse(request_id=str(i), status="생성완료", product_id="chat_draft", timing=ExecutionTiming(),
                         candidates=[GeneratedCandidate(text=text, tier="safe")])
        for i, text in enumerate(["선케어 루틴", "립밤 루틴", "짧은 립밤 루틴"])
    ]
    first = svc.chat(ChatRequest(message="선크림 광고 써줘"))
    second = svc.chat(ChatRequest(message="이번엔 립밤 광고 써줘", context=first.context))
    svc.chat(ChatRequest(message="방금 걸 더 짧게", context=second.context))
    sent = [call.args[0] for call in svc.generator.generate.call_args_list]
    assert sent[1].reference_copy == ""
    assert sent[2].reference_copy == "립밤 루틴"


def test_new_product_and_followup_do_not_reuse_selected_product_evidence(sample_product):
    svc = service(None)
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="generate", new_topic=True, context=ChatContext(product_name="립밤", product_description="립밤")),
        ChatPlan(intent="generate", context=ChatContext(product_name="립밤", product_description="립밤", tone="재치 있는")),
    ]
    svc.generator.generate.return_value = GenerateResponse(
        request_id="lip", status="생성완료", product_id="chat_draft", timing=ExecutionTiming(),
        candidates=[GeneratedCandidate(text="립밤 루틴", tier="safe")])
    result = svc.chat(ChatRequest(message="이번에는 립밤 광고 써줘", product=sample_product))
    assert result.context.product_source == "conversation"
    svc.chat(ChatRequest(message="방금 걸 재치 있게", product=sample_product, context=result.context))
    for call in svc.generator.generate.call_args_list:
        assert call.args[0].product.name == "립밤"
        assert call.args[0].product.owned_evidence == []
        assert call.args[0].product.functional_type is None
