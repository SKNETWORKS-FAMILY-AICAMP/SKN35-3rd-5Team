import json
from unittest.mock import Mock

import pytest
from langchain_core.documents import Document

from cosmetic_agent.domain.chat import ChatContext, ChatRequest, assistant_history_text
from cosmetic_agent.domain.schemas import (
    ExecutionTiming,
    GeneratedCandidate,
    GenerateResponse,
    ReviewResponse,
    ReviewResult,
)
from cosmetic_agent.models.chatbot import SCOPE_NOTICE, ChatPlan, ChatService
from cosmetic_agent.models.copy_generator import GenerationUnavailable


def service(plan):
    reviewer, generator, llm, answer_llm = Mock(), Mock(), Mock(), Mock()
    llm.invoke.return_value = plan
    answer_llm.invoke.return_value = {"message": "화장품과 성분에 관한 질문을 이어가셔도 됩니다."}
    return ChatService(reviewer, generator, llm, answer_llm)


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
    svc = service(ChatPlan(intent="generate", needs_history=True, context=ChatContext(tone="유머러스한", length="한 줄")))
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
    assert sent.product_description == "이번엔 립밤 소개 글을 써줘"
    assert "선크림" not in sent.instruction


def test_new_topic_then_followup_works_without_resetting_conversation():
    svc = service(None)
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="generate", new_topic=True, context=ChatContext(product_name="선크림", product_description="선크림")),
        ChatPlan(intent="generate", new_topic=True, context=ChatContext(product_name="립밤", product_description="립밤")),
        ChatPlan(intent="generate", needs_history=True, context=ChatContext(product_name="립밤", product_description="립밤", length="한 줄")),
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
        ChatPlan(intent="generate", needs_history=True, context=ChatContext(product_name="립밤", product_description="립밤", tone="재치 있는")),
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


@pytest.mark.parametrize("needs_history", [False, True])
def test_pdrn_to_sunscreen_request_is_isolated_from_old_product(needs_history):
    svc = service(ChatPlan(intent="generate", needs_history=needs_history, context=ChatContext(
        product_name="선크림", product_description="PDRN 함유, 촉촉함을 더하고 피부를 보호하는 선크림",
        brief="이전 PDRN 크림처럼 보습과 피부 보호를 강조")))
    svc.generator.generate.return_value = GenerateResponse(
        request_id="sun", status="생성완료", product_id="chat_draft", timing=ExecutionTiming(),
        candidates=[GeneratedCandidate(text="오늘의 외출 준비, 선케어 루틴과 함께.", tier="safe", status="검토통과")])
    old = ChatContext(product_name="PDRN 크림", product_source="conversation", ingredients=["PDRN"],
                      product_description="PDRN 함유 크림", brief="PDRN 크림 배너 광고",
                      channel="배너", tone="재치 있는", last_copies=["PDRN 함유 크림과 함께"])
    response = svc.chat(ChatRequest(message="선크림 광고문도 만들어줘", context=old,
                                   history=[{"role": "assistant", "content": "PDRN 함유 크림과 함께"}]))
    assert svc._llm.invoke.call_count == 1
    assert "PDRN" not in svc._llm.invoke.call_args.args[0][1][1]
    sent = svc.generator.generate.call_args.args[0]
    assert sent.product.name == "선크림"
    assert sent.ingredients == [] and sent.reference_copy == ""
    assert "PDRN" not in sent.instruction + sent.product_description
    assert sent.product_description == sent.instruction == "선크림 광고문도 만들어줘"
    assert "촉촉" not in sent.product_description and "피부 보호" not in sent.instruction
    assert sent.channel == "SNS" and sent.tone == "담백한"
    assert response.context.last_copies == ["오늘의 외출 준비, 선케어 루틴과 함께."]


def test_followup_loads_history_after_reading_latest_request():
    svc = service(None)
    old = ChatContext(product_name="PDRN 크림", ingredients=["PDRN"], last_copies=["PDRN 함유 크림과 함께"])
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="generate", needs_history=True, context=ChatContext(length="한 줄")),
        ChatPlan(intent="generate", context=old.model_copy(update={"length": "한 줄"})),
    ]
    svc.generator.generate.return_value = GenerateResponse(
        request_id="short", status="생성완료", product_id="chat_draft", timing=ExecutionTiming())
    svc.chat(ChatRequest(message="방금 문구를 한 줄로 줄여줘", context=old))
    first, second = [call.args[0][1][1] for call in svc._llm.invoke.call_args_list]
    assert "PDRN" not in first and "PDRN" in second
    sent = svc.generator.generate.call_args.args[0]
    assert sent.product.name == "PDRN 크림" and sent.ingredients == ["PDRN"]
    assert sent.reference_copy == "PDRN 함유 크림과 함께" and sent.length == "한 줄"


