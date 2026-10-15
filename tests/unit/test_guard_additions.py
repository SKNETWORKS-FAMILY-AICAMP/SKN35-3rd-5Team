"""생성 결과에서 검증을 통과했던 위험 표현(예방·깊은 보습·고민 끝)을 거르는지, 평범한 문장은 그대로 두는지."""
import pytest

from cosmetic_agent.domain.verifier import CopyVerifier

VERIFIER = CopyVerifier()


@pytest.mark.parametrize("text", [
    "수분크림으로 건조함을 예방하세요.",
    "가벼운 젤, 깊은 보습",
    "피부 속 깊이 채워지는 수분",
    "두피 고민, 이젠 루트 리바이탈 샴푸로 끝!",
    "각질 고민 종결!",
])
def test_risky_generation_phrases_are_caught(text):
    assert VERIFIER.inspect(text, []), text


@pytest.mark.parametrize("text", [
    "한 번의 펌핑으로 세안 끝!",
    "은은한 향이 오래 남는 바디워시",
    "끈적임 없이 산뜻하게 마무리됩니다.",
    "손바닥에서 금방 일어나는 거품",
    "백탁 부담 없이 매끄럽게 마무리",
])
def test_plain_phrases_pass(text):
    assert not VERIFIER.inspect(text, []), [str(i) for i in VERIFIER.inspect(text, [])]
