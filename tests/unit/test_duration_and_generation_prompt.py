from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.generation.ingredients import ingredient_profiles
from cosmetic_agent.models.generation_prompts import GENERATION_SYSTEM_PROMPT

TONER = {"name": "수딩 촉촉 워터 토너", "category": "일반", "key_ingredients": ["히알루론산", "판테놀"], "owned_evidence": []}
TESTED = dict(TONER, owned_evidence=[{"test_type": "인체적용시험", "item": "피부 수분량", "value": "8시간 후 피부 수분량 32% 증가"}])


def test_duration_claims_need_a_timed_test():
    engine = RuleEngine()
    for text in ["하루 종일 촉촉한 토너", "8시간 동안 촉촉함", "밤사이 촉촉하게"]:
        assert engine.evaluate(text, TONER)["level"] == 1
        assert engine.evaluate(text, TESTED)["level"] == 0
    rich = "세안 직후, 비어 있는 수분부터\n히알루론산이 수분을 머금고 판테놀이 건조해진 피부를 편안하게 가꿔줍니다."
    assert engine.evaluate(rich, TONER)["level"] == 0


def test_prompt_asks_for_concrete_copy_within_limits():
    for phrase in ["[구체성]", "[일반 화장품 효능 어휘]", "[시험이 있을 때의 구성]", "'짧은 문단'은 headline + supporting_copy 2~3문장"]:
        assert phrase in GENERATION_SYSTEM_PROMPT


def test_ingredient_cards_carry_benefit_phrases():
    names = {p["name"]: p for p in ingredient_profiles(TONER)}
    assert set(names) == {"히알루론산", "판테놀"}
    assert all(p.get("benefit_phrases") for p in names.values())
