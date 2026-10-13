import json

import pytest

from eval.run_eval import load_cases, run_evaluation, summarize


def test_failures_are_counted_as_misses_not_dropped():
    records = [
        {"truth": 0, "predicted": 0, "latency_ms": 1},
        {"truth": 1, "predicted": 1, "latency_ms": 1},
        {"truth": 2, "predicted": None, "latency_ms": 1},
    ]
    metrics = summarize(records)
    assert metrics["accuracy_all_cases"] == pytest.approx(2 / 3)
    assert metrics["failed"] == 1
    assert metrics["level2_recall"] == 0
    assert metrics["macro_f1_fixed_3_classes"] == pytest.approx(2 / 3)


def test_dangerous_miss_and_overflag_are_separate():
    result = summarize([{"truth": 2, "predicted": 0, "latency_ms": 0},
                        {"truth": 0, "predicted": 1, "latency_ms": 0}])
    assert result["critical_errors_2_to_0"] == 1
    assert result["overflag_rate_on_level0"] == 1


def test_holdout_is_opt_in():
    with pytest.raises(ValueError, match="Holdout"):
        run_evaluation("holdout")


def test_duplicate_ids_are_rejected(tmp_path):
    case = {"id": "fixture", "split": "dev", "ground_truth_level": 0,
            "copy_text": "fixture", "product_id": "p"}
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case) + "\n" + json.dumps(case), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(path, {"p": {}}, "dev")


def test_type_accuracy_and_detection_rate():
    records = [
        {"truth": 2, "truth_type": "의약품오인", "predicted": 2, "violation_type": "의약품오인", "latency_ms": 0},
        {"truth": 2, "truth_type": "범위이탈", "predicted": 2, "violation_type": "의약품오인", "latency_ms": 0},
        {"truth": 1, "truth_type": "실증필요", "predicted": 0, "violation_type": "없음", "latency_ms": 0},
        {"truth": 0, "truth_type": "없음", "predicted": 0, "violation_type": "없음", "latency_ms": 0},
    ]
    m = summarize(records)
    assert m["violation_detection_rate"] == pytest.approx(2 / 3)
    assert m["violation_type_accuracy"] == pytest.approx(1 / 3)
    assert m["confusion_truth_x_pred"][1][0] == 1
