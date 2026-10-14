import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "sales_forecast_reference"


def rows(name):
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
    ]


def test_public_sales_and_cases_are_not_copy_training_labels():
    sales = rows("product_sales_observations.jsonl")
    cases = rows("beauty_campaign_cases.jsonl")
    assert len(sales) == 2 and len(cases) == 5
    assert all(not row["eligible_for_copy_sales_training"] for row in sales + cases)
    assert all(not row["copy_effect_identified"] for row in sales + cases)
    assert all(row["units_sold"] is None for row in sales + cases)
    assert all(not row["exact_sku_match_verified"] for row in sales)
    assert all(row["currency"] == "JPY" and row["net_revenue"] is None for row in sales)


def test_campaign_metrics_preserve_scope_and_entity():
    cases = {case["case_id"]: case for case in rows("beauty_campaign_cases.jsonl")}
    assert cases["NUMBUZIN_TIKTOK_MY"]["brand"] == "Numbuzin/넘버즈인"
    metrics = cases["BIODERMA_CRITEO"]["metrics"]
    assert metrics[0]["metric"] == "ROAS_ratio_vs_previous_setup"
    assert metrics[0]["operator"] == "approx"
    assert sum(len(c["metrics"]) for c in cases.values()) == 17


def test_sample_products_remain_explicitly_unready():
    coverage = rows("sample_product_coverage.jsonl")
    assert len(coverage) == 5
    assert all(row["same_period_copy_performance_rows"] == 0 for row in coverage)
    assert all(
        row["forecast_readiness"] == "insufficient_matched_data" for row in coverage
    )
    assert all(
        row["purchases"] is None and row["units_sold"] is None for row in coverage
    )


def test_scenario_template_contains_no_fabricated_forecasts():
    template = json.loads(
        (ROOT / "forecast_input_template.json").read_text(encoding="utf-8")
    )
    assert template["record_kind"] == "scenario_assumptions_not_observed"
    assert not template["copy_lift"]["identified"]
    for key in [
        "planned_clicks",
        "expected_buyers",
        "expected_orders",
        "expected_units",
        "expected_net_revenue_krw",
    ]:
        assert template[key] is None


def test_hillstrom_aggregate_is_cross_domain_and_not_unit_sales():
    aggregate = json.loads(
        (ROOT / "hillstrom_group_summary.json").read_text(encoding="utf-8")
    )
    assert aggregate["domain"] == "non_cosmetics_retail"
    assert sum(g["customers"] for g in aggregate["groups"]) == 64000
    assert sum(g["buyers"] for g in aggregate["groups"]) == 578
    assert all(g["units_sold"] is None for g in aggregate["groups"])
    assert all(0 <= g["buyer_rate"] <= 1 for g in aggregate["groups"])
