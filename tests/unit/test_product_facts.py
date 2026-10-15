"""제품 사실(질감·향·용기 등)과 제형 사용감 어휘가 생성 재료로 들어가는지."""
import json
import random

import pytest

from cosmetic_agent.common.config import ASSETS_DIR
from cosmetic_agent.domain.copy_knowledge import build_generation_knowledge, form_words
from cosmetic_agent.domain.schemas import ProductCard
from cosmetic_agent.models.generation_prompts import build_generation_prompt

BASE = {"product_id": "T1", "name": "하이드라 워터 크림", "category": "일반", "owned_evidence": []}


def _prompt(product: dict) -> str:
    return build_generation_prompt(instruction="광고 문구", product=product, channel="SNS", tone="", length="짧은 문단",
                                   keywords=[], evidence_text="")


def test_facts_survive_schema_and_reach_prompt():
    card = ProductCard.model_validate({**BASE, "texture": "물처럼 가벼운 젤 크림", "package": "50ml 튜브"})
    prompt = _prompt(card.model_dump())
    assert "- 제형·질감: 물처럼 가벼운 젤 크림" in prompt and "- 용량·용기: 50ml 튜브" in prompt
    assert "향:" not in prompt  # 입력하지 않은 칸은 넣지 않는다


def test_missing_facts_are_marked_unconfirmed():
    assert "미확인 (지어내지 말 것)" in _prompt(BASE)


@pytest.mark.parametrize("name, form", [
    ("데일리 워터 선크림", "선크림"), ("허니 립밤", "립"), ("하이드로겔 수분 마스크팩", "마스크팩"),
    ("하이드라 워터 크림", "젤·수분크림"), ("시카 배리어 크림", "크림·밤"), ("스칼프 탈모 앰플", "헤어"),
    ("클리어 바디워시", "바디"), ("나의 화장품", ""),
])
def test_form_words_pick_the_most_specific_form(name, form):
    assert form_words({"name": name})[0] == form


def test_form_vocab_has_no_words_the_verifier_removes():
    banned = ("흡수", "스며", "침투", "듬뿍", "풍부", "농축", "진정", "고함량")
    words = [w for row in json.loads((ASSETS_DIR / "form_vocab.json").read_text(encoding="utf-8"))["forms"] for w in row["words"]]
    assert words and not [w for w in words if any(b in w for b in banned)]


def test_knowledge_includes_form_vocab_only_when_form_known():
    assert "[제형 사용감 어휘 - 젤·수분크림" in build_generation_knowledge(BASE, rng=random.Random(0))
    assert "[제형 사용감 어휘" not in build_generation_knowledge({**BASE, "name": "나의 화장품"}, rng=random.Random(0))


def test_demo_products_have_facts():
    for name in ("mock_products.json", "sample_products.json"):
        for row in json.loads((ASSETS_DIR / name).read_text(encoding="utf-8")):
            assert row.get("texture") and row.get("usage_step"), row["product_id"]


def test_copy_bank_prefers_same_form_and_feeds_knowledge(monkeypatch):
    import cosmetic_agent.domain.copy_knowledge as ck

    rows = ({"type": "scene", "form": "젤·수분크림", "text": "출근 전 거울 앞 30초"},
            {"type": "scene", "form": "선크림", "text": "외출 직전 현관 앞"},
            {"type": "template", "form": "", "text": "{시간대}의 {제형} 한 겹"})
    monkeypatch.setattr(ck, "_bank_rows", lambda: rows)
    monkeypatch.setenv("COPY_BANK", "1")
    bank = ck.copy_bank(BASE, random.Random(0))
    assert bank == {"scene": ["출근 전 거울 앞 30초"], "template": ["{시간대}의 {제형} 한 겹"]}
    assert "- 사용 장면: 출근 전 거울 앞 30초" in build_generation_knowledge(BASE, rng=random.Random(0))
    monkeypatch.delenv("COPY_BANK")
    assert "[수집 표현 재료" not in build_generation_knowledge(BASE, rng=random.Random(0))  # 기본은 꺼짐


def test_build_copy_bank_filters_risky_long_and_duplicate_items():
    import importlib.util

    spec = importlib.util.spec_from_file_location("bcb", ASSETS_DIR.parents[1] / "scripts" / "build_copy_bank.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    kept, dropped = module.clean([
        {"type": "scene", "form": "크림", "text": "자기 전 마지막 한 겹"},
        {"type": "scene", "form": "크림", "text": "자기 전 마지막 한 겹"},
        {"type": "sensory_vocab", "form": "크림", "text": "피부 속까지 스며드는"},
        {"type": "scene", "form": "", "text": "여드름 고민 끝", "risk": True},
        {"type": "template", "form": "", "text": "가" * 80},
    ])
    assert [k["text"] for k in kept] == ["자기 전 마지막 한 겹"] and kept[0]["form"] == "크림·밤"
    assert dropped["dup"] == 1 and dropped["words"] == 1 and dropped["risk"] == 1 and dropped["length"] == 1


def test_market_tags_only_on_mz_channels_and_carry_no_rank_or_numbers():
    import re

    from cosmetic_agent.domain.copy_knowledge import market_tags

    sun = {**BASE, "name": "데일리 워터 선크림"}
    assert "물막선크림" in market_tags(sun)
    assert "올리브영 랭킹 태그어" in build_generation_knowledge(sun, channel="SNS", rng=random.Random(0))
    assert "올리브영 랭킹 태그어" not in build_generation_knowledge(sun, channel="상세페이지", rng=random.Random(0))
    tags = [t for row in json.loads((ASSETS_DIR / "form_vocab.json").read_text(encoding="utf-8"))["forms"] for t in row["market_tags"]]
    assert not [t for t in tags if re.search(r"1등|1위|연속|\d+\s*(시간|%|배)|진정|미백|장벽|탈모|트러블|여드름|특허", t)]


def test_quick_generation_finds_form_from_request_text():
    from cosmetic_agent.domain.copy_knowledge import with_request_form

    draft = {"product_id": "generation_draft", "name": "나의 화장품", "category": "일반", "owned_evidence": []}
    assert with_request_form(draft, "가벼운 선크림 광고 만들어줘")["form"] == "선크림"
    assert with_request_form(draft, "수분크림 인스타 문구")["form"] == "젤·수분크림"
    assert "form" not in with_request_form(draft, "광고 문구 만들어줘")  # 단서가 없으면 그대로
    named = {**draft, "name": "허니 립밤"}
    assert with_request_form(named, "선크림처럼 가볍게") is named  # 제품명으로 알 수 있으면 요청 문장보다 우선
    assert "[제형 사용감 어휘 - 선크림" in build_generation_knowledge(
        with_request_form(draft, "선크림 광고"), channel="SNS", rng=random.Random(0))


def test_placeholder_name_is_not_given_as_product_name():
    prompt = _prompt({**BASE, "name": "나의 화장품"})
    assert "- 제품명: 미정" in prompt and "나의 화장품" not in prompt


def test_soften_keeps_sentence_when_removing_worry_free():
    from cosmetic_agent.generation.nodes import _soften

    assert _soften("백탁 걱정 없이 매끄럽게 마무리") == "백탁 부담 없이 매끄럽게 마무리"
    assert _soften("완벽하게 촉촉한 마무리") == "촉촉한 마무리"
    # 문장 끝 부사를 지워도 '전에도 .'처럼 공백이 남지 않는다
    assert _soften("끈적임 없이 가볍게, 메이크업 전에도 완벽하게. #수분크림") == "끈적임 없이 가볍게, 메이크업 전에도. #수분크림"
