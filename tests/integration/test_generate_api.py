from unittest.mock import Mock

from fastapi.testclient import TestClient

from api.main import create_app
from cosmetic_agent.domain.generation import GenerateResponse
from cosmetic_agent.models.copy_generator import GenerationUnavailable


def test_generation_api_contract_and_failure():
    generator = Mock()
    generator.generate.return_value = GenerateResponse()
    payload = {"ingredients": ["판테놀"], "tone": "눈길 끄는", "product": {
        "product_id": "P1", "name": "크림", "category": "일반",
    }}
    with TestClient(create_app(lambda: object(), lambda reviewer: generator)) as client:
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        assert "disclaimer" in response.json()
        assert generator.generate.call_args.args[0].ingredients == ["판테놀"]
        assert generator.generate.call_args.args[0].tone == "눈길 끄는"
        generator.reset_mock()
        assert client.post("/generate", json=dict(payload, ingredients=[" "])).status_code == 422
        generator.generate.assert_not_called()
        generator.generate.side_effect = GenerationUnavailable("모델 연결 실패")
        assert client.post("/generate", json=payload).status_code == 503
