from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.verifier import CopyVerifier
from cosmetic_agent.generation.ingredients import catalog, ingredient_profiles
from cosmetic_agent.generation.nodes import (
    generate_candidates_node,
    verify_candidates_node,
)


def test_ten_roles_have_traceable_scope_and_no_evidence_transfer():
    cards = catalog()["cards"]
    assert len(cards) == 10 and len({c["ingredient_id"] for c in cards}) == 10
    assert all(c["source_url"].startswith("https://") and c["study_conditions"] for c in cards)
    assert all(c["allowed_as_owned_evidence"] is False and c["allowed_as_regulatory_evidence"] is False for c in cards)
    pdrn = next(c for c in cards if c["ingredient_id"] == "pdrn")
    assert "동물" in pdrn["evidence_kind"] and "미세침" in pdrn["study_conditions"]


def test_only_declared_ingredients_match_with_chemical_boundaries():
    assert ingredient_profiles({"name": "히알루론산 토너", "key_ingredients": []}) == []
    product = {"key_ingredients": ["Sodium Hyaluronate", "Panthenol", "레티놀(0.1%)", "Squalene", "레티날", "PN"]}
    profiles = ingredient_profiles(product)
    assert {p["ingredient_id"] for p in profiles} == {"hyaluronic_acid", "panthenol", "retinol"}
    assert ingredient_profiles({"key_ingredients": ["마데카소사이드"]})[0]["matched_ingredients"] == ["마데카소사이드"]


def test_role_prompt_does_not_add_owned_evidence():
    captured = {}
    class Generator:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return []
    product = {"name": "수딩 토너", "category": "일반", "key_ingredients": ["판테놀"], "owned_evidence": []}
    state = {"product": product, "ingredient_profiles": ingredient_profiles(product),
             "instruction": "데일리 보습 루틴 중심", "channel": "SNS", "tone": "간결한", "length": "한 줄", "keywords": []}
    generate_candidates_node(state, Generator())
    # 성분 역할 카드는 생성 재료 블록의 성분 카드 줄에 I번호로 붙는다
    assert "판테놀" in captured["knowledge"] and "[I1]" in captured["knowledge"]
    assert captured["product"]["owned_evidence"] == []


def test_role_research_does_not_unlock_functional_or_numeric_claims():
    product = {"name": "레티놀 크림", "category": "일반", "key_ingredients": ["레티놀"], "owned_evidence": []}
    state = {"product": product, "ingredient_profiles": ingredient_profiles(product), "drafts": [
        {"text": "주름 개선 크림", "tier": "strong", "ingredient_reference_ids": ["I1"]},
        {"text": "24주 후 주름 90% 개선", "tier": "strong", "ingredient_reference_ids": ["I1"]},
        {"text": "레티놀 함유 크림", "tier": "safe", "ingredient_reference_ids": ["I99"]},
    ]}
    result = verify_candidates_node(state, CopyVerifier(), RuleEngine())
    assert result["candidates"] == [] and len(result["rejected_notes"]) == 3


def test_role_preview_shows_only_current_product_and_full_catalog():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
from app.components.ingredient_roles import render_ingredient_roles
render_ingredient_roles({"key_ingredients": ["히알루론산", "판테놀"]})
''').run()
    assert not app.exception
    assert app.expander[0].label.endswith("2개 연결")
    assert [t.label for t in app.tabs] == ["우리 제품 성분", "지원 성분 10개 보기"]
    assert len(app.get("link_button")) == 2
