"""Exact normalized ingredient overlap, not efficacy or formulation equivalence."""

import json
import re
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "sales_forecast_reference"
    / "copy_comparison"
    / "ingredient_profiles.json"
)
ALIASES = {
    "water": "정제수",
    "aqua": "정제수",
    "squalane": "스쿠알란",
    "glycerin": "글리세린",
    "ceramidenp": "세라마이드엔피",
    "sodiumhyaluronate": "소듐하이알루로네이트",
    "tocopherol": "토코페롤",
    "carbomer": "카보머",
    "phenoxyethanol": "페녹시에탄올",
    "ethylhexylglycerin": "에틸헥실글리세린",
    "sodiumhydroxide": "소듐하이드록사이드",
    "cetearylalcohol": "세테아릴알코올",
    "cetylpalmitate": "세틸팔미테이트",
    "sorbitanpalmitate": "솔비탄팔미테이트",
    "sorbitanolivate": "솔비탄올리베이트",
    "caprylic/caprictriglyceride": "카프릴릭/카프릭트라이글리세라이드",
    "linoleicacid": "리놀레익애씨드",
    "oleicacid": "올레익애씨드",
    "linolenicacid": "리놀레닉애씨드",
    "euterpeoleraceasterols": "아사이야자스테롤",
}


def normalize(name):
    value = re.sub(r"\s+", "", name).casefold()
    return ALIASES.get(value, value)


def registry():
    return json.loads(PATH.read_text(encoding="utf-8"))


def names(profile):
    raw = profile["ingredient_text"]
    return {
        normalize(x)
        for x in (raw.split(",") if profile["delimiter"] == "comma" else raw.split())
        if x.strip()
    }


def compare_profiles(target, reference):
    a, b = names(target), names(reference)
    af = {normalize(x) for x in target.get("focus_ingredients", [])}
    bf = {normalize(x) for x in reference.get("focus_ingredients", [])}
    shared_focus = sorted(af & bf & a & b)
    same_form = target["form"] == reference["form"]
    complete = bool(target.get("complete_list") and reference.get("complete_list"))
    return {
        "eligible": same_form and complete and bool(shared_focus),
        "shared": sorted(a & b),
        "target_only": sorted(a - b),
        "reference_only": sorted(b - a),
        "shared_focus": shared_focus,
        "reference_only_focus": sorted((bf & b) - a),
        "target_count": len(a),
        "reference_count": len(b),
        "reason": "동일 제형·공식 전성분 확인·주요 소구 성분 공통"
        if same_form and complete and shared_focus
        else "제형 또는 전성분 또는 주요 소구 성분 일치 조건 부족",
        "efficacy_equivalence": None,
        "concentration_similarity": None,
    }


def matched_references(product_id):
    data = registry()
    target_id = data["project_profile_ids"].get(product_id)
    if target_id is None:
        return None, [], []
    target = data["profiles"][target_id]
    accepted, excluded = [], []
    for pid, reference in data["profiles"].items():
        if pid == target_id:
            continue
        match = compare_profiles(target, reference)
        row = {"reference_id": pid, "profile": reference, "comparison": match}
        (accepted if match["eligible"] else excluded).append(row)
    accepted.sort(
        key=lambda r: (-len(r["comparison"]["shared_focus"]), r["reference_id"])
    )
    return target, accepted, excluded
