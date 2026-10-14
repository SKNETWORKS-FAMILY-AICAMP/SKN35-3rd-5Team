from unittest.mock import Mock

from fastapi.testclient import TestClient

from api.main import create_app
from cosmetic_agent.domain.schemas import ExecutionTiming, GenerateResponse
from cosmetic_agent.models.copy_generator import GenerationUnavailable


def test_generation_api_contract_and_failure():
    generator = Mock()
    generator.generate.return_value = GenerateResponse(request_id="test", status="생성완료", product_id="P1", timing=ExecutionTiming())
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


def test_both_generation_inputs_use_one_graph_service():
    reviewer, generator = Mock(), Mock()
    generator.generate.return_value = GenerateResponse(
        request_id="project", status="생성완료", product_id="P1", timing=ExecutionTiming())
    product = {"product_id": "P1", "name": "크림", "category": "일반"}
    with TestClient(create_app(lambda: reviewer, lambda service: generator)) as client:
        ingredient = client.post("/generate", json={"ingredients": ["판테놀"], "product": product})
        project = client.post("/generate", json={"instruction": "제품 기준 광고문", "product": product})
    assert ingredient.status_code == project.status_code == 200
    assert "disclaimer" in ingredient.json()
    assert project.json()["status"] == "생성완료"
    assert generator.generate.call_count == 2
    reviewer.generate_copy.assert_not_called()


def test_freeform_generation_request_needs_no_ingredients():
    generator = Mock()
    generator.generate.return_value = GenerateResponse(
        request_id="freeform", status="생성완료", product_id="P1", timing=ExecutionTiming())
    with TestClient(create_app(lambda: object(), lambda reviewer: generator)) as client:
        response = client.post("/generate", json={"instruction": "선크림 광고를 작성해줘", "product": {
            "product_id": "P1", "name": "선크림", "category": "일반"}})
    assert response.status_code == 200
    assert generator.generate.call_args.args[0].ingredients == []
