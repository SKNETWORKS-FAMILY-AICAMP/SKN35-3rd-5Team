"""
[tests/unit/test_rules.py]
규칙 엔진·규칙 판정(R0) 단위 테스트. 골든셋 문구가 아닌 별도 문구로 검사한다.
"""
import json
import re

import pytest

from cosmetic_agent.common.config import settings
from cosmetic_agent.domain.rules import VIOLATION_TYPES, RuleEngine
from cosmetic_agent.models.rule_judge import RuleJudgeModel

GENERAL = {"category": "일반", "functional_type": None, "owned_evidence": []}
MOIST = {"category": "일반", "functional_type": None, "owned_evidence": [
    {"test_type": "인체적용시험", "item": "피부 보습 개선", "value": "4주 사용 후 보습력 35% 개선", "institute": "외부기관"}]}
SURVEY = {"category": "기능성", "functional_type": "주름 개선", "owned_evidence": [
    {"test_type": "자사비교시험", "item": "탄력감 만족도", "value": "2주차 만족도 88%", "institute": "사내 설문"}]}
HAIR = {"category": "기능성", "functional_type": "탈모 증상 완화", "owned_evidence": []}
ACNE = {"category": "기능성", "functional_type": "여드름성 피부 완화", "owned_evidence": []}


@pytest.fixture(scope="module")
def engine() -> RuleEngine:
    return RuleEngine()


def test_rule_engine_initialization(engine):
    assert isinstance(engine.banned_terms, list) and len(engine.banned_terms) >= 40
    assert engine.substantiation_rules and engine.comparison_rules


def test_assets_use_contract_names_and_id_format(engine):
    """③ violation_type 7개 이름 / ④ 근거 ID 는 RAG 청크 형식 (옛 LAW_COSMETIC_RULE 형식 금지)"""
    rules = engine.banned_terms + engine.substantiation_rules + engine.comparison_rules + engine.exaggeration_rules
    for rule in rules:
        assert rule["type"] in VIOLATION_TYPES, rule["id"]
        for key in ("basis_id", "law_id"):
            assert re.match(r"^(LAW|GUIDE|NOTICE)_", rule[key]), (rule["id"], rule[key])
            assert "COSMETIC" not in rule[key]
    raw = settings.BANNED_TERMS_PATH.read_text(encoding="utf-8")
    assert "LAW_COSMETIC_RULE" not in raw
    assert "LAW_시행규칙_별표5-2가" in raw


def test_check_banned_terms_contract(engine):
    """② (등급, 적발목록) 형식 유지, 2개 인자 호출도 동작 (CopyVerifier 호환)"""
    level, hits = engine.check_banned_terms("세포 재생 크림", "일반")
    assert level == 2 and isinstance(hits, list)
    assert {"type", "term", "basis_id"} <= hits[0].keys()
    assert engine.check_banned_terms("부드러운 사용감", "일반") == (0, [])
    assert engine.check_banned_terms("", "일반") == (0, [])


def test_hits_are_sorted_by_priority(engine):
    _, hits = engine.check_banned_terms("진피층까지 닿아 피부를 재생", "일반")
    assert hits[0]["type"] == "의약품오인"  # 의약품오인 > 범위이탈


@pytest.mark.parametrize("text,vtype", [
    ("두피염을 치료하는 토닉", "의약품오인"),
    ("손상 피부를 재생시켜 줍니다", "의약품오인"),
    ("항염 성분 듬뿍", "의약품오인"),
    ("레이저 시술 같은 효과", "범위이탈"),
    ("약사가 추천한 크림", "소비자오인"),
    ("국내 최고 보습력", "비교광고"),
])
def test_banned_examples(engine, text, vtype):
    res = engine.evaluate(text, GENERAL)
    assert res["level"] == 2 and res["violation_type"] == vtype


def test_functional_claim_only_for_reviewed_type(engine):
    text = "탈모 증상 완화에 도움"
    assert engine.evaluate(text, HAIR)["level"] == 0
    res = engine.evaluate(text, GENERAL)
    assert res["level"] == 2 and res["violation_type"] == "기능성오인"
    assert res["basis_ids"][0] == "LAW_시행규칙_별표5-2나"
    # 기능성 유형을 넘기지 않으면 예외가 적용되지 않는다 (rule_check_node 회귀 방지)
    assert engine.check_banned_terms(text, "기능성")[0] == 2
    assert engine.check_banned_terms(text, "기능성", "탈모 증상 완화")[0] == 0


def test_functional_product_claiming_different_effect(engine):
    res = engine.evaluate("탈모를 예방하는 샴푸", HAIR)
    assert res["level"] == 2


def test_numbers_against_evidence(engine):
    assert engine.evaluate("4주 사용 후 보습력 35% 개선", MOIST)["level"] == 0
    wrong = engine.evaluate("보습력 70% 개선", MOIST)           # 같은 효능 시험과 다른 수치 → 불가
    assert wrong["level"] == 2 and wrong["violation_type"] == "소비자오인"
    none = engine.evaluate("보습력 70% 개선", GENERAL)           # 시험 자체가 없음 → 조건부
    assert none["level"] == 1 and none["violation_type"] == "실증필요" and none["next_test"]
    survey = engine.evaluate("사용자 88%가 만족 (2주)", SURVEY)  # 자사 조사 수치 → 조건부
    assert survey["level"] == 1 and "NOTICE_실증규정_제5조" in survey["basis_ids"]


def test_substantiation_targets(engine):
    res = engine.evaluate("피부장벽 강화 크림", MOIST)
    assert res["level"] == 1 and res["violation_type"] == "실증필요"
    assert engine.evaluate("여드름성 피부에 사용 적합", GENERAL)["level"] == 1
    assert engine.evaluate("여드름성 피부에 사용 적합", ACNE)["level"] == 0


def test_guideline_exceptions(engine):
    assert engine.evaluate("보습으로 건조함에 의한 가려움을 일시적으로 완화", GENERAL)["level"] == 0
    assert engine.evaluate("가려움을 싹 진정", GENERAL)["level"] == 2
    assert engine.check_banned_terms("식물 엑소좀 함유", "일반")[0] == 0
    assert engine.check_banned_terms("엑소좀 크림", "일반")[0] == 2
    assert engine.evaluate("모공 노폐물을 말끔히 세정", GENERAL)["level"] == 0


def test_ladder_and_functional_ceiling(engine):
    assert engine.get_ladder_ceiling("보습")["claim"] == "보습"
    assert engine.get_ladder_ceiling("콜라겐")["claim"] == "주름"
    assert engine.get_ladder_ceiling("unknown") == {}
    assert engine.get_functional_ceiling("주름 개선")["ceiling"]


def test_rule_judge_output_contract():
    res = RuleJudgeModel(RuleEngine()).judge_product("피부 재생 크림", GENERAL)
    assert res["model_level"] == 2 and res["violation_type"] == "의약품오인"
    assert {"model_level", "violation_type", "claim_type", "confidence", "rationale"} <= res.keys()
    assert RuleJudgeModel(RuleEngine()).judge("피부 재생 크림", "일반")["model_level"] == 2


def test_functional_claims_keep_suggester_contract():
    """copy_suggester 가 type → ceiling 으로 읽는다"""
    items = json.loads(settings.FUNCTIONAL_CLAIMS_PATH.read_text(encoding="utf-8"))
    products = json.loads(settings.MOCK_PRODUCTS_PATH.read_text(encoding="utf-8"))
    types = {i["type"] for i in items}
    assert all(i["ceiling"] for i in items)
    assert {p["functional_type"] for p in products if p["functional_type"]} <= types