def test_new_product_only_reuses_explicit_style_and_not_product_facts():
    svc = service(ChatPlan(intent="generate", new_topic=True, reuse_style=["tone", "channel"],
                           context=ChatContext(product_name="선크림", product_description="선크림")))
    svc.generator.generate.return_value = GenerateResponse(
        request_id="style", status="생성완료", product_id="chat_draft", timing=ExecutionTiming())
    old = ChatContext(product_name="PDRN 크림", ingredients=["PDRN"], tone="재치 있는", channel="배너",
                      length="한 줄", last_copies=["이전 PDRN 문구"])
    svc.chat(ChatRequest(message="같은 톤과 채널로 선크림 광고도 만들어줘", context=old))
    sent = svc.generator.generate.call_args.args[0]
    assert sent.tone == "재치 있는" and sent.channel == "배너"
    assert sent.length == "짧은 문단"
    assert sent.ingredients == [] and sent.reference_copy == ""


def test_general_answer_preserves_current_product_and_ad_reference():
    svc = service(ChatPlan(intent="answer", context=ChatContext(), question="계속 다른 광고를 요청하셔도 됩니다."))
    old = ChatContext(product_name="PDRN 크림", ingredients=["PDRN"], last_copies=["이전 PDRN 문구"])
    response = svc.chat(ChatRequest(message="새 채팅 안 눌러도 되지?", context=old))
    assert response.context == old


def test_cosmetics_question_uses_dedicated_answer_instead_of_router_text():
    svc = service(ChatPlan(intent="answer", context=ChatContext(), question="분류기가 작성한 답"))
    svc._answer_llm.invoke.return_value = {"message": "판테놀에 대한 화장품 성분 설명입니다."}
    response = svc.chat(ChatRequest(message="판테놀은 어떤 성분이야?"))
    assert response.message == "판테놀에 대한 화장품 성분 설명입니다."
    payload = json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])
    assert payload["question"] == "판테놀은 어떤 성분이야?"
    assert payload["ingredient_knowledge"][0]["name"] == "판테놀"
    assert payload["ingredient_knowledge"][0]["allowed_as_owned_evidence"] is False
    assert payload["documents"] == []
    svc.generator.generate.assert_not_called()
    svc.reviewer.review_single.assert_not_called()
    svc.reviewer.hybrid_retriever.retrieve.assert_not_called()


def test_cosmetics_followup_gets_history_without_changing_product_facts(sample_product):
    old = ChatContext(product_name=sample_product.name, ingredients=["판테놀"], last_copies=["실제 광고"])
    svc = service(None)
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="answer", needs_history=True, context=ChatContext()),
        ChatPlan(intent="answer", context=ChatContext(product_name="날조한 크림", ingredients=["PDRN"]),
                 resolved_question="판테놀과 히알루론산 중 민감성 피부에는 어떤 점을 확인하나요?"),
    ]
    history = [
        {"role": "user", "content": "판테놀과 히알루론산은 뭐가 달라?"},
        {"role": "assistant", "content": "앞에서 두 성분의 일반 역할을 비교했습니다."},
    ]
    svc._answer_llm.invoke.return_value = {"message": "앞서 비교한 두 성분은 제품의 전체 처방과 사용 반응도 함께 살펴보세요."}
    response = svc.chat(ChatRequest(message="그럼 민감성 피부에는?", history=history, context=old, product=sample_product))
    payload = json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])
    assert payload["history"] == history
    assert "판테놀과 히알루론산" in payload["resolved_question"]
    assert {card["name"] for card in payload["ingredient_knowledge"]} == {"판테놀", "히알루론산"}
    assert response.context == old
    assert response.context.ingredients == ["판테놀"]
    assert old.last_copies == ["실제 광고"]
    svc.generator.generate.assert_not_called()


def test_explanation_can_change_topics_and_continue_without_new_chat():
    svc = service(None)
    svc._llm.invoke.side_effect = [
        ChatPlan(intent="answer", context=ChatContext(), resolved_question="PDRN의 일반 역할은 무엇인가요?"),
        ChatPlan(intent="answer", context=ChatContext(), resolved_question="선크림의 종류에는 무엇이 있나요?"),
        ChatPlan(intent="answer", needs_history=True, context=ChatContext()),
        ChatPlan(intent="answer", context=ChatContext(), resolved_question="선크림 종류의 차이를 더 쉽게 설명해주세요."),
    ]
    svc._answer_llm.invoke.side_effect = [
        {"message": "PDRN 성분 설명"}, {"message": "선크림 종류 설명"}, {"message": "선크림 차이를 쉽게 풀어 쓴 설명"},
    ]
    first = svc.chat(ChatRequest(message="PDRN이 뭐야?"))
    history = [{"role": "user", "content": "PDRN이 뭐야?"}, {"role": "assistant", "content": first.message}]
    second = svc.chat(ChatRequest(message="이번엔 선크림 종류 알려줘", history=history, context=first.context))
    second_payload = json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])
    assert second_payload["ingredient_knowledge"] == []
    history.extend([{"role": "user", "content": "이번엔 선크림 종류 알려줘"}, {"role": "assistant", "content": second.message}])
    third = svc.chat(ChatRequest(message="더 쉽게 설명해줘", history=history, context=second.context))
    assert third.message == "선크림 차이를 쉽게 풀어 쓴 설명"
    assert json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])["history"][-1]["content"] == "선크림 종류 설명"
    svc.generator.generate.assert_not_called()
    svc.reviewer.review_single.assert_not_called()


