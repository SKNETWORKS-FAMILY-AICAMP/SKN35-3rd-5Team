"""
[eval/run_eval.py]
골든셋(Dev/Holdout)을 대상으로 /review API를 호출하여 베이스라인 성능 비교표를 출력하는 스크립트.
"""
import argparse
from pathlib import Path
import json


def run_evaluation(split: str = "dev"):
    data_path = Path(f"data/golden_set/{split}.jsonl")
    if not data_path.exists():
        print(f"[eval] 평가 데이터가 존재하지 않습니다: {data_path}")
        return

    print(f"=== [{split.upper()} SET] 에이전트 성능 평가 시작 ===")
    # TODO (팀원 구현 영역):
    # 1. jsonl 로드
    # 2. ReviewService 또는 HTTP POST /review 호출
    # 3. accuracy, critical_error, latency 측정 후 결과 표 출력
    print("평가 완료! 결과 레포트를 생성합니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=str, default="dev", choices=["dev", "holdout"])
    args = parser.parse_args()
    run_evaluation(args.split)
