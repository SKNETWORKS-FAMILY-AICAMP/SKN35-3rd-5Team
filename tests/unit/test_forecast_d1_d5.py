import importlib.util
import json
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sales_forecast_reference"
SPEC = importlib.util.spec_from_file_location(
    "forecast_d1_d5", ROOT / "scripts" / "build_forecast_d1_d5.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_penalty_schedule_preserves_law_item_sanction_and_blank_fourth_column():
    data = json.loads((OUT / "penalty_schedule.json").read_text(encoding="utf-8"))
    groups = {g["schedule_id"]: g for g in data["schedules"]}
    mapping = {m["rule_item"]: m for m in data["law_id_mapping"]}
    assert len(mapping) == 11
    for item in ["2가", "2나", "2카"]:
        group = groups[mapping[item]["schedule_id"]]
        assert group["months_by_offense"] == [3, 6, 9]
        assert group["offense_columns"][3]["months"] is None
        assert (
            group["offense_columns"][3]["source_cell_status"] == "blank_requires_review"
        )
        assert group["sanction"]["광고"] == "해당 품목 광고업무정지"
        assert group["sanction"]["표시"] == "해당 품목 판매업무정지"
        assert group["verified_against_raw"] is True
    for item in ["2다", "2라", "2마", "2바", "2사", "2아", "2자", "2차"]:
        assert groups[mapping[item]["schedule_id"]]["months_by_offense"] == [
            2,
            4,
            6,
            12,
        ]
    assert data["detection_probability"] is None and data["revenue_loss"] is None
    assert not data["mapping_policy"]["violation_type_only_lookup_allowed"]
    assert {x["item"] for x in data["general_criteria"]} >= {
        "1가",
        "1다·라",
        "1마",
        "1자1",
        "1자2",
    }
    assert data["source"]["sha256"] == MODULE.digest(MODULE.LAW)


def test_d5_quantiles_match_independent_statistics_calculation():
    data = json.loads(
        (OUT / "copy_effect_size_distribution.json").read_text(encoding="utf-8")
    )
    rows = [
        json.loads(line)
        for line in MODULE.PAIRS.read_text(encoding="utf-8").splitlines()
    ]
    values = [
        abs(
            (r["b"]["clicks"] * r["a"]["impressions"])
            / (r["b"]["impressions"] * r["a"]["clicks"])
            - 1
        )
        for r in rows
    ]
    expected = statistics.quantiles(values, n=4, method="inclusive")
    actual = data["absolute_relative_ctr_change"]["quantiles"]
    assert [actual["p25"], actual["median"], actual["p75"]] == pytest.approx(expected)
    assert actual["p90"] == pytest.approx(
        statistics.quantiles(values, n=10, method="inclusive")[8]
    )
    assert data["input_pair_count"] == 148
    assert data["interval_zero_exclusion"]["count"] == 29
    assert data["interval_zero_exclusion"]["proportion"] == pytest.approx(29 / 148)
    assert data["direction_counts"] == {"b_higher": 71, "b_lower": 77, "equal": 0}
    assert not data["automatic_cosmetics_revenue_transfer_allowed"]
    assert data["cosmetics_revenue_uplift"] is None


def test_zero_baseline_and_boundary_zero_are_not_fabricated_effects():
    row = {
        "a": {"impressions": 1000, "clicks": 0},
        "b": {"impressions": 1000, "clicks": 5},
        "observed": {"difference_95_interval_pp": [0, 1]},
    }
    summary = MODULE.summarize_pairs([row])
    assert summary["relative_change_defined_count"] == 0
    assert summary["zero_baseline_pairs_excluded_from_relative_distribution"] == 1
    assert all(
        v is None for v in summary["absolute_relative_ctr_change"]["quantiles"].values()
    )
    assert summary["interval_zero_exclusion"]["count"] == 0
    assert MODULE.quantile([0, 10], 0.25) == 2.5
