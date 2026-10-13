"""Standalone preliminary judge evaluation, NOT full RAG/suggestion evaluation.
Run from repo root:
    uv run python -m eval.run_eval --backend rule --split dev        # R0 규칙
    uv run python -m eval.run_eval --backend gpt --split dev         # R1 GPT zero-shot (유료)
    uv run python -m eval.run_eval --backend gpt-few --split dev     # R2 GPT few-shot  (유료)
    uv run python -m eval.run_eval --backend rule gpt gpt-few        # 여러 개 비교표
GPT evaluation is billable. Holdout needs explicit --allow-holdout.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cosmetic_agent.common.config import PROJECT_ROOT, settings
from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.schemas import ProductCard
from cosmetic_agent.models.gpt_judge import GPTJudgeModel, JudgeOutput
from cosmetic_agent.models.rule_judge import RuleJudgeModel


def load_cases(path: Path, products: dict[str, dict[str, Any]], split: str) -> list[dict[str, Any]]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for case in cases:
        if case["id"] in seen:
            raise ValueError("Duplicate case ID")
        seen.add(case["id"])
        if case["split"] != split or case["ground_truth_level"] not in (0, 1, 2):
            raise ValueError("Invalid split or level")
        if case["product_id"] not in products or not case["copy_text"].strip():
            raise ValueError("Unknown product or empty copy")
    if not cases:
        raise ValueError("Empty dataset")
    return cases


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    truth = [row["truth"] for row in records]
    predicted = [row.get("predicted") for row in records]
    f1s = []
    for level in (0, 1, 2):
        tp = sum(p == level and g == level for p, g in zip(predicted, truth))
        fp = sum(p == level and g != level for p, g in zip(predicted, truth))
        fn = sum(p != level and g == level for p, g in zip(predicted, truth))
        f1s.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    unsafe = sum(g == 2 for g in truth)
    safe = sum(g == 0 for g in truth)
    violations = [row for row in records if row["truth"] >= 1]
    confusion = {g: {**{p: 0 for p in (0, 1, 2)}, "실패": 0} for g in (0, 1, 2)}
    for p, g in zip(predicted, truth):
        confusion[g]["실패" if p is None else p] += 1
    return {
        "total": total,
        "failed": sum(p is None for p in predicted),
        "accuracy_all_cases": sum(p == g for p, g in zip(predicted, truth)) / total if total else 0.0,
        "macro_f1_fixed_3_classes": sum(f1s) / 3,
        "critical_errors_2_to_0": sum(p == 0 and g == 2 for p, g in zip(predicted, truth)),
        "level2_recall": sum(p == 2 and g == 2 for p, g in zip(predicted, truth)) / unsafe if unsafe else None,
        "overflag_rate_on_level0": sum(p in (1, 2) and g == 0 for p, g in zip(predicted, truth)) / safe if safe else None,
        "violation_detection_rate": (
            sum(row.get("predicted") in (1, 2) for row in violations) / len(violations) if violations else None
        ),
        "violation_type_accuracy": (
            sum(row.get("predicted") == row["truth"] and row.get("violation_type") == row.get("truth_type")
                for row in violations) / len(violations) if violations else None
        ),
        "mean_latency_ms": sum(row["latency_ms"] for row in records) / total if total else 0.0,
        "confusion_truth_x_pred": confusion,
    }


def run_evaluation(split: str = "dev", backend: str = "rule", *, allow_holdout: bool = False) -> dict[str, Any]:
    if split == "holdout" and not allow_holdout:
        raise ValueError("Holdout is reserved; use --allow-holdout for final evaluation")
    products = {
        item["product_id"]: ProductCard.model_validate(item).model_dump()
        for item in json.loads(settings.MOCK_PRODUCTS_PATH.read_text(encoding="utf-8"))
    }
    cases = load_cases(PROJECT_ROOT / "data" / "golden_set" / f"{split}.jsonl", products, split)
    if backend in ("gpt", "gpt-few"):
        model = GPTJudgeModel(model_name=settings.OPENAI_MODEL_NAME, few_shot=backend == "gpt-few")
        _ = model.llm  # Fail before starting if the credentials are missing.
    elif backend == "rule":
        model = RuleJudgeModel(RuleEngine())
    else:
        raise ValueError("Unsupported backend")
    records = []
    for case in cases:
        started = time.perf_counter()
        row = {"id": case["id"], "truth": case["ground_truth_level"], "truth_type": case.get("violation_type", "없음")}
        try:
            # Only copy and whitelisted product fields reach the model.
            result = model.judge_product(case["copy_text"], products[case["product_id"]])
            if backend in ("gpt", "gpt-few"):
                JudgeOutput.model_validate({k: v for k, v in result.items() if k != "prompt_version"})
            row.update(predicted=result["model_level"], violation_type=result["violation_type"],
                       rationale=result.get("rationale"))
        except Exception as exc:  # noqa: BLE001 -- record failures, never fabricate a prediction
            row.update(predicted=None, error_type=type(exc).__name__)
        row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        records.append(row)
        if len(records) % 5 == 0 or len(records) == len(cases):
            print(f"Progress: {backend} {len(records)}/{len(cases)}", flush=True)
    report = {
        "scope": "standalone_preliminary_judge_not_RAG",
        "backend": backend, "model": settings.OPENAI_MODEL_NAME if backend.startswith("gpt") else None,
        "prompt_version": getattr(model, "prompt_version", None),
        "split": split, "summary": summarize(records), "records": records,
    }
    output = PROJECT_ROOT / "output" / "eval"
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = output / f"{backend}_{split}_{stamp}.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("Scope:", report["scope"])
    print("Report:", destination)
    return report


BASELINE_NAMES = {"rule": "R0 규칙", "gpt": "R1 GPT zero-shot", "gpt-few": "R2 GPT few-shot"}


def print_comparison(reports: list[dict[str, Any]]) -> None:
    """여러 베이스라인 결과를 한 표로 출력 (발표용)"""
    def pct(x):
        return "-" if x is None else f"{x * 100:.1f}%"
    print()
    print("| 베이스라인 | N | 정확도 | Macro-F1 | 위반 탐지율 | 치명 오판(2→0) | 과잉 경고(0→1·2) | 유형까지 정답 | 실패 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for report in reports:
        m = report["summary"]
        print(f"| {BASELINE_NAMES.get(report['backend'], report['backend'])} | {m['total']} | {pct(m['accuracy_all_cases'])} | "
              f"{m['macro_f1_fixed_3_classes']:.3f} | {pct(m['violation_detection_rate'])} | {m['critical_errors_2_to_0']} | "
              f"{pct(m['overflag_rate_on_level0'])} | {pct(m['violation_type_accuracy'])} | {m['failed']} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev", choices=["dev", "holdout"])
    parser.add_argument("--backend", nargs="+", default=["rule"], choices=list(BASELINE_NAMES))
    parser.add_argument("--allow-holdout", action="store_true")
    args = parser.parse_args()
    reports = [run_evaluation(args.split, backend, allow_holdout=args.allow_holdout) for backend in args.backend]
    if len(reports) > 1:
        print_comparison(reports)
    raise SystemExit(1 if any(r["summary"]["failed"] for r in reports) else 0)
