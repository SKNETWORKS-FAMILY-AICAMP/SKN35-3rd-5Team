"""
[finetune/dataset/validate_leakage.py]
Train 세트와 Dev/Holdout 평가 세트 간의 데이터 누수(Data Leakage)를 점검하는 스크립트.
"""
from pathlib import Path


def check_dataset_leakage(train_file: Path, dev_file: Path, holdout_file: Path) -> bool:
    """동일 원본 문구나 유사 문구가 분할 세트 간에 섞여 있는지 검사합니다."""
    print("[finetune] 데이터 누수 검사 중...")
    # TODO (팀원 구현 영역):
    # n-gram 또는 자카드 유사도로 train과 dev/holdout 간 중복율 0% 검증
    return True


if __name__ == "__main__":
    check_dataset_leakage(
        Path("finetune/dataset/train.jsonl"),
        Path("data/golden_set/dev.jsonl"),
        Path("data/golden_set/holdout.jsonl"),
    )
