from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.services import backend

PAGE = Path(__file__).resolve().parents[2] / "app" / "views" / "generate.py"


def test_generation_page_defaults_to_unsubstantiated_custom_product(monkeypatch):
    calls = []

    def generate(payload):
        calls.append(payload)
        return {"candidates": [{"text": "판테놀 함유 화장품", "status": "검토통과", "notes": []}],
                "warnings": [], "disclaimer": "자동 검토는 법률 준수를 보장하지 않습니다."}

    monkeypatch.setattr(backend, "generate_copy", generate)
    page = AppTest.from_file(str(PAGE)).run()
    assert not page.exception
    page.text_area[0].set_value("판테놀, 글리세린\n판테놀")
    next(widget for widget in page.selectbox if widget.label == "문구 분위기").set_value("눈길 끄는")
    page.button[0].click().run()
    assert not page.exception
    assert calls[0]["ingredients"] == ["판테놀", "글리세린"]
    assert calls[0]["product"]["owned_evidence"] == []
    assert calls[0]["tone"] == "눈길 끄는"
    assert page.code[0].value == "판테놀 함유 화장품"
    # 입력/제품 기준 변경 후 이전 결과를 그대로 쓰지 않는다.
    page.text_input[0].set_value("다른 제품").run()
    assert not page.code


def test_generation_page_blank_and_backend_error(monkeypatch):
    def fail(payload):
        raise backend.BackendError("모델 연결 실패")

    monkeypatch.setattr(backend, "generate_copy", fail)
    page = AppTest.from_file(str(PAGE)).run()
    page.button[0].click().run()
    assert "성분을 하나 이상" in page.error[0].value
    page.text_area[0].set_value("판테놀")
    page.button[0].click().run()
    assert not page.exception
    assert page.error[0].value == "모델 연결 실패"
