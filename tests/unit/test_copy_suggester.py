"""문구 제안기 단위 테스트 (LLM 은 가짜 객체로 대체, 네트워크 호출 없음)."""
from cosmetic_agent.models.copy_suggester import DEFAULT_NEXT_TEST, CopySuggester, SuggestionOutput
from cosmetic_agent.models.prompts import build_suggest_user_prompt
from cosmetic_agent.workflow.nodes import suggest_copy_node

PRODUCT = {
    "product_id": "TEST_1",
    "name": "테스트 수분 크림",
    "category": "일반",
    "functional_type": None,
    "owned_evidence": [{"test_type": "인체적용시험", "item": "보습", "value": "8주 사용 후 수분량 35% 증가"}],
}


class FakeLLM:
    def __init__(self, output):
        self.output = output
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def test_prompt_contains_evidence_and_retry_feedback():
    prompt = build_suggest_user_prompt(
        copy_text="원문",
        product=PRODUCT,
        owned_evidence=PRODUCT["owned_evidence"],
        level=1,
        violation_type="실증필요",
        previous_suggestion="이전 문구",
        verify_note="검증 실패: 숫자날조",
    )
    assert "35% 증가" in prompt
    assert "조건부" in prompt
    assert "숫자날조" in prompt


def test_conditional_level_always_has_next_test():
    llm = FakeLLM(SuggestionOutput(suggestion="촉촉하게 가꿔 줍니다", next_test=None))
    result = CopySuggester(llm=llm).suggest(copy_text="원문", product=PRODUCT, level=1)
    assert result["suggestion"] == "촉촉하게 가꿔 줍니다"
    assert result["next_test"] == DEFAULT_NEXT_TEST


def test_llm_failure_returns_none_suggestion():
    result = CopySuggester(llm=FakeLLM(RuntimeError("no key"))).suggest(copy_text="원문", product=PRODUCT, level=2)
    assert result["suggestion"] is None
    assert "RuntimeError" in result["suggest_error"]


def test_node_passes_verify_note_only_on_retry():
    llm = FakeLLM(SuggestionOutput(suggestion="새 문구"))
    suggester = CopySuggester(llm=llm)
    state = {"copy_text": "원문", "product": PRODUCT, "level": 2, "violation_type": "의약품오인"}

    first = suggest_copy_node(state, suggester)
    assert first["suggestion"] == "새 문구"
    assert "탈락 사유" not in llm.messages[1][1]

    retry_state = {**state, "suggestion": "이전 문구", "verify_passed": False, "verify_note": "검증 실패: X"}
    suggest_copy_node(retry_state, suggester)
    assert "검증 실패: X" in llm.messages[1][1]
