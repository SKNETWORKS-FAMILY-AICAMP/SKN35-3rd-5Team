import importlib.util
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "build_copy_comparison_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("copy_evidence", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def arms(day="2014-03-01"):
    return [
        {
            "clickability_test_id": "test",
            "eyecatcher_id": "image",
            "created_at": day,
            "headline": text,
            "impressions": "2000",
            "clicks": str(clicks),
        }
        for text, clicks in [("A", 20), ("B", 40)]
    ]


def test_entire_test_excluded_if_any_arm_in_suspect_period():
    rows = arms()
    rows[1]["created_at"] = "2014-01-10"
    pairs, counts = MODULE.select_pairs(rows)
    assert not pairs
    assert counts["tests_excluded_randomization_risk_period"] == 1


def test_images_must_match_and_missing_images_are_not_equal():
    rows = arms()
    rows[1]["eyecatcher_id"] = "other"
    assert not MODULE.select_pairs(rows)[0]
    for row in rows:
        row["eyecatcher_id"] = ""
    assert not MODULE.select_pairs(rows)[0]


def test_arm_order_does_not_follow_winner_and_no_sales_label():
    rows = arms()
    rows[0]["clicks"] = "100"
    pair = MODULE.select_pairs(list(reversed(rows)))[0][0]
    assert pair["a"]["copy_text"] == "A"
    assert pair["observed"]["difference_b_minus_a_pp"] < 0
    assert pair["revenue"] is None
    assert not pair["eligible_for_cosmetics_sales_prediction"]


def test_uncertainty_handles_equal_and_zero_clicks():
    for clicks in [0, 20]:
        arm = {"clicks": clicks, "impressions": 1000}
        result = MODULE.comparison(arm, arm)
        assert result["difference_b_minus_a_pp"] == 0
        assert result["interval_includes_zero"]
        low, high = result["difference_95_interval_pp"]
        assert low < 0 < high
