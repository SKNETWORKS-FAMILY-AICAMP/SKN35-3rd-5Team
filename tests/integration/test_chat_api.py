from unittest.mock import Mock

from fastapi.testclient import TestClient

from api.main import create_app
from cosmetic_agent.domain.chat import ChatContext, ChatResponse
from cosmetic_agent.models.chatbot import SCOPE_NOTICE, ChatPlan, ChatService
from cosmetic_agent.models.copy_generator import GenerationUnavailable


def test_chat_api_contract_validation_and_unavailable():
    chatbot = Mock()
    chatbot.chat.return_value = ChatResponse(intent="clarify", message="성분을 알려주세요", context=ChatContext())
    with TestClient(create_app(lambda: Mock(), lambda reviewer: Mock(), lambda reviewer, generator: chatbot)) as client:
        response = client.post("/chat", json={"message": "광고문 만들어줘"})
        assert response.status_code == 200
        assert response.json()["intent"] == "clarify"
        assert chatbot.chat.call_args.args[0].product.owned_evidence == []
        chatbot.reset_mock()
        for message in [" ", "x" * 5001]:
            assert client.post("/chat", json={"message": message}).status_code == 422
        chatbot.chat.assert_not_called()
        chatbot.chat.side_effect = GenerationUnavailable("모델 연결 실패")
        assert client.post("/chat", json={"message": "문구 검토"}).status_code == 503


def test_cosmetics_conversation_and_scope_gate_through_real_graph_api():
    reviewer, generator, router, answer = Mock(), Mock(), Mock(), Mock()
    router.invoke.side_effect = [
        ChatPlan(intent="answer", context=ChatContext(), resolved_question="PDRN이란 무엇인가요?"),
        ChatPlan(intent="answer", context=ChatContext(), needs_history=True),
        ChatPlan(intent="answer", context=ChatContext(), resolved_question="PDRN 설명을 쉽게 풀어주세요."),
        ChatPlan(intent="answer", context=ChatContext(), scope="out_of_scope"),
    ]
    answer.invoke.side_effect = [{"message": "PDRN 성분 설명"}, {"message": "PDRN 성분을 쉽게 풀어 쓴 설명"}]
    chatbot = ChatService(reviewer, generator, llm=router, answer_llm=answer)
    app = create_app(lambda: reviewer, lambda _: generator, lambda *_: chatbot)
    with TestClient(app) as client:
        first = client.post("/chat", json={"message": "PDRN이 뭐야?"})
        assert first.status_code == 200 and first.json()["message"] == "PDRN 성분 설명"
        second = client.post("/chat", json={
            "message": "더 쉽게 설명해줘", "context": first.json()["context"],
            "history": [{"role": "user", "content": "PDRN이 뭐야?"}, {"role": "assistant", "content": first.json()["message"]}],
        })
        assert second.status_code == 200 and second.json()["message"] == "PDRN 성분을 쉽게 풀어 쓴 설명"
        unrelated = client.post("/chat", json={"message": "이번 주 주식 추천해줘"})
        assert unrelated.status_code == 200 and unrelated.json()["message"] == SCOPE_NOTICE
    assert answer.invoke.call_count == 2
    reviewer.review_single.assert_not_called()
    reviewer.hybrid_retriever.retrieve.assert_not_called()
    generator.generate.assert_not_called()
