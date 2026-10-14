import json
from pathlib import Path
from types import SimpleNamespace

from cosmetic_agent.domain.schemas import ProductCard
from cosmetic_agent.models.prompts import build_suggest_user_prompt
from cosmetic_agent.service import ReviewService

ROOT = Path(__file__).resolve().parents[2]


def product():
    data = json.loads(
        (ROOT / "data/assets/public_analysis_products.json").read_text(encoding="utf-8")
    )
    return ProductCard.model_validate(data[0])


def test_public_trial_summaries_keep_actual_product_scope_and_conditions():
    card = product()
    assert len(card.owned_evidence) == 3
    assert all(
        e.source_kind == "public_brand_summary" and e.report_available is False
        for e in card.owned_evidence
    )
    assert all(
        e.institute is None and e.source_url and e.conditions
        for e in card.owned_evidence
    )
    body = json.dumps(card.model_dump(), ensure_ascii=False)
    assert "72시간" in body and "23.5%" in body and "29.3%" in body
    assert "44%" not in body and "42%" not in body


def test_source_metadata_reaches_graph_and_review_notes():
    card = product()
    captured = {}

    def invoke(state):
        captured.update(state)
        return {"status": "판정", "level": 0}

    service = ReviewService.__new__(ReviewService)
    service.graph = SimpleNamespace(invoke=invoke)
    response = service.review_single("수분 크림", card)
    assert captured["owned_evidence"][0]["source_kind"] == "public_brand_summary"
    assert "원보고서" in response.result.review_notes
    prompt = build_suggest_user_prompt(
        copy_text="보습",
        product=card.model_dump(),
        owned_evidence=captured["owned_evidence"],
        level=1,
        violation_type="실증필요",
    )
    assert "18~65세 여성 29명" in prompt
    assert "원보고서 미확보" in prompt


def test_review_chat_receives_selected_evidence_and_respects_checkbox(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("UI_DATA_MODE", "mock")
    app = AppTest.from_file(
        str(ROOT / "app/streamlit_app.py"), default_timeout=30
    ).run()
    app.switch_page("views/review.py").run()
    assert not app.exception
    # 기본 제품은 시연용 자사 샘플(PROD_001). 공개 분석 샘플을 직접 고른 뒤 같은 내용을 확인한다.
    assert app.selectbox(key="proj_product").value == "PROD_001"
    app.selectbox(key="proj_product").select("PUBLIC_KIEHLS_UFC").run()
    assert not app.exception
    assert len([c for c in app.checkbox if c.key.startswith("proj_ev_PUBLIC_")]) == 3
    app.chat_input(key="bw_chat").set_value("도포 72시간 후 수분 유지력 23.5%").run()
    assert not app.exception
    threads = app.session_state["bw_threads"]
    sent = threads[0]["messages"][0]["product"]["owned_evidence"]
    assert len(sent) == 3 and sent[0]["source_kind"] == "public_brand_summary"
    assert any(m["role"] == "assistant" for m in threads[0]["messages"])
    app.checkbox(key="proj_ev_PUBLIC_KIEHLS_UFC_0").uncheck().run()
    assert not app.exception
    assert sum(c.value for c in app.checkbox if c.key.startswith("proj_ev_PUBLIC_")) == 2
    assert len(threads[0]["messages"][0]["product"]["owned_evidence"]) == 3
