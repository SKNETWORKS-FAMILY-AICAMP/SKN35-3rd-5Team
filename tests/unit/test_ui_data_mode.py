from app.services import backend


def test_mode_reads_dotenv_and_sees_edits_without_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("UI_DATA_MODE", raising=False)
    monkeypatch.setattr(backend, "_REPO", tmp_path)
    assert backend.data_mode() == "mock"
    (tmp_path / ".env").write_text("UI_DATA_MODE=api\n", encoding="utf-8")
    assert backend.data_mode() == "api"
    (tmp_path / ".env").write_text("UI_DATA_MODE=mock\n", encoding="utf-8")
    assert backend.data_mode() == "mock"


def test_process_environment_overrides_dotenv(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "_REPO", tmp_path)
    (tmp_path / ".env").write_text("UI_DATA_MODE=api\n", encoding="utf-8")
    monkeypatch.setenv("UI_DATA_MODE", "mock")
    assert backend.data_mode() == "mock"
    monkeypatch.setenv("UI_DATA_MODE", " API ")
    assert backend.data_mode() == "api"


def test_local_mode_routes_chat_and_ingredient_generation_through_embedded_app(monkeypatch):
    monkeypatch.setenv("UI_DATA_MODE", "local")
    calls = []

    def post(path, payload, *, timeout):
        calls.append(path)
        return {"ok": True}

    monkeypatch.setattr(backend, "_post", post)
    assert backend.data_mode() == "local"
    assert backend.chat({"message": "광고 생성"}) == {"ok": True}
    assert backend.generate_copy({"ingredients": ["판테놀"]}) == {"ok": True}
    assert calls == ["/chat", "/generate"]