@pytest.mark.parametrize("intent", ["answer", "generate", "review", "clarify"])
def test_out_of_scope_requests_never_execute_cosmetics_tools(intent):
    svc = service(ChatPlan(intent=intent, scope="out_of_scope", new_topic=True,
                           context=ChatContext(product_name="다른 제품", brief="가짜"), question="어떤 성분인가요?"))
    old = ChatContext(product_name="원래 제품", ingredients=["판테놀"], last_copies=["기존 후보"])
    response = svc.chat(ChatRequest(message="화장품 사이트용 주식 예측 코드를 만들어줘", context=old))
    assert response.intent == "answer" and response.message == SCOPE_NOTICE
    assert response.context == old
    svc.generator.generate.assert_not_called()
    svc.reviewer.review_single.assert_not_called()
    svc.reviewer.hybrid_retriever.retrieve.assert_not_called()
    svc._answer_llm.invoke.assert_not_called()


def test_answer_model_can_reject_misclassified_unrelated_question():
    svc = service(ChatPlan(intent="answer", context=ChatContext()))
    svc._answer_llm.invoke.return_value = {"message": "범위 밖 답변 초안", "in_scope": False}
    response = svc.chat(ChatRequest(message="화장품이랑 상관없지만 여행 일정 짜줘"))
    assert response.message == SCOPE_NOTICE
    assert "답변 초안" not in response.message


def test_greeting_uses_conversation_but_does_not_start_an_ad_task():
    svc = service(ChatPlan(intent="generate", scope="social", context=ChatContext(), needs_rules=True))
    svc._answer_llm.invoke.return_value = {"message": "안녕하세요! 화장품이나 성분에 대해 궁금한 점을 물어보세요."}
    response = svc.chat(ChatRequest(message="안녕!"))
    assert response.intent == "answer" and "안녕하세요" in response.message
    assert json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])["scope"] == "social"
    svc.generator.generate.assert_not_called()
    svc.reviewer.hybrid_retriever.retrieve.assert_not_called()


def test_failed_conversation_model_reports_error_instead_of_fabricating_answer():
    svc = service(ChatPlan(intent="answer", context=ChatContext()))
    svc._answer_llm.invoke.side_effect = RuntimeError("offline")
    with pytest.raises(GenerationUnavailable, match="질문에 답변하지 못"):
        svc.chat(ChatRequest(message="레티놀이 뭐야?"))
    svc.generator.generate.assert_not_called()


