"""예상 매출 시나리오: 처분 위험(D1)·문구 변화 폭(D5)의 계산 규칙."""
import pytest

from app.services.revenue_scenario import (
    Range3,
    build_scenario,
    copy_change_band,
    load_effect_distribution,
    penalty_for,
)

GENERAL = {"category": "일반", "functional_type": None, "owned_evidence": []}


def _scenario(text, **kw):
    kw.setdefault("price_krw", 10000)
    kw.setdefault("monthly_units", 100)
    return build_scenario(copy_text=text, product=GENERAL, **kw)


def test_drug_claim_maps_to_three_months_ad_suspension():
    risk = _scenario("피부 재생 크림")["revenue_at_risk_if_unchanged"]
    assert risk["status"] == "mapped" and risk["months"] == 3
    assert risk["basis_law_id"] == "LAW_시행규칙_별표5-2가"
    assert risk["sanction"] == "해당 품목 광고업무정지"
    assert risk["upper_bound_krw"]["mid"] == 10000 * 100 * 3
    assert risk["estimate_krw"] is None and risk["detection_probability"] is None


def test_ad_dependent_share_gives_estimate_and_label_violation_stops_sales():
    risk = _scenario("피부 재생 크림", ad_dependent_share=0.4)["revenue_at_risk_if_unchanged"]
    assert risk["estimate_krw"]["mid"] == pytest.approx(10000 * 100 * 3 * 0.4)
    label = _scenario("피부 재생 크림", sanction_kind="표시")["revenue_at_risk_if_unchanged"]
    assert label["sanction"] == "해당 품목 판매업무정지" and label["amount_krw"]["mid"] == 3_000_000


def test_offense_count_and_blank_fourth_column():
    assert penalty_for(["LAW_시행규칙_별표5-2가"], offense=2)["heaviest"]["months"] == 6
    fourth = penalty_for(["LAW_시행규칙_별표5-2가"], offense=4)
    assert fourth["heaviest"] is None and fourth["status"] == "needs_review"
    assert penalty_for(["LAW_시행규칙_별표5-2사"], offense=4)["heaviest"]["months"] == 12


def test_multiple_violations_use_heaviest_not_sum():
    p = penalty_for(["LAW_시행규칙_별표5-2사", "LAW_시행규칙_별표5-2가"])
    assert p["heaviest"]["months"] == 3 and len(p["matched"]) == 2


def test_unmapped_law_id_is_review_not_guess():
    p = penalty_for(["LAW_화장품법_제13조"])
    assert p["status"] == "needs_review" and p["unmapped_law_ids"] == ["LAW_화장품법_제13조"]
    risk = build_scenario(price_krw=1, monthly_units=1, law_ids=["LAW_화장품법_제13조"], level=2)
    assert risk["revenue_at_risk_if_unchanged"]["status"] == "needs_review"


def test_clean_copy_has_no_risk():
    assert _scenario("촉촉한 수분 크림")["revenue_at_risk_if_unchanged"]["status"] == "no_violation"


def test_conditional_level_is_labelled_conditionally():
    risk = _scenario("보습력 87% 개선")["revenue_at_risk_if_unchanged"]
    assert risk["condition"].startswith("실증 자료")


def test_copy_band_is_symmetric_and_only_on_exposed_share():
    revenue = Range3(1000, 1000, 1000)
    q = load_effect_distribution()["absolute_relative_ctr_change"]["quantiles"]
    full = copy_change_band(revenue, 1.0)
    half = copy_change_band(revenue, 0.5)
    assert full["direction"] == "unknown"
    assert full["typical_range_krw"]["low"] == round(1000 - 1000 * q["p75"])
    assert full["typical_range_krw"]["high"] == round(1000 + 1000 * q["p75"])
    assert half["change_magnitude_krw"]["p75"] == round(500 * q["p75"])


def test_ranges_and_validation():
    s = build_scenario(price_krw={"low": 9000, "high": 11000}, monthly_units={"low": 50, "mid": 100, "high": 200},
                       law_ids=[], level=0)
    assert s["monthly_revenue_krw"] == {"low": 450000, "mid": 1000000, "high": 2200000}
    with pytest.raises(ValueError):
        build_scenario(price_krw=-1, monthly_units=1, law_ids=[], level=0)
    with pytest.raises(ValueError):
        build_scenario(price_krw=1, monthly_units={"low": 5, "high": 1}, law_ids=[], level=0)
    with pytest.raises(ValueError):
        build_scenario(price_krw=1, monthly_units=1, law_ids=[], level=0, copy_exposed_share=1.5)
    with pytest.raises(ValueError):
        build_scenario(price_krw=1, monthly_units=1)
