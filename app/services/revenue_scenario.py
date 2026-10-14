"""
[app/services/revenue_scenario.py]
추천 문구 사용에 따른 예상 매출·판매량 시나리오와, 원문 유지 시 처분 위험 매출을 계산한다.

설계 원칙 (data/sales_forecast_reference/FORECAST_DATA_PLAN.md)
- 학습된 예측이 아니라 '가정 기반 시나리오'다. 모든 입력값에 출처 또는 '사용자 입력'을 붙인다.
- 문구 효과(D5)는 방향을 모르는 '변화 폭'이다. 상승률이 아니므로 기준값 ± 범위로만 보여준다.
- 문구 효과는 '문구가 노출되는 경로의 유입(클릭)'에만 적용한다. 구매전환율·객단가는 그대로 둔다.
  → 영향받는 매출 = 기준 매출 × copy_exposed_share
- 처분 위험(D1)은 law_id 로만 기간을 찾는다. 연결되지 않은 law_id 는 '개별 검토'로 표시한다.
  복수 위반은 더하지 않고 가장 무거운 기준 하나를 쓴다. 적발 확률은 만들지 않는다.
- 광고업무정지는 판매 중단이 아니다. 광고 의존 매출 비중을 모르면 금액은 '상한'만 보여준다.
- 미확인 값은 0으로 채우지 않고 None 으로 둔다.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "data" / "sales_forecast_reference"
PENALTY_PATH = REFERENCE / "penalty_schedule.json"
EFFECT_PATH = REFERENCE / "copy_effect_size_distribution.json"

DISPLAY_LABEL = "가정 기반 시나리오 · 학습된 예측 아님"
EFFECT_LABEL = "다른 분야 실험에서 관찰된 문구 효과 크기를 참고한 가정 범위 (방향 미정, ±)"


# ---------------------------------------------------------------------- 입력 정리
@dataclass(frozen=True)
class Range3:
    """low / mid / high. 한 값만 알면 세 값이 같다."""
    low: float
    mid: float
    high: float

    @classmethod
    def of(cls, value: Any, name: str) -> "Range3":
        if isinstance(value, Range3):
            return value
        if isinstance(value, dict):
            low, mid, high = value.get("low"), value.get("mid"), value.get("high")
            mid = mid if mid is not None else (low + high) / 2 if low is not None and high is not None else None
            low = low if low is not None else mid
            high = high if high is not None else mid
        else:
            low = mid = high = value
        for v in (low, mid, high):
            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{name}: 0 이상의 숫자(또는 low/mid/high)를 입력해 주세요.")
        if not low <= mid <= high:
            raise ValueError(f"{name}: low ≤ mid ≤ high 순서여야 합니다.")
        return cls(float(low), float(mid), float(high))

    def scale(self, k: float) -> "Range3":
        return Range3(self.low * k, self.mid * k, self.high * k)

    def as_dict(self, digits: int = 0) -> dict[str, float]:
        return {k: round(getattr(self, k), digits) for k in ("low", "mid", "high")}


def _share(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{name}: 0~1 사이 비율로 입력해 주세요.")
    return float(value)


# ---------------------------------------------------------------------- 데이터 로딩
@lru_cache(maxsize=1)
def load_penalty_schedule(path: Path = PENALTY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_effect_distribution(path: Path = EFFECT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- ① 처분 위험
def law_ids_for_copy(copy_text: str, product: dict[str, Any], rule_engine: Any = None) -> tuple[int, list[str]]:
    """규칙 엔진으로 원문을 다시 검사해, 최종 수준을 만든 위반의 law_id 만 모은다.
    (RAG citations 는 검색된 참고 조항이라 위반 조항과 다를 수 있어 쓰지 않는다)"""
    if rule_engine is None:
        from cosmetic_agent.domain.rules import RuleEngine

        rule_engine = RuleEngine()
    report = rule_engine.evaluate(copy_text, product)
    level = report["level"]
    ids = [h.get("law_id") for h in report["hits"] if h["level"] == level and h.get("law_id")]
    return level, list(dict.fromkeys(ids))


def penalty_for(law_ids: list[str], offense: int = 1, schedule: dict[str, Any] | None = None) -> dict[str, Any]:
    """law_id 목록 → 처분 기준. 복수면 가장 무거운 기준 하나 (합산하지 않음)."""
    schedule = schedule or load_penalty_schedule()
    by_id = {s["schedule_id"]: s for s in schedule["schedules"]}
    mapping = {m["law_id"]: m for m in schedule["law_id_mapping"]}
    if offense < 1:
        raise ValueError("위반 차수는 1 이상입니다.")

    matched, unmapped = [], []
    for law_id in law_ids:
        entry = mapping.get(law_id)
        if not entry:
            unmapped.append(law_id)
            continue
        sched = by_id[entry["schedule_id"]]
        cols = sched["offense_columns"]
        col = cols[min(offense, len(cols)) - 1]
        matched.append({"law_id": law_id, "schedule_id": sched["schedule_id"], "rule_item": entry["rule_item"],
                        "description": entry.get("description"), "months": col["months"],
                        "source_cell_status": col["source_cell_status"], "sanction": sched["sanction"],
                        "source_article": sched["source_article"]})

    known = [m for m in matched if m["months"] is not None]
    heaviest = max(known, key=lambda m: m["months"]) if known else None
    status = "mapped" if heaviest else ("needs_review" if (matched or unmapped) else "no_violation")
    return {
        "status": status,
        "offense": offense,
        "heaviest": heaviest,
        "matched": matched,
        "unmapped_law_ids": unmapped,
        "note": (
            "처분 기준과 연결되지 않은 조항이 있어 개별 검토가 필요합니다." if unmapped and not heaviest
            else "원문 칸이 비어 있는 차수라 개별 검토가 필요합니다." if matched and not heaviest
            else "복수 위반은 가장 무거운 기준만 표시합니다 (합산하지 않음). 감경·가중은 반영하지 않습니다."
            if heaviest else None
        ),
    }


def revenue_at_risk(monthly_revenue: Range3, penalty: dict[str, Any], level: int,
                    ad_dependent_share: float | None, sanction_kind: str = "광고") -> dict[str, Any]:
    heaviest = penalty.get("heaviest")
    if level == 0 or penalty["status"] == "no_violation":
        return {"status": "no_violation", "label": "규칙상 처분 위험 표현 없음"}
    if not heaviest:
        return {"status": "needs_review", "label": "처분 기준 개별 검토 필요", "note": penalty.get("note"),
                "unmapped_law_ids": penalty.get("unmapped_law_ids", [])}

    months = heaviest["months"]
    condition = ("적발 시" if level == 2
                 else "실증 자료를 제출하지 못해 위반으로 판단될 경우")
    if sanction_kind == "표시":
        # 표시 위반 → 해당 품목 판매업무정지: 정지 기간의 품목 매출 전체가 영향
        amount = monthly_revenue.scale(months)
        return {"status": "mapped", "condition": condition, "months": months,
                "sanction": heaviest["sanction"]["표시"], "basis_law_id": heaviest["law_id"],
                "amount_krw": amount.as_dict(), "amount_kind": "판매업무정지 기간의 품목 매출",
                "unmapped_law_ids": penalty.get("unmapped_law_ids", []),
                "detection_probability": None, "note": penalty.get("note")}

    # 광고 위반 → 해당 품목 광고업무정지: 판매는 계속될 수 있다
    upper = monthly_revenue.scale(months)
    estimate = upper.scale(ad_dependent_share) if ad_dependent_share is not None else None
    return {"status": "mapped", "condition": condition, "months": months,
            "sanction": heaviest["sanction"]["광고"], "basis_law_id": heaviest["law_id"],
            "upper_bound_krw": upper.as_dict(),
            "upper_bound_meaning": "모든 판매가 광고에서 발생한다고 가정한 상한",
            "estimate_krw": estimate.as_dict() if estimate else None,
            "estimate_note": None if estimate else "광고 의존 매출 비중을 입력하면 추정액을 계산합니다.",
            "unmapped_law_ids": penalty.get("unmapped_law_ids", []),
            "detection_probability": None, "note": penalty.get("note")}


# ---------------------------------------------------------------------- ② 문구 교체 시 변화 폭
def copy_change_band(monthly_revenue: Range3, copy_exposed_share: float,
                     effect: dict[str, Any] | None = None) -> dict[str, Any]:
    effect = effect or load_effect_distribution()
    q = effect["absolute_relative_ctr_change"]["quantiles"]
    exposed_mid = monthly_revenue.mid * copy_exposed_share
    bands = {name: round(exposed_mid * q[name]) for name in ("p25", "median", "p75")}
    return {
        "applies_to": "문구가 노출되는 경로의 유입(클릭) 기반 매출만. 구매전환율·객단가는 고정",
        "exposed_revenue_mid_krw": round(exposed_mid),
        "change_magnitude_pct": {k: round(q[k] * 100, 1) for k in ("p25", "median", "p75")},
        "change_magnitude_krw": bands,
        "typical_range_krw": {   # p75 기준 ± 폭
            "low": round(monthly_revenue.mid - bands["p75"]),
            "high": round(monthly_revenue.mid + bands["p75"]),
        },
        "direction": "unknown",
        "label": EFFECT_LABEL,
        "source": effect["source"]["file"],
        "not_identified": "추천 문구별 상승률은 식별되지 않았습니다. 후보 A/B/C 에 같은 범위를 공통 적용합니다.",
    }


# ---------------------------------------------------------------------- 통합
def build_scenario(
    *,
    price_krw: Any,
    monthly_units: Any,
    copy_text: str | None = None,
    product: dict[str, Any] | None = None,
    law_ids: list[str] | None = None,
    level: int | None = None,
    offense: int = 1,
    sanction_kind: str = "광고",
    ad_dependent_share: float | None = None,
    copy_exposed_share: float = 1.0,
    units_source: str = "사용자 입력",
    price_source: str = "사용자 입력",
    rule_engine: Any = None,
) -> dict[str, Any]:
    """예상 매출 시나리오.

    Args:
        price_krw: 1개 단위 판매가 (숫자 또는 {low, mid, high})
        monthly_units: 월 판매량 (숫자 또는 {low, mid, high}; D2 리뷰 보정 범위를 넣을 수 있음)
        copy_text, product: 원문 문구와 제품. law_ids/level 을 주지 않으면 규칙 엔진으로 계산
        sanction_kind: '광고'(광고업무정지) 또는 '표시'(판매업무정지)
        ad_dependent_share: 광고에서 발생하는 매출 비중 (모르면 None → 상한만)
        copy_exposed_share: 문구가 노출되는 경로의 매출 비중 (기본 1.0 = 전부라고 가정)
    """
    if sanction_kind not in ("광고", "표시"):
        raise ValueError("sanction_kind 는 '광고' 또는 '표시' 입니다.")
    price = Range3.of(price_krw, "판매가")
    units = Range3.of(monthly_units, "월 판매량")
    exposed = _share(copy_exposed_share, "문구 노출 경로 매출 비중")
    ad_share = _share(ad_dependent_share, "광고 의존 매출 비중")

    if law_ids is None or level is None:
        if copy_text is None or product is None:
            raise ValueError("law_ids·level 또는 copy_text·product 중 하나는 필요합니다.")
        level, law_ids = law_ids_for_copy(copy_text, product, rule_engine)

    revenue = Range3(units.low * price.low, units.mid * price.mid, units.high * price.high)
    penalty = penalty_for(law_ids, offense) if level and level > 0 else {"status": "no_violation", "heaviest": None}

    assumptions = [
        f"월 판매량: {units_source}",
        f"판매가: {price_source}",
        f"문구 노출 경로 매출 비중 {exposed:.0%}" + (" (기본값: 전부라고 가정)" if copy_exposed_share == 1.0 else ""),
        "구매전환율·객단가는 문구와 무관하게 고정",
    ]
    if ad_share is not None:
        assumptions.append(f"광고 의존 매출 비중 {ad_share:.0%}")

    return {
        "display_label": DISPLAY_LABEL,
        "inputs": {"price_krw": price.as_dict(), "monthly_units": units.as_dict(1), "level": level,
                   "law_ids": law_ids, "offense": offense, "sanction_kind": sanction_kind},
        "monthly_revenue_krw": revenue.as_dict(),
        "copy_change_band": copy_change_band(revenue, exposed),
        "revenue_at_risk_if_unchanged": revenue_at_risk(revenue, penalty, level, ad_share, sanction_kind),
        "assumptions": assumptions,
        "not_provided": ["적발 확률", "추천 문구별 상승률", "감경·가중 처분"],
    }