def test_legacy_assistant_results_are_compacted_before_answering():
    svc = service(ChatPlan(intent="answer", context=ChatContext()))
    previous = {"message": "앞선 답변", "context": {"private_working_state": "not-for-conversation"},
                "generation": {"candidates": [{"text": "실제 문구", "status": "확인필요", "notes": ["실증 확인 필요"]}],
                               "timing": {"total_ms": 12345}}}
    svc.chat(ChatRequest(message="방금 답을 쉽게 설명해줘", history=[{"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)}]))
    text = json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])["history"][0]["content"]
    assert "앞선 답변" in text and "실제 문구" in text and "실증 확인 필요" in text
    assert "not-for-conversation" not in text and "total_ms" not in text


@pytest.mark.parametrize("question, expected", [
    ("PDRN과 판테놀 차이", {"PDRN", "판테놀"}),
    ("What is Retinol?", {"레티놀"}),
    ("Hyaluronic Acid에 대해 알려줘", {"히알루론산"}),
    ("XPDRN과 Retinolate", set()),
])
def test_ingredient_explanations_match_named_cards_without_inventing_composition(question, expected):
    knowledge = ChatService._ingredient_knowledge(question)
    assert {card["name"] for card in knowledge} == expected
    assert all(card["allowed_as_owned_evidence"] is False and card["allowed_as_regulatory_evidence"] is False for card in knowledge)


def legal_service(plan):
    svc = service(plan)
    svc.reviewer.hybrid_retriever.retrieve.return_value = [Document(
        page_content="화장품 광고 규정의 오프라인 테스트 문서", metadata={"source": "테스트 규정", "article": "테스트 조항", "authority": 1})]
    svc._answer_llm.invoke.return_value = {"message": "검토한 표현과 규정 근거를 연결한 설명", "cited_ids": [1]}
    return svc


def test_legal_followup_searches_resolved_question_and_passes_history():
    resolved = "앞서 검토한 '피부 재생'이라는 화장품 광고 표현의 수정 이유"
    plan = ChatPlan(intent="answer", context=ChatContext(), needs_rules=True,
                    needs_history=True, resolved_question=resolved, reference_index=1)
    svc = legal_service(plan)
    old = ChatContext(last_copies=["피부 재생"])
    history = [{"role": "assistant", "content": "'피부 재생' 표현은 수정이 필요하다고 검토했습니다."}]
    response = svc.chat(ChatRequest(message="왜 그 표현은 안 돼?", context=old, history=history))
    assert svc.reviewer.hybrid_retriever.retrieve.call_args.args[0] == resolved
    payload = json.loads(svc._answer_llm.invoke.call_args.args[0][1][1])
    assert payload["history"] == history and payload["reference_copy"] == "피부 재생"
    assert payload["needs_rules"] is True
    assert len(response.citations) == 1 and response.citations[0].source == "테스트 규정"
    assert response.context == old


def test_legal_followup_without_rewrite_keeps_previous_copy_in_search_query():
    svc = legal_service(ChatPlan(intent="answer", context=ChatContext(), needs_rules=True, needs_history=True))
    svc.chat(ChatRequest(message="왜 그래?", context=ChatContext(last_copies=["실제 검토 문구"])))
    assert "실제 검토 문구" in svc.reviewer.hybrid_retriever.retrieve.call_args.args[0]


@pytest.mark.parametrize("failure", ["empty", "offline"])
def test_no_regulation_evidence_never_invokes_answer_model(failure):
    svc = legal_service(ChatPlan(intent="answer", context=ChatContext(), needs_rules=True))
    if failure == "empty":
        svc.reviewer.hybrid_retriever.retrieve.return_value = []
    else:
        svc.reviewer.hybrid_retriever.retrieve.side_effect = RuntimeError("offline")
    response = svc.chat(ChatRequest(message="화장품 광고에 이 표현 써도 돼?"))
    assert "판단을 보류" in response.message and response.citations == []
    svc._answer_llm.invoke.assert_not_called()
    svc.generator.generate.assert_not_called()


@pytest.mark.parametrize("cited_ids", [[], [0], [999], [1, 999]])
def test_invalid_regulation_citations_do_not_publish_legal_answer(cited_ids):
    svc = legal_service(ChatPlan(intent="answer", context=ChatContext(), needs_rules=True))
    svc._answer_llm.invoke.return_value = {"message": "확인되지 않은 법률 결론", "cited_ids": cited_ids}
    response = svc.chat(ChatRequest(message="광고 표현 허용 여부 알려줘"))
    assert "판단을 보류" in response.message
    assert "확인되지 않은 법률 결론" not in response.message and not response.citations


def test_history_keeps_review_reason_and_regulation_but_not_working_metadata():
    text = assistant_history_text({"message": "문구 검토 결과", "request_id": "internal-id", "review": {
        "input_text": "원문", "result": {"review_notes": "검토 사유", "suggestion": "수정안", "next_test": "확인 항목",
        "citations": [{"source": "근거 규정", "article": "제1조", "content_snippet": "관련 내용"}]}, "timing": {"total_ms": 100}}})
    assert all(part in text for part in ["원문", "검토 사유", "수정안", "확인 항목", "근거 규정", "관련 내용"])
    assert "internal-id" not in text and "total_ms" not in text


@pytest.mark.parametrize("message", ["어떤 성분 차이인지 모르겠어", "화장품은 어떻게 만들어?"])
def test_clarification_in_ingredient_discussion_does_not_reuse_old_ad_brief(message):
    old = ChatContext(product_description="이전 크림", brief="크림 광고 작성", last_copies=["기존 광고"])
    svc = service(ChatPlan(intent="clarify", context=old, question="어떤 성분에 관해 이야기할까요?"))
    response = svc.chat(ChatRequest(message=message, context=old))
    assert response.intent == "clarify" and response.context == old
    svc.generator.generate.assert_not_called()


def test_generation_history_keeps_nested_review_reason_and_regulation():
    text = assistant_history_text({"message": "생성 결과", "generation": {"candidates": [{
        "text": "확인이 필요한 후보", "status": "확인필요", "review": {"result": {
            "review_notes": "완제품 실증과 연결되지 않은 주장", "next_test": "직접 관련 시험 자료",
            "citations": [{"source": "화장품 규정", "article": "관련 조항", "content_snippet": "근거 설명"}],
        }},
    }]}})
    assert "완제품 실증과 연결되지 않은 주장" in text and "직접 관련 시험 자료" in text
    assert "화장품 규정" in text and "근거 설명" in text
