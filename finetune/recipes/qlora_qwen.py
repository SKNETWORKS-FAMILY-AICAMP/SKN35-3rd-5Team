"""
[finetune/recipes/qlora_qwen.py]
Colab / 로컬 GPU 환경에서 Qwen2.5 계열 모델을 4bit QLoRA로 파인튜닝하는 레시피 스크립트.
"""


def train_qlora():
    print("[QLoRA] 파인튜닝 스크립트 시작")
    # TODO (팀원 구현 영역):
    # 1. BitsAndBytes 4-bit 양자화 설정 (nf4)
    # 2. Qwen2.5-3B-Instruct 베이스 모델 로드
    # 3. LoRAConfig (r=16, lora_alpha=32, target_modules=['q_proj', 'v_proj'])
    # 4. SFTTrainer 학습 실행 및 adapters 저장
    pass


if __name__ == "__main__":
    train_qlora()
