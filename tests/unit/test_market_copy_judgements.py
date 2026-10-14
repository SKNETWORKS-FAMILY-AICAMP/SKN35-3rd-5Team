"""시장 문구 판정: 원본 수집 파일 불변, 기능성 확인 여부 처리, 함량 표기 오탐 방지."""
import json
import sys
from pathlib import Path

import pytest

from app.services.market_evidence import load_reference_catalog
from app.services.market_judgements import judgement_counts, load_copy_judgements
from cosmetic_agent.domain.rules import RuleEngine, functional_types
from cosmetic_agent.models.rule_judge import RuleJudgeModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import judge_market_copies as jmc  # noqa: E402

GENERAL = {"category": "일반", "functional_type": None, "owned_evidence": []}


@pytest.fixture(scope="module")
def judge():
    return RuleJudgeModel(RuleEngine())


def test_functional_types_normalization():
    assert functional_types("피부 미백;주름 개선") == ["피부 미백", "주름 개선"]
    assert functional_types(["주름 개선"]) == ["주름 개선"]
    assert functional_types(None) == []


def test_dual_functional_product_is_exempt_for_both_types():
    engine = RuleEngine()
    product = {"category": "기능성", "functional_type": "피부 미백;주름 개선", "owned_evidence": []}
    assert engine.evaluate("미백과 주름 개선에 도움", product)["level"] == 0
    assert engine.evaluate("미백과 주름 개선에 도움", GENERAL)["level"] == 2


@pytest.mark.parametrize("text", ["레티놀 RX™ 2%", "레티날 부스터 샷 0.2퍼센트"])
def test_ingredient_content_is_not_an_efficacy_number(judge, text):
    assert judge.judge_product(text, GENERAL)["model_level"] == 0


@pytest.mark.parametrize("text", ["팔자 주름\n-18.49%", "892% 흡수 기술", "72시간 보습 효과"])
def test_efficacy_numbers_still_need_evidence(judge, text):
    assert judge.judge_product(text, GENERAL)["model_level"] == 1


def test_collagen_ingredient_name_is_not_a_claim(judge):
    assert judge.judge_product("콜라겐 PDRN 밀키 토너", GENERAL)["model_level"] == 0
    assert judge.judge_product("콜라겐 생성을 촉진", GENERAL)["model_level"] == 1


def test_unconfirmed_functional_status_is_flagged_not_convicted(judge):
    out = jmc.judge_copy(judge, "미간 주름 완화에 도움", None)
    assert out["depends_on_functional_status"] is True
    assert out["level_if_general"] == 2 and out["res"]["model_level"] == 0
    confirmed = jmc.judge_copy(judge, "미간 주름 완화에 도움", ["주름 개선"])
    assert confirmed["depends_on_functional_status"] is False


def test_tag_normalization():
    assert jmc.normalize_tags(["수치", "성분 강조"]) == ["효능 수치형", "성분 소구형"]
    assert jmc.normalize_tags([]) == ["기타"]


def test_build_covers_every_catalog_copy_without_touching_raw_files():
    raw = ROOT / "data" / "top_product_copies" / "wrinkle_serum_sample" / "copies.jsonl"
    before = raw.read_bytes()
    rows = jmc.build()
    catalog = load_reference_catalog()
    assert len(rows) == sum(len(c["observed_copies"]) for c in catalog.values())
    assert all(r["judge_level"] in (0, 1, 2) and r["disclaimer"] for r in rows)
    assert all(r["문구 유형"] and set(r["문구 유형"]) <= set(jmc.APPEAL_TYPES) for r in rows)
    assert raw.read_bytes() == before
    assert all(json.loads(line)["judge_level"] is None for line in before.decode("utf-8").splitlines() if line.strip())


def test_saved_judgements_load_for_ui(tmp_path):
    assert load_copy_judgements(tmp_path / "missing.jsonl") == {}
    saved = load_copy_judgements()
    if saved:
        assert sum(judgement_counts(saved).values()) == len(saved)
