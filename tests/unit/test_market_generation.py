from pathlib import Path

from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.verifier import CopyVerifier
from cosmetic_agent.generation.market import market_references
from cosmetic_agent.generation.nodes import (
    generate_candidates_node,
    verify_candidates_node,
)
from cosmetic_agent.market_reference import _merge_same_product, ingredient_groups

TONER = {"product_id": "CUSTOM_001", "name": "수분 진정 수딩 토너", "form": "토너",
         "category": "일반", "key_ingredients": ["히알루론산", "판테놀"], "owned_evidence": []}


def test_market_references_reuse_originals_with_sources_and_no_owned_evidence():
    refs = market_references(TONER)
    assert len(refs) == 1
    row = refs[0]
    assert row["reference_id"] == "M1" and row["form"] == "토너"
    assert "anua.kr" in row["source_url"] and row["observed_on"] == "2026-10-14"
    assert row["conditions"] and row["allowed_as_owned_evidence"] is False
    assert "owned_evidence" not in row and TONER["owned_evidence"] == []
    assert market_references(dict(TONER, form="클렌저")) == []


def test_existing_cream_profiles_are_available_to_generation():
    refs = market_references({"name": "스쿠알란 크림", "form": "크림", "key_ingredients": ["스쿠알란"]})
    assert any(r["product_id"] == "MKT_BIOSSANCE_OMEGA" and r["market"] == "US" for r in refs)
    assert "판테놀" in ingredient_groups("Panthenol")
    own_refs = market_references({"product_id": "PUBLIC_KIEHLS_UFC", "name": "키엘 크림", "form": "크림", "key_ingredients": ["스쿠알란"]})
    assert own_refs and all(r["product_id"] != "MKT_KIEHLS_UFC" for r in own_refs)


def test_same_brand_shared_ingredient_does_not_merge_different_skus():
    a = {"product_id": "a", "brand": "브랜드", "form": "토너", "ingredients": {"판테놀"},
         "ranking": None, "review_count": None, "score": 3, "copies": [], "signals": []}
    assert len(_merge_same_product([a, dict(a, product_id="b")])) == 2


def test_generation_receives_market_data_separately_from_regulations():
    captured = {}
    class Generator:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return []
    generate_candidates_node({"product": TONER, "instruction": "소개", "channel": "SNS",
                              "tone": "간결한", "length": "한 줄", "keywords": [],
                              "evidence_text": "[L1] 규정", "market_references": market_references(TONER)}, Generator())
    # 시장 문구는 규정(evidence_text)과 섞이지 않고 생성 재료 블록의 [말투 참고]에 M번호로 들어간다
    assert "M1" in captured["knowledge"] and "M1" not in captured["evidence_text"]
    assert captured["evidence_text"] == "[L1] 규정"
    assert captured["product"]["owned_evidence"] == []


def test_reference_ids_and_foreign_ingredients_cannot_be_invented():
    refs = market_references(TONER)
    state = {"product": TONER, "market_references": refs, "drafts": [
        {"text": "히알루론산 함유 토너", "tier": "safe", "market_reference_ids": ["M99"]},
        {"text": "레티놀 함유 토너", "tier": "safe", "market_reference_ids": ["M1"]},
        {"text": "보습력 90% 개선 토너", "tier": "strong", "market_reference_ids": ["M1"]},
    ]}
    result = verify_candidates_node(state, CopyVerifier(), RuleEngine())
    assert result["candidates"] == [] and len(result["rejected_notes"]) == 3


def test_selected_generated_copy_is_shared_with_forecast(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from app.services import backend, mock

    monkeypatch.setenv("UI_DATA_MODE", "mock")
    # 새 생성 화면은 데모 모드에서 생성을 막으므로, 화면 흐름 시험에는 결정적 예시 생성기를 쓴다
    monkeypatch.setattr(backend, "generate_copy", lambda payload: mock.generate_copy(payload["instruction"], payload["product"]))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/streamlit_app.py"), default_timeout=30).run()
    app.switch_page("views/generate.py").run()
    # 실증 자료가 있는 시연용 예시 제품을 불러온다 (처음에는 제품 정보 없음 기준)
    app.selectbox(key="proj_product").select("PROD_001").run()
    next(c for c in app.checkbox if c.label.startswith("왼쪽 「내 제품」")).check().run()
    # 폼 안의 입력은 제출 버튼과 같은 실행에서 반영된다
    next(t for t in app.text_area if t.label == "어떤 광고문을 만들까요?").input("제품 광고문을 만들어줘")
    next(b for b in app.button if b.label == "광고문 만들기").click().run()
    assert not app.exception
    pid, record = next(iter(app.session_state["bw_generation_records"].items()))
    expected = record["response"]["candidates"][1]["text"]
    # 후보마다 달린 선택 버튼(준호)으로 두 번째 후보를 예상 매출에 보낸다
    app.button(key="select_generated_1").click().run()
    assert not app.exception
    assert next(t.value for t in app.text_area if t.label == "선택한 생성 문구") == expected
    # 기존 수치 근거를 해제하면 다른 화면에서 이전 결과를 재사용하지 않는다.
    app.checkbox(key=f"proj_ev_{pid}_0").uncheck().run()
    app.switch_page("views/forecast.py").run()
    assert not app.exception
    assert any("다시 생성" in w.value for w in app.warning)
    assert next(t.value for t in app.text_area if t.label == "선택한 생성 문구") == ""

