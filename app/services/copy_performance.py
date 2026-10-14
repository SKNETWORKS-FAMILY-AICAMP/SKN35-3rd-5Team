"""Observed CTR and equal-exposure arithmetic scenarios; no learned sales uplift."""

import math


def relative_change(baseline, candidate):
    if baseline in (None, 0) or candidate is None:
        return None
    return (candidate / baseline - 1) * 100


def compare_arms(a, b, planned_impressions=None):
    for label, arm in [("A", a), ("B", b)]:
        for key in ("impressions", "clicks", "orders", "units", "net_revenue"):
            value = arm.get(key)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{label}: 수치는 0 이상의 유한한 값이어야 합니다.")
        if not arm.get("impressions") or arm.get("clicks") is None:
            raise ValueError(f"{label}: 노출 수(1 이상)와 클릭 수를 입력해 주세요.")
        if arm["clicks"] > arm["impressions"]:
            raise ValueError(
                f"{label}: 클릭 수가 노출 수보다 큽니다. 동일한 집계 기준인지 확인해 주세요."
            )
    if planned_impressions is not None and (
        not math.isfinite(planned_impressions) or planned_impressions <= 0
    ):
        raise ValueError("계획 노출 수는 1 이상이어야 합니다.")
    ctr_a = a["clicks"] / a["impressions"]
    ctr_b = b["clicks"] / b["impressions"]
    result = {
        "ctr_a": ctr_a,
        "ctr_b": ctr_b,
        "ctr_difference_pp": (ctr_b - ctr_a) * 100,
        "ctr_relative_change_pct": relative_change(ctr_a, ctr_b),
        "planned_impressions": planned_impressions,
        "projections": {},
    }
    for metric in ("orders", "units", "net_revenue"):
        pa = (
            planned_impressions * a[metric] / a["impressions"]
            if planned_impressions and a.get(metric) is not None
            else None
        )
        pb = (
            planned_impressions * b[metric] / b["impressions"]
            if planned_impressions and b.get(metric) is not None
            else None
        )
        result["projections"][metric] = {
            "a": pa,
            "b": pb,
            "change_pct": relative_change(pa, pb),
            "difference": pb - pa if pa is not None and pb is not None else None,
        }
    return result
