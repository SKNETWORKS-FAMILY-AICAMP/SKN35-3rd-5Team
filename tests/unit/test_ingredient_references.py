from cosmetic_agent.domain.ingredients import (
    compare_profiles,
    matched_references,
    names,
    normalize,
    registry,
)
from cosmetic_agent.domain.schemas import ProductCard
from cosmetic_agent.models.prompts import build_suggest_user_prompt


def test_aliases_and_common_base_do_not_establish_reference_match():
    assert normalize("Squalane") == normalize("스쿠알란")
    a = {
        "form": "cream",
        "complete_list": True,
        "delimiter": "comma",
        "ingredient_text": "Water, Glycerin, Squalane",
        "focus_ingredients": ["Squalane"],
    }
    b = dict(
        a,
        ingredient_text="Water, Glycerin, Ceramide NP",
        focus_ingredients=["Ceramide NP"],
    )
    comparison = compare_profiles(a, b)
    assert len(comparison["shared"]) == 2
    assert not comparison["eligible"]
    assert comparison["efficacy_equivalence"] is None


def test_actual_reference_requires_focus_and_form_match_and_excludes_self():
    target, accepted, excluded = matched_references("PUBLIC_KIEHLS_UFC")
    assert accepted[0]["reference_id"] == "MKT_BIOSSANCE_OMEGA"
    assert accepted[0]["comparison"]["shared_focus"] == ["스쿠알란"]
    assert "세라마이드엔피" in accepted[0]["comparison"]["reference_only_focus"]
    assert len(accepted[0]["comparison"]["shared"]) == 8
    assert excluded[0]["reference_id"] == "MKT_KIEHLS_BARRIER"
    assert not compare_profiles(target, dict(accepted[0]["profile"], form="shampoo"))[
        "eligible"
    ]
    assert not matched_references("PROD_001")[1]


def test_prompt_keeps_external_reference_out_of_owned_evidence():
    target = registry()["profiles"]["MKT_KIEHLS_UFC"]
    product = ProductCard(
        product_id="PUBLIC_KIEHLS_UFC",
        name=target["name"],
        category="일반",
        ingredients=sorted(names(target)),
    )
    prompt = build_suggest_user_prompt(
        copy_text="크림",
        product=product.model_dump(),
        owned_evidence=[],
        level=1,
        violation_type="실증필요",
    )
    assert "공통 주요 소구 성분: 스쿠알란" in prompt
    assert "규정/실증 근거 아님" in prompt
    assert "보유 근거 없음" in prompt
    assert "현재 전성분에서 확인되지 않은" in prompt
    assert "42%" not in prompt and "44%" not in prompt
