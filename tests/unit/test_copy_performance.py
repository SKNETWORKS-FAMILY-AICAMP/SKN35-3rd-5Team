import pytest

from app.services.copy_performance import compare_arms, relative_change


def test_equal_exposure_projection_separates_click_and_sales_changes():
    # Synthetic test fixture, not observed public or cosmetics sales data.
    a = {
        "impressions": 1000,
        "clicks": 50,
        "orders": 10,
        "units": 15,
        "net_revenue": 300000,
    }
    b = {
        "impressions": 2000,
        "clicks": 200,
        "orders": 10,
        "units": 20,
        "net_revenue": 400000,
    }
    result = compare_arms(a, b, 10000)
    assert result["ctr_relative_change_pct"] == pytest.approx(100)
    assert result["ctr_difference_pp"] == pytest.approx(5)
    assert result["projections"]["net_revenue"]["a"] == 3000000
    assert result["projections"]["net_revenue"]["b"] == 2000000
    assert result["projections"]["units"]["b"] == 100
    assert result["projections"]["orders"]["b"] == 50
    assert result["projections"]["net_revenue"]["change_pct"] < 0


def test_missing_sales_stays_missing_and_zero_baseline_has_no_relative_lift():
    a = {"impressions": 1000, "clicks": 0}
    b = {"impressions": 1000, "clicks": 20}
    result = compare_arms(a, b, 10000)
    assert result["ctr_relative_change_pct"] is None
    assert result["projections"]["units"]["b"] is None
    assert result["projections"]["net_revenue"]["change_pct"] is None
    assert relative_change(10, 0) == -100


@pytest.mark.parametrize(
    "arm",
    [
        {"impressions": 0, "clicks": 0},
        {"impressions": 100, "clicks": 101},
        {"impressions": 100, "clicks": 2, "units": -1},
        {"impressions": 100, "clicks": 2, "net_revenue": float("nan")},
    ],
)
def test_invalid_values_do_not_generate_forecasts(arm):
    with pytest.raises(ValueError):
        compare_arms(arm, {"impressions": 100, "clicks": 2}, 1000)


def test_form_keeps_missing_sales_blank_and_requires_explicit_input():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(
        "from app.components.performance import render_performance\nrender_performance('PROD_001')",
        default_timeout=20,
    ).run()
    assert not app.exception
    assert all(widget.value is None for widget in app.number_input)
    app.text_input(key="perf_PROD_001_source").set_value(
        "자동 테스트용 가정; 실제 실적 아님"
    )
    for arm, clicks in [("A", 20), ("B", 30)]:
        app.text_input(key=f"perf_PROD_001_{arm}_copy").set_value(f"가정 후보 {arm}")
        app.number_input(key=f"perf_PROD_001_{arm}_impressions").set_value(1000)
        app.number_input(key=f"perf_PROD_001_{arm}_clicks").set_value(clicks)
    app.button[0].click().run()
    assert not app.exception
    record = app.session_state["perf_PROD_001_result"]
    assert record["basis"] == "가정 시나리오"
    assert record["result"]["ctr_difference_pp"] == pytest.approx(1)
    assert record["result"]["projections"]["net_revenue"]["b"] is None
