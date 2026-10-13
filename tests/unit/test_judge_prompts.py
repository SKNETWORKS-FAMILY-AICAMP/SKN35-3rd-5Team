"""판정 프롬프트: few-shot 구성, 골든셋 누수 방지, 출력 계약."""
import json

import pytest

from cosmetic_agent.common.config import settings
from cosmetic_agent.models.gpt_judge import GPTJudgeModel, JudgeOutput
from cosmetic_agent.models.judge_prompts import JUDGE_FEW_SHOTS, build_judge_messages


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return self.result


OUT = {"model_level": 2, "violation_type": "의약품오인", "claim_type": "장벽", "confidence": 0.9, "rationale": "재생"}


def _golden_texts() -> set[str]:
    texts = set()
    for path in (settings.DEV_SET_PATH, settings.HOLDOUT_SET_PATH):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                texts.add(json.loads(line)["copy_text"].replace(" ", ""))
    return texts


def test_few_shot_examples_are_valid_and_not_from_golden_set():
    golden = _golden_texts()
    for ex in JUDGE_FEW_SHOTS:
        JudgeOutput.model_validate(ex["output"])
        assert ex["copy_text"].replace(" ", "") not in golden


def test_message_layout():
    zero = build_judge_messages("문구", {"category": "일반"})
    few = build_judge_messages("문구", {"category": "일반"}, few_shot=True)
    assert len(zero) == 2 and zero[0][0] == "system"
    assert len(few) == 2 + 2 * len(JUDGE_FEW_SHOTS)
    assert json.loads(few[-1][1])["copy_text"] == "문구"


@pytest.mark.parametrize("few_shot,version", [(False, "judge-zero-shot-v2"), (True, "judge-few-shot-v2")])
def test_gpt_judge_uses_prompt_module(few_shot, version):
    llm = FakeLLM(OUT)
    res = GPTJudgeModel(llm=llm, few_shot=few_shot).judge_product("피부 재생", {"category": "일반", "notes": "숨김"})
    assert res["prompt_version"] == version and res["model_level"] == 2
    assert "숨김" not in llm.messages[-1][1]
