"""외부 모델/검색 인프라 없이 검증하는 API 계약 테스트."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from api.main import create_app
from cosmetic_agent.domain.schemas import ExecutionTiming, ReviewResponse, ReviewResult


class StubReviewService:
    def __init__(self):
        self.calls = []

    def review_single(self, text, product):
        self.calls.append((text, product))
        return ReviewResponse(
            request_id=str(uuid4()), input_text=text,
            result=ReviewResult(status="판단보류", review_notes="API 테스트용 응답"),
            timing=ExecutionTiming(),
        )


@pytest.fixture
def api_client():
    service = StubReviewService()
    with TestClient(create_app(lambda: service)) as client:
        yield client, service


def test_health_check_endpoint(api_client):
    client, _ = api_client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_single_review_passes_product_and_evidence(api_client, sample_product):
    client, service = api_client
    response = client.post("/review", json={
        "copy_text": "  피부 보습을 돕습니다.  ", "product": sample_product.model_dump(),
    })
    assert response.status_code == 200
    assert response.json()["input_text"] == "피부 보습을 돕습니다."
    assert response.json()["result"]["status"] == "판단보류"
    assert service.calls == [("피부 보습을 돕습니다.", sample_product)]


def test_bulk_preserves_decimal_and_order(api_client, sample_product):
    client, service = api_client
    response = client.post("/review/bulk", json={
        "full_text": '보습 42.5% 개선. 촉촉해요!매끈해요?\n\n"피부를 케어합니다." 마지막 문구',
        "product": sample_product.model_dump(),
    })
    assert response.status_code == 200
    expected = ["보습 42.5% 개선.", "촉촉해요!", "매끈해요?", '"피부를 케어합니다."', "마지막 문구"]
    assert [item["input_text"] for item in response.json()] == expected
    assert [text for text, _ in service.calls] == expected
    assert all(product == sample_product for _, product in service.calls)


@pytest.mark.parametrize("path,field,value", [
    ("/review", "copy_text", " \n\t"),
    ("/review", "copy_text", "가" * 5001),
    ("/review/bulk", "full_text", "\n\n"),
    ("/review/bulk", "full_text", "가" * 50001),
    ("/review/bulk", "full_text", "문구. " * 101),
], ids=["single-blank", "single-too-long", "bulk-blank", "bulk-too-long", "too-many-sentences"])
def test_invalid_input(api_client, sample_product, path, field, value):
    client, service = api_client
    response = client.post(path, json={field: value, "product": sample_product.model_dump()})
    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize("change", [
    {"category": "의약품"}, {"name": " "}, {"product_id": ""},
    {"owned_evidence": [{"test_type": "", "item": "보습"}]},
])
def test_invalid_product(api_client, sample_product, change):
    client, service = api_client
    product = sample_product.model_dump()
    product.update(change)
    response = client.post("/review", json={"copy_text": "보습 케어", "product": product})
    assert response.status_code == 422
    assert service.calls == []


def test_openapi_contract(api_client):
    client, _ = api_client
    schema = client.get("/openapi.json").json()
    assert "/review" in schema["paths"]
    assert "/review/bulk" in schema["paths"]
    assert schema["components"]["schemas"]["ProductCard"]["properties"]["category"]["enum"] == ["일반", "기능성"]
