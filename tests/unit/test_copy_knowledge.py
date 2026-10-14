"""광고문 생성 재료(성분 카드·표현 각도·사후 점검) 단위 테스트."""
import random

import pytest

from cosmetic_agent.domain.copy_knowledge import (
    build_generation_knowledge,
    case_phrases,
    ingredient_card,
    material_claim_notes,
    origin_phrase,
)
from cosmetic_agent.models.generation_prompts import build_generation_prompt

GENERAL = {"category": "일반", "functional_type": None, "owned_evidence": []}
WRINKLE = {"category": "기능성", "functional_type": "주름 개선", "owned_evidence": [],
           "key_ingredients": ["아데노신", "팔미토일펜타펩타이드-4", "호호바씨오일"]}


@pytest.mark.parametrize("definition, expected", [
    ("이 원료는 병풀 (Centella asiatica)의 전초에서 추출한 것이다.", "병풀 전초에서 추출한 원료"),
    ("이 원료는 티트리 (Melaleuca alternifolia)의 잎을 증류하여 얻은 오일이다.", "티트리 잎에서 얻은 원료"),
    ("이 원료는 사막 관목인 호호바 (Simmondsia Chinensis) 씨에서 추출하거나 압착하여 만든 불휘발성 오일에서 얻은 물질이다.", "호호바 씨에서 얻은 원료"),
    ("이 원료는 다음의 구조를 갖는 헤테로고리 방향족 아마이드이다.", None),
])
def test_origin_phrase_reads_only_clear_sources(definition, expected):
    assert origin_phrase(definition) == expected


def test_card_separates_notified_ingredient_by_product_type():
    # 같은 나이아신아마이드라도 미백 기능성 제품이 아니면 함유 사실만
    assert "함유 사실만" in ingredient_card("나이아신아마이드", GENERAL)
    whitening = {"category": "기능성", "functional_type": "피부 미백"}
    assert "심사 문구와 연결 가능" in ingredient_card("나이아신아마이드", whitening)
    assert "Centella Asiatica Extract" in ingredient_card("병풀추출물", GENERAL)


def test_knowledge_block_assigns_different_angles_and_origin():
    product = dict(GENERAL, key_ingredients=["병풀추출물", "판테놀"])
    block = build_generation_knowledge(product, "SNS", random.Random(0))
    angles = [line for line in block.splitlines() if line.startswith(("- strong:", "- balanced:", "- safe:"))]
    assert len(angles) == 3 and len({a.split("—")[0].split(":")[1] for a in angles}) == 3
    assert "성분 유래 스토리" in block  # 유래 정보가 있으면 반드시 한 후보에 배정
    assert "[채널 문법 - SNS]" in block


def test_case_phrases_keep_only_violation_quotes():
    phrases = case_phrases()
    assert "피부재생" in phrases
    assert not any("+" in p or "browser" in p for p in phrases)


@pytest.mark.parametrize("text", [
    "차나무 잎에서 추출한 녹차의 힘으로 피부를 깨끗하게",
    "자연 그대로의 샴푸",
    "자연이 주는 부드러움을 느껴보세요",
    "아데노신 및 팔미토일펜타펩타이드-4와 같은 기능성 성분",
    "자연에서 유래한 아데노신을 담은 세럼",
    "#주름개선 #피부탄력",
])
def test_material_mistakes_are_sent_back(text):
    assert material_claim_notes(text, WRINKLE)


@pytest.mark.parametrize("text", [
    "주름 개선 기능성 성분 아데노신 함유, 피부의 주름 개선에 도움",
    "호호바 씨에서 얻은 호호바씨오일을 담은 세럼",
    "Adenosine, Palmitoyl Pentapeptide-4 함유. 성분을 숨기지 않는 세럼",
])
def test_material_facts_pass(text):
    assert not material_claim_notes(text, WRINKLE)


def test_generation_prompt_carries_knowledge_block():
    prompt = build_generation_prompt(
        instruction="광고 문구", product=WRINKLE, channel="SNS", tone="담백한", length="한 줄",
        keywords=[], evidence_text="", knowledge="[성분 카드]\n- 아데노신",
    )
    assert "[쓸 수 있는 재료" in prompt and "- 아데노신" in prompt


def test_clean_copy_strips_formatting_artifacts():
    from cosmetic_agent.models.project_copy_generator import clean_copy

    assert clean_copy("**제목**\n살리실릭애씨드 함유! [제품을 보여주며 감탄]") == "제목\n살리실릭애씨드 함유!"
    assert material_claim_notes("자연을 담아낸 촉촉한 케어", GENERAL)
