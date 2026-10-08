# Model Card: Cosmetic Ad Judge QLoRA

## 1. 모델 개요
- **Base Model**: `Qwen/Qwen2.5-3B-Instruct`
- **Tuning Method**: 4-bit QLoRA (PEFT)
- **목적**: 화장품 광고 문구 위반 여부 (0: 가능, 1: 조건부, 2: 불가) 및 위반 유형 정형 분류

## 2. 하이퍼파라미터
- LoRA Rank (r): 16
- LoRA Alpha: 32
- Target Modules: `q_proj`, `v_proj`, `k_proj`, `o_proj`
- Learning Rate: 2e-4
- Batch Size: 4 (Gradient Accumulation 4)
- Epochs: 3

## 3. 평가 결과 (Holdout Set)
| 지표 | Baseline (Rule) | GPT Few-shot | QLoRA Fine-tuned |
| :--- | :---: | :---: | :---: |
| 판정 정확도 (Accuracy) | TBD | TBD | TBD |
| 위반유형 Macro-F1 | TBD | TBD | TBD |
| 치명적 오류 (불가 -> 가능 판정) | TBD | TBD | TBD |
| 문구당 추론 지연시간 (Latency) | TBD | TBD | TBD |
