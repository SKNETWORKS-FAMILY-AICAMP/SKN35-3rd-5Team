from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.services import backend

PAGE = Path(__file__).resolve().parents[2] / "app" / "views" / "generate.py"


def test_generation_page_creates_from_description_without_ingredients(monkeypatch):
    calls = []

    def generate(payload):
        calls.append(payload)
        return {"candidates": [{"text": "외출 준비의 선케어 루틴", "status": "검토통과", "notes": []}],
                "warnings": [], "disclaimer": "자동 검토는 법률 준수를 보장하지 않습니다."}

    monkeypatch.setattr(backend, "generate_copy", generate)
    page = AppTest.from_file(str(PAGE)).run()
    assert not page.exception
    page.text_area[0].set_value("선크림 광고를 짧고 발랄하게 만들어줘")
    page.button[0].click().run()
    assert not page.exception
    assert calls[0]["ingredients"] == []
    assert calls[0]["product"]["owned_evidence"] == []
    assert "선크림" in calls[0]["instruction"]
    assert page.code[0].value == "외출 준비의 선케어 루틴"
    page.text_area[0].set_value("크림 광고로 바꿔줘")
    page.button[0].click().run()
    assert calls[1]["instruction"] == "크림 광고로 바꿔줘"


def test_generation_page_accepts_optional_ingredients(monkeypatch):
    calls = []
    monkeypatch.setattr(backend, "generate_copy", lambda payload: calls.append(payload) or {"candidates": [], "warnings": []})
    page = AppTest.from_file(str(PAGE)).run()
    page.text_area[0].set_value("성분 함유 크림 광고")
    next(w for w in page.text_area if w.label == "실제 함유 성분 (선택)").set_value("판테놀, 글리세린\n판테놀")
    page.button[0].click().run()
    assert not page.exception
    assert calls[0]["ingredients"] == ["판테놀", "글리세린"]


def test_generation_page_blank_and_backend_error(monkeypatch):
    def fail(payload):
        raise backend.BackendError("모델 연결 실패")

    monkeypatch.setattr(backend, "generate_copy", fail)
    page = AppTest.from_file(str(PAGE)).run()
    page.button[0].click().run()
    assert "요청을 입력" in page.error[0].value
    page.text_area[0].set_value("선크림 광고 작성")
    page.button[0].click().run()
    assert not page.exception
    assert page.error[0].value == "모델 연결 실패"
