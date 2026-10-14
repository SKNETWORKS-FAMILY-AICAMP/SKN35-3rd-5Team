from unittest.mock import Mock

from fastapi.testclient import TestClient

from api.main import create_app
from cosmetic_agent.domain.chat import ChatContext, ChatResponse
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
