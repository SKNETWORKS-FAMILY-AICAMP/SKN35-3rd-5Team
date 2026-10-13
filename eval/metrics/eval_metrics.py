"""
[eval/metrics/eval_metrics.py]
판정 모델 및 RAG 검색 성능 평가 지표 계산 함수 모음.
"""
from typing import Any


def calculate_accuracy(predictions: list[int], ground_truths: list[int]) -> float:
    """판정 Level (0, 1, 2) 일치율"""
    if not ground_truths:
        return 0.0
    correct = sum(p == g for p, g in zip(predictions, ground_truths))
    return correct / len(ground_truths)


def calculate_critical_errors(predictions: list[int], ground_truths: list[int]) -> int:
    """불가(2) 문구를 가능(0)으로 오판한 치명적 위험 건수"""
    return sum(p == 0 and g == 2 for p, g in zip(predictions, ground_truths))


def calculate_hit_at_k(retrieved_ids: list[list[str]], target_ids: list[str], k: int = 4) -> float:
    """RAG 검색 상위 K개 내 정답 조항 포함율 (Hit@K)"""
    if not target_ids:
        return 0.0
    hits = sum(target in retrieved[:k] for retrieved, target in zip(retrieved_ids, target_ids))
    return hits / len(target_ids)
