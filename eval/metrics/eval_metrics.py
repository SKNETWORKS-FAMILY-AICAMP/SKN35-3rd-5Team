"""
[eval/metrics/eval_metrics.py]
판정 모델 및 RAG 검색 성능 평가 지표 계산 함수 모음.
"""


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


def calculate_macro_f1(predictions: list[int | None], ground_truths: list[int], labels: tuple[int, ...] = (0, 1, 2)) -> float:
    """수준(0·1·2) 고정 3클래스 Macro-F1. 예측 실패(None)는 놓친 것으로 계산 (eval/run_eval.py 와 같은 기준)"""
    f1s = []
    for label in labels:
        tp = sum(p == label and g == label for p, g in zip(predictions, ground_truths))
        fp = sum(p == label and g != label for p, g in zip(predictions, ground_truths))
        fn = sum(p != label and g == label for p, g in zip(predictions, ground_truths))
        f1s.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return sum(f1s) / len(labels)


def calculate_detection_rate(predictions: list[int | None], ground_truths: list[int]) -> float:
    """위반 문구(정답 1·2) 중 1 이상으로 잡아낸 비율"""
    targets = [p for p, g in zip(predictions, ground_truths) if g >= 1]
    return sum(p in (1, 2) for p in targets) / len(targets) if targets else 0.0
