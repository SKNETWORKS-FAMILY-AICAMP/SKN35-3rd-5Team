"""
[finetune/dataset/generate_synthetic.py]
금지어 사전 및 적발 사례 기반으로 LLM을 활용해 학습용 문구를 증강 생성하는 스크립트.
"""
from pathlib import Path


def generate_synthetic_samples(input_banned_terms: Path, output_file: Path, target_count: int = 300):
    """금지 표현을 바탕으로 현실적인 마케팅 문구를 생성합니다.

    주의: 생성 후 반드시 사람이 검수(Human-in-the-loop)하여 라벨의 정합성을 확인해야 합니다.
    """
    print(f"[finetune] {input_banned_terms} 기반 {target_count}개 합성 데이터 생성 시작")
    # TODO (팀원 구현 영역):
    # GPT-4o-mini 호출로 문구 변형 생성 및 JSONL 저장
    pass


if __name__ == "__main__":
    generate_synthetic_samples(
        Path("data/assets/banned_terms.json"),
        Path("finetune/dataset/train.jsonl"),
    )
