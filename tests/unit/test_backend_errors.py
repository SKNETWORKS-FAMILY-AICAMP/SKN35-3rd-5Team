import httpx
import pytest

from app.services import backend


@pytest.mark.parametrize("payload,expected", [
    ({"detail": "검색 DB(Qdrant) 연결을 확인해 주세요."}, "검색 DB(Qdrant) 연결을 확인해 주세요."),
    ({"detail": [{"msg": "invalid"}]}, "HTTP 503"),
])
def test_search_error_displays_server_detail(monkeypatch, payload, expected):
    response = httpx.Response(503, json=payload, request=httpx.Request("GET", "http://test/search"))
    monkeypatch.setattr(backend.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(backend.BackendError) as error:
        backend._get("/search")
    assert expected in str(error.value)
