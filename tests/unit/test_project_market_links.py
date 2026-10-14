import json

from app.services.market_evidence import (
    COMPARISON,
    DATA,
    load_reference_catalog,
    references_for,
)


def test_links_cover_project_products_without_missing_reference_ids():
    products = json.loads(
        (DATA / "assets" / "mock_products.json").read_text(encoding="utf-8")
    )
    links = json.loads(
        (COMPARISON / "project_reference_links.json").read_text(encoding="utf-8")
    )
    catalog = load_reference_catalog()
    assert set(links["links"]) == {p["product_id"] for p in products}
    for profile in links["links"].values():
        assert all(pid in catalog for pid in profile["reference_ids"])
    assert links["evidence_transfer_allowed"] is False
    assert links["market_performance_transfer_allowed"] is False


def test_shampoos_do_not_fall_back_to_serums_or_other_products():
    catalog = load_reference_catalog()
    links = json.loads(
        (COMPARISON / "project_reference_links.json").read_text(encoding="utf-8")
    )
    for pid in ["PROD_003", "PROD_004", "unknown"]:
        assert not references_for(pid, catalog, links)[1]
    assert not references_for("PROD_001", catalog, links)[1]  # No declared ingredients.
    public_refs = references_for("PUBLIC_KIEHLS_UFC", catalog, links)[1]
    assert len(public_refs) == 1
    assert public_refs[0]["product_id"] == "MKT_BIOSSANCE_OMEGA"
    assert public_refs[0]["observed_copies"]


def test_market_page_follows_shared_sidebar_product_and_evidence(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("UI_DATA_MODE", "mock")
    root = DATA.parent
    app = AppTest.from_file(
        str(root / "app" / "streamlit_app.py"), default_timeout=20
    ).run()
    assert not app.exception
    app.switch_page("views/market.py").run()
    assert not app.exception
    # 처음에는 제품 정보 없이 일반 화장품 기준(GENERAL_DEFAULT). 공개 분석 샘플을 고르면 시장 페이지가 따라간다.
    assert app.selectbox(key="proj_product").value == "GENERAL_DEFAULT"
    app.selectbox(key="proj_product").select("PUBLIC_KIEHLS_UFC").run()
    assert not app.exception
    assert any("키엘" in h.value for h in app.subheader)
    app.button(key="ingredient_review_PUBLIC_KIEHLS_UFC").click().run()
    assert not app.exception
    assert any("데모 판정" in m.value for m in app.markdown)
    products = json.loads(
        (DATA / "assets" / "mock_products.json").read_text(encoding="utf-8")
    )
    for product in products:
        app.selectbox(key="proj_product").select(product["product_id"]).run()
        assert not app.exception
        assert any(product["name"] in h.value for h in app.subheader)
        if product["product_id"] in {"PROD_003", "PROD_004"}:
            assert not [
                s for s in app.selectbox if s.key.startswith("market_reference_")
            ]
    app.selectbox(key="proj_product").select("PROD_001").run()
    app.checkbox(key="proj_ev_PROD_001_0").uncheck().run()
    assert not app.exception
    assert any("선택 실증 0/1" in c.value for c in app.caption)
