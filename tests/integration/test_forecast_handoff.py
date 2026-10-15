from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.services import backend

APP = Path(__file__).resolve().parents[2] / "app/streamlit_app.py"


def generation_response(payload):
    return {"status": "생성완료", "candidates": [
        {"text": "오늘의 수분 루틴", "tier": "strong", "status": "검토통과", "verified": True},
        {"text": "판테놀을 담은 데일리 크림", "tier": "balanced", "status": "검토통과", "verified": True},
        {"text": "나를 챙기는 크림 루틴", "tier": "safe", "status": "검토통과", "verified": True},
    ]}


def test_new_product_selection_reaches_forecast_and_survives_rerun(monkeypatch):
    monkeypatch.setenv("UI_DATA_MODE", "mock")
    monkeypatch.setattr(backend, "generate_copy", generation_response)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.switch_page("views/generate.py").run()
    next(w for w in page.text_input if w.label == "제품명 (선택)").set_value("듀포즈 수분 크림")
    next(w for w in page.text_area if w.label == "실제 함유 성분 (선택)").set_value("판테놀, 히알루론산")
    next(w for w in page.text_area if w.label == "어떤 광고문을 만들까요?").set_value("세안 뒤 사용할 광고문")
    next(w for w in page.button if w.label == "광고문 만들기").click().run()
    page.button(key="select_generated_1").click().run()
    assert not page.exception
    assert next(w.value for w in page.text_area if w.label == "선택한 생성 문구") == "판테놀을 담은 데일리 크림"
    pid = page.session_state["bw_pid"]
    assert pid.startswith("CUSTOM_")
    assert page.session_state["bw_generation_records"][pid]["selected"] == 1
    page.switch_page("views/forecast.py").run()
    assert not page.exception
    assert next(w.value for w in page.text_area if w.label == "선택한 생성 문구") == "판테놀을 담은 데일리 크림"
    assert len(page.session_state["bw_custom_products"]) == 1


def test_handoff_activates_product_without_refreshing_stale_evidence(monkeypatch):
    from types import SimpleNamespace

    from app.services import generation_results

    state = {}
    monkeypatch.setattr(generation_results, "st", SimpleNamespace(session_state=state))
    product = {"product_id": "CUSTOM_001", "name": "수분 크림", "owned_evidence": []}
    generation_results.send_to_forecast(product, generation_response({}), {}, 1)
    state["bw_pid"] = "PROD_001"
    assert generation_results.receive_forecast()
    assert state["bw_pid"] == "CUSTOM_001"
    assert generation_results.selected(product)["text"] == "판테놀을 담은 데일리 크림"
    changed = dict(product, owned_evidence=[{"item": "보습", "value": "새 시험"}])
    assert generation_results.record(changed)[1]
    assert generation_results.selected(changed) is None


def test_unverified_candidate_cannot_be_sent_to_forecast(monkeypatch):
    from types import SimpleNamespace

    import pytest

    from app.services import generation_results

    state = {}
    monkeypatch.setattr(generation_results, "st", SimpleNamespace(session_state=state))
    response = {"candidates": [{"text": "확인 필요 초안", "verified": False, "status": "확인필요"}]}
    with pytest.raises(ValueError):
        generation_results.send_to_forecast({"product_id": "CUSTOM_001"}, response, {}, 0)
    assert "bw_forecast_handoff" not in state
