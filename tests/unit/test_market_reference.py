import json
import shutil

import pytest
from jsonschema import Draft202012Validator

from scripts.build_market_reference import ROOT, build_context


def test_public_copies_are_not_legal_or_sales_labels():
    rows = build_context()
    assert len(rows) >= 28
    assert all(row["corpus_type"] == "market_reference" for row in rows)
    assert all(not row["allowed_as_regulatory_evidence"] for row in rows)
    assert all(not row["allowed_as_copy_performance_label"] for row in rows)
    assert all(row["performance"]["net_revenue_krw"] is None for row in rows)
    assert all(row["performance"]["paid_targeting"] is None for row in rows)


def test_listing_offer_keeps_bundle_and_images_together():
    row = next(row for row in build_context() if row["observation_id"] == "COPY_003")
    assert row["offer"]["unit_count"] == 2
    assert len(row["assets"]) == 2
    assert all(asset["offer_id"] == row["offer"]["offer_id"] for asset in row["assets"])


def test_brand_campaign_target_is_not_transferred_to_a_product():
    row = next(row for row in build_context() if row["observation_id"] == "COPY_013")
    assert row["product"] is None and row["offer"] is None
    assert row["scope"] == "brand_line_campaign"
    assert row["performance"]["paid_targeting"] is None


def test_company_revenue_cannot_be_attached_to_copy(tmp_path):
    for path in ROOT.iterdir():
        if path.is_file():
            shutil.copy2(path, tmp_path / path.name)
    path = tmp_path / "business_context.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["product_id"] = "MKT_ANUA_PDRN_SERUM"
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="Company revenue"):
        build_context(tmp_path)


def test_performance_schema_and_unknown_values_are_explicit():
    schema = json.loads((ROOT / "internal_performance.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["source_kind"]["enum"] == [
        "ad_platform_export", "analytics_export", "order_attribution_export",
    ]
    assert "null" in schema["properties"]["purchases"]["type"]
    payload = json.loads((ROOT / "internal_performance.json").read_text(encoding="utf-8"))
    assert payload["records"] == []


def test_product_cumulative_units_do_not_become_oliveyoung_offer_sales():
    row = next(row for row in build_context() if row["observation_id"] == "COPY_011")
    signal = next(s for s in row["public_market_signals"] if s["metric"] == "cumulative_units_sold")
    assert signal["channel"] is None
    assert signal["relationship"] == "product_family_context_not_offer_performance"
    assert row["performance"]["net_revenue_krw"] is None


def test_brand_sales_threshold_is_not_exact_product_sales():
    row = next(row for row in build_context() if row["observation_id"] == "COPY_012")
    signal = next(s for s in row["public_market_signals"] if s["metric"] == "annual_sales_krw")
    assert signal["value_semantics"] == "lower_bound_exclusive"
    assert signal["product_id"] is None and not signal["copy_effect_established"]
    assert row["product"] is None


def test_same_product_family_has_three_distinct_platform_offers():
    rows = [row for row in build_context() if row["product"] and row["product"]["product_id"] == "MKT_AESTURA_365"]
    assert {row["offer"]["channel"] for row in rows if row["offer"]} == {
        "oliveyoung", "musinsa_beauty", "beauty_kurly",
    }
    historical = next(row for row in rows if row["offer"] and row["offer"]["channel"] == "beauty_kurly")
    assert historical["offer"]["record_type"] == "historical_promotion_announcement"
    assert historical["offer"]["displayed_price_krw"] is None


def test_kurly_sales_are_linked_only_to_correct_dalba_product_family():
    rows = build_context()
    spray = next(row for row in rows if row["observation_id"] == "COPY_027")
    lotion = next(row for row in rows if row["observation_id"] == "COPY_016")
    assert any(s["metric"] == "event_units_sold" and s["value"] == 5200 for s in spray["public_market_signals"])
    assert not any(s["metric"] == "event_units_sold" for s in lotion["public_market_signals"])
    assert spray["performance"]["purchases"] is None


def test_rejuran_cosmetics_and_odm_are_not_medical_or_ownership_shortcuts():
    rows = build_context()
    rejuran = next(row for row in rows if row["observation_id"] == "COPY_020")
    assert rejuran["product"]["product_domain"] == "cosmetics"
    assert rejuran["company_context"][0]["company"]["company_id"] == "CO_PHARMARESEARCH"
    assert all(context["company"]["company_id"] != "CO_KOLMAR" for row in rows for context in row["company_context"])


def test_medicube_corporate_ir_is_not_oliveyoung_mask_revenue():
    row = next(row for row in build_context() if row["observation_id"] == "COPY_018")
    signal = next(s for s in row["public_market_signals"] if s["metric"] == "cosmetics_revenue_krw")
    assert signal["channel"] == "all_channels" and signal["period"] == "2024-Q4"
    assert signal["product_id"] is None
    assert row["performance"]["net_revenue_krw"] is None
