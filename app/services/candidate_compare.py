"""
[app/services/candidate_compare.py]
광고문 생성 후보(헤드라인 + 설명 + 시험 별첨)를 예상 매출 관점에서 나란히 비교한다.

후보마다 보는 것
  · 문구 유형     후보 문장을 7개 유형으로 분류 (시장 비교 ②와 같은 기준)
  · 시장 사용도   같은 유형을 쓰는 비슷한 시장 제품 수 · 인기 상위(랭킹 10위 안) 수
  · 규칙 판정     규칙 엔진 재검사 (0 쓸 수 있음 / 1 근거 필요 / 2 쓰면 안 됨)
  · 처분 위험     위반이면 처분 기준표의 정지 기간 (가장 무거운 1개)
  · 근거 강도     생성 표현 강도(strong/balanced/safe) + 우리 제품 시험(E) 사용 여부

추천 = 규칙상 쓸 수 있는 후보 중 [표현 강도 → 우리 시험 사용 → 시장 인기 유형] 순으로 가장 높은 것.
문구별 매출 상승률은 데이터가 없어 추정하지 않는다. 추천은 '처분 위험 없이 가장 강하게 말할 수 있는 문구'라는 뜻이다.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.revenue_scenario import law_ids_for_copy, penalty_for

TIER_LABEL = {"strong": "강한 표현", "balanced": "균형", "safe": "가장 안전"}
TIER_RANK = {"strong": 3, "balanced": 2, "safe": 1}

# 문구 유형 분류 규칙 (위에서부터 검사, 여러 개 해당 가능)
_NUMERIC = re.compile(r"\d+(?:\.\d+)?\s*(?:%|퍼센트|배|시간|주|일|회)")
_RANK = re.compile(r"(?:1위|No\.?\s?1|넘버원|TOP\s?\d|최고|가장|단독|최다|어워[드즈])", re.I)
_TEST = re.compile(r"(?:테스트|시험|임상|인체적용|전문의|피부과)")
_EFFECT = re.compile(r"(?:개선|도움|미백|주름|보습|진정|장벽|탄력|수분을?\s?(?:채|공급)|톤|광채|생기|결)")
_FEEL = re.compile(r"(?:산뜻|촉촉|부드러|끈적|스며|가볍|텍스처|감싸|촉감|질감|흡수|발림)")
_OFFER = re.compile(r"(?:증정|리필|기획|세트|할인|1\+1|무료배송|추가\s?\d)")


def classify_appeal(text: str, product: dict | None = None) -> list[str]:
    """후보 문장 → 문구 유형 목록. 시장 문구 분석(market_reference.APPEAL_TYPES)과 같은 이름을 쓴다."""
    from cosmetic_agent.market_reference import ingredient_groups

    t = text or ""
    types: list[str] = []
    if _NUMERIC.search(t) and _EFFECT.search(t):
        types.append("효능 수치형")
    if _EFFECT.search(t):
        types.append("효능 서술형")
    names = [n for n in (product or {}).get("key_ingredients", []) if n and n in t]
    if names or ingredient_groups(t):
        types.append("성분 소구형")
    if _FEEL.search(t):
        types.append("사용감형")
    if _OFFER.search(t):
        types.append("구성·혜택형")
    if _RANK.search(t):
        types.append("비교·순위형")
    if _TEST.search(t):
        types.append("시험·검사 표방형")
    return types or ["효능 서술형"]


def _creative_names(ids: list[str]) -> list[str]:
    try:
        from cosmetic_agent.generation.creative import creative_catalog

        names = {s["reference_id"]: s["name"] for s in creative_catalog()["styles"]}
    except (OSError, KeyError, ValueError, ImportError):
        names = {}
    return [names.get(i, i) for i in ids]


def judge_copy(text: str, product: dict, offense: int = 1, rule_engine: Any = None) -> dict:
    """규칙 수준 + 처분 기준(정지 개월). 빈 문장은 판정하지 않는다."""
    if not (text or "").strip():
        return {"level": None, "law_ids": [], "penalty": None, "months": None, "sanction": None}
    level, law_ids = law_ids_for_copy(text, product, rule_engine)
    pen = penalty_for(law_ids, offense) if law_ids else {"status": "no_violation", "heaviest": None}
    heaviest = pen.get("heaviest") or {}
    return {"level": level, "law_ids": law_ids, "penalty": pen["status"],
            "months": heaviest.get("months"), "sanction": heaviest.get("sanction")}


def compare_candidates(product: dict, candidates: list[dict], appeal_rows: list[dict],
                       offense: int = 1, rule_engine: Any = None) -> list[dict]:
    """생성 후보 목록 → 비교 행. appeal_rows 는 market_reference.appeal_summary(peers) 결과."""
    if rule_engine is None:
        from cosmetic_agent.domain.rules import RuleEngine

        rule_engine = RuleEngine()
    by_type = {r["type"]: r for r in appeal_rows}
    rows = []
    for i, c in enumerate(candidates):
        text = c.get("text") or ""
        types = classify_appeal(text, product)
        market = [by_type[t] for t in types if t in by_type and by_type[t]["products"]]
        judged = judge_copy(text, product, offense, rule_engine)
        rows.append({
            "index": i,
            "headline": c.get("headline") or text.split("\n")[0],
            "supporting": c.get("supporting_copy") or "\n".join(text.split("\n")[1:]),
            "text": text,
            "tier": c.get("tier"),
            "tier_label": TIER_LABEL.get(c.get("tier"), c.get("tier") or "—"),
            "creative": _creative_names(c.get("creative_reference_ids") or []),
            "uses_evidence": bool(c.get("evidence_reference_ids") or c.get("used_evidence")),
            "evidence_ids": c.get("evidence_reference_ids") or [],
            "market_ids": c.get("market_reference_ids") or [],
            "types": types,
            "peer_products": max((m["products"] for m in market), default=0),
            "peer_popular": max((m["popular_products"] for m in market), default=0),
            "peer_total": max((m["peers"] for m in appeal_rows), default=0),
            "verified": c.get("verified", True),
            **judged,
        })
    usable = [r for r in rows if r["level"] == 0 and r["verified"]]
    best = max(usable, key=lambda r: (TIER_RANK.get(r["tier"], 0), r["uses_evidence"], r["peer_popular"],
                                      r["peer_products"]), default=None)
    for r in rows:
        r["recommended"] = r is best
        r["why"] = _why(r) if r is best else None
    return rows


def _why(r: dict) -> str:
    parts = ["규칙상 쓸 수 있는 후보 중"]
    parts.append(f"표현이 가장 강하고({r['tier_label']})")
    if r["uses_evidence"]:
        parts.append("우리 제품 시험 자료로 뒷받침되며")
    if r["peer_popular"]:
        parts.append(f"인기 상위 시장 제품 {r['peer_popular']}개가 쓰는 유형({', '.join(r['types'][:2])})이에요")
    else:
        parts.append(f"문구 유형은 {', '.join(r['types'][:2])}이에요")
    return " ".join(parts) + "."
