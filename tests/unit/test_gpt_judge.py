"""Judge input/output contracts, no paid calls or golden-set examples."""
import json

import pytest
from pydantic import ValidationError

from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.models.gpt_judge import GPTJudgeModel, JudgeOutput
from cosmetic_agent.models.rule_judge import RuleJudgeModel
from cosmetic_agent.workflow.nodes import judge_claim_node


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


OUTPUT = {"model_level": 1, "violation_type": "실증필요", "claim_type": "보습",
          "confidence": 0.5, "rationale": "시험 조건 추가 확인"}


def test_product_evidence_reaches_model_but_labels_do_not():
    llm = FakeLLM(OUTPUT)
    product = {"category": "일반", "name": "fixture", "owned_evidence": [{"value": "fixture evidence"}],
               "ground_truth_level": 2, "notes": "hidden answer"}
    model = GPTJudgeModel(llm=llm)
    result = judge_claim_node({"copy_text": "fixture copy", "product": product}, model)
    payload = json.loads(llm.messages[1][1])
    assert payload["product"]["owned_evidence"] == product["owned_evidence"]
    assert "ground_truth_level" not in payload["product"]
    assert "hidden answer" not in llm.messages[1][1]
    assert result["level"] == 1


@pytest.mark.parametrize("changes", [
    {"model_level": 3}, {"confidence": 1.1}, {"violation_type": "invented"},
    {"model_level": 0}, {"rationale": ""},
])
def test_invalid_output_is_not_a_success(changes):
    with pytest.raises(ValidationError):
        GPTJudgeModel(llm=FakeLLM({**OUTPUT, **changes})).judge("fixture", "일반")


def test_model_object_output_and_failure():
    assert GPTJudgeModel(llm=FakeLLM(JudgeOutput(**OUTPUT))).judge("fixture", "일반")["model_level"] == 1
    with pytest.raises(RuntimeError):
        GPTJudgeModel(llm=FakeLLM(RuntimeError("offline"))).judge("fixture", "일반")


def test_rule_floor_preserves_reason_and_legacy_adapter():
    model = GPTJudgeModel(llm=FakeLLM({**OUTPUT, "model_level": 0, "violation_type": "없음"}))
    state = {"copy_text": "fixture", "product": {"category": "일반"},
             "rule_level": 2, "rule_hits": [{"type": "의약품오인"}]}
    result = judge_claim_node(state, model)
    assert result["level"] == 2
    assert result["violation_type"] == "의약품오인"
    assert RuleJudgeModel(RuleEngine()).judge_product("피부 재생", state["product"])["model_level"] == 2
