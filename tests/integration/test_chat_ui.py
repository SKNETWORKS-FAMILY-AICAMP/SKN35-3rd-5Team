from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.services import backend

PAGE = Path(__file__).resolve().parents[2] / "app" / "views" / "chat.py"
APP = PAGE.parents[1] / "streamlit_app.py"


def test_chat_page_followup_and_reset(monkeypatch):
    calls = []

    def chat(payload):
        calls.append(payload)
        return {"intent": "clarify", "message": "실제 성분을 알려주세요", "context": {"ingredients": ["판테놀"]}}

    monkeypatch.setattr(backend, "chat", chat)
    page = AppTest.from_file(str(PAGE)).run()
    assert not page.exception
    page.chat_input[0].set_value("광고문 생성").run()
    assert not page.exception
    assert calls[0]["product"]["owned_evidence"] == []
    page.chat_input[0].set_value("SNS로 만들어줘").run()
    assert calls[1]["context"]["ingredients"] == ["판테놀"]
    assert calls[1]["history"][0]["content"] == "광고문 생성"
    assert len(page.chat_message) == 4
    page.button[0].click().run()
    assert not page.chat_message


def test_error_keeps_previous_conversation(monkeypatch):
    def fail(payload):
        raise backend.BackendError("모델 연결 실패")

    monkeypatch.setattr(backend, "chat", fail)
    page = AppTest.from_file(str(PAGE)).run()
    page.chat_input[0].set_value("검토해줘").run()
    assert not page.exception
    assert page.error[0].value == "모델 연결 실패"
    assert not page.chat_message


def test_launcher_and_chat_navigation_preserve_existing_pages(monkeypatch):
    monkeypatch.setattr(backend, "health", lambda: {"mode": "mock", "ok": True})
    page = AppTest.from_file(str(APP)).run()
    assert not page.exception
    assert set(page.session_state["bw_pages"]) == {"chat", "generate", "review", "bulk", "library", "market"}
    assert len(page.get("popover")) == 1
    assert any(w.label == "보내기" for w in page.button)


def test_chat_backend_mock_does_not_fabricate_response(monkeypatch):
    monkeypatch.setattr(backend, "data_mode", lambda: "mock")
    try:
        backend.chat({"message": "광고 생성"})
    except backend.BackendError as error:
        assert "API 모드" in error.message
    else:
        raise AssertionError("mock chat must report API requirement")


def test_popup_and_full_page_share_conversation(monkeypatch):
    calls = []

    def chat(payload):
        calls.append(payload)
        return {"intent": "clarify", "message": "사용할 채널을 알려주세요", "context": {"ingredients": ["판테놀"]}}

    monkeypatch.setattr(backend, "chat", chat)
    monkeypatch.setattr(backend, "health", lambda: {"mode": "mock", "ok": True})
    page = AppTest.from_file(str(APP)).run()
    next(w for w in page.text_input if w.label == "챗봇 요청").set_value("판테놀 광고문 만들어줘")
    next(w for w in page.button if w.label == "보내기").click().run()
    assert not page.exception
    page.switch_page("views/chat.py").run()
    assert not page.exception
    next(w for w in page.chat_input if w.key == "chat_full_input").set_value("SNS로 만들어줘").run()
    assert not page.exception
    assert calls[1]["context"] == {"ingredients": ["판테놀"]}
    assert calls[1]["history"][0]["content"] == "판테놀 광고문 만들어줘"
