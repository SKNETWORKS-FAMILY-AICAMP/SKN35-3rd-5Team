"""Build only D1 and D5 from local source snapshots; no revenue calculation."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sales_forecast_reference"
LAW = ROOT / "data" / "01_raw" / "law" / "화장품법_시행규칙.xml"
PAIRS = OUT / "copy_comparison" / "headline_comparisons.jsonl"
DATE = "2026-10-14"
VISUALLY_AUDITED_XML_SHA256 = (
    "268b60f3ad8e59df37480ba8b99f0e02f49ff11913dd08b9936ed142b902447f"
)
VISUALLY_AUDITED_PDF_SHA256 = (
    "c8a97458853fd3f6a436d4904479d95be513c408192e8540d3f104fee5079cdc"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def compact(text):
    return re.sub(r"\s+", "", text)


def annex(root, number):
    return next(
        b
        for b in root.findall(".//별표단위")
        if b.findtext("별표번호") == number and b.findtext("별표가지번호") == "00"
    )


def extract_months(block):
    """Join each original table column vertically; verify both sanction branches."""
    rows = [
        line.split("│")[1:-1]
        for line in block.splitlines()
        if line.strip().startswith("│")
    ]
    rows = [r for r in rows if len(r) == 6]
    if not rows:
        raise ValueError("No six-column source table found")
    columns = [compact("".join(r[i] for r in rows)) for i in range(2, 6)]
    result = []
    for column in columns:
        values = [int(x) for x in re.findall(r"정지(\d+)개월", column)]
        if not column:
            result.append(None)
        elif (
            len(values) == 2
            and len(set(values)) == 1
            and "판매업무" in column
            and "광고업무" in column
        ):
            result.append(values[0])
        else:
            raise ValueError(
                f"Unrecognized or inconsistent source sanction column: {column}"
            )
    return result, columns


def walk_rules(value):
    if isinstance(value, dict):
        if value.get("law_id") and value.get("type"):
            yield value
        for child in value.values():
            yield from walk_rules(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_rules(child)


def build_d1():
    if digest(LAW) != VISUALLY_AUDITED_XML_SHA256:
        raise ValueError(
            "원문 버전이 바뀌었습니다. 처분표·공란·일반기준을 다시 대조한 뒤 감사 해시를 갱신하세요."
        )
    root = ET.parse(LAW).getroot()
    annex7, annex5 = annex(root, "0007"), annex(root, "0005")
    text7, text5 = annex7.findtext("별표내용"), annex5.findtext("별표내용")
    start, stop = text7.index("더. 법 제13조"), text7.index("러. 법 제14조")
    part = text7[start:stop]
    first, second = part.index("│ 1)"), part.index("│ 2)")
    groups = []
    all_items = list("가나다라마바사아자차카")
    for index, (letters, block) in enumerate(
        [
            (list("가나카"), part[first:second]),
            (list("다라마바사아자차"), part[second:]),
        ],
        start=1,
    ):
        months, columns = extract_months(block)
        groups.append(
            {
                "schedule_id": f"ANNEX7_2_DEO_{index}",
                "rule_items": [f"2{x}" for x in letters],
                "law_ids": [f"LAW_시행규칙_별표5-2{x}" for x in letters],
                "sanction": {
                    "표시": "해당 품목 판매업무정지",
                    "광고": "해당 품목 광고업무정지",
                },
                "months_by_offense": [x for x in months if x is not None],
                "offense_columns": [
                    {
                        "offense": label,
                        "months": value,
                        "source_cell_status": "blank_requires_review"
                        if value is None
                        else "stated",
                    }
                    for label, value in zip(["1", "2", "3", "4이상"], months)
                ],
                "source_article": f"화장품법 시행규칙 제29조제1항·별표7 제2호 더목{index}) / 화장품법 제13조·제24조제1항제10호",
                "source_file": LAW.relative_to(ROOT).as_posix(),
                "source_locator": "별표번호=0007, 가지번호=00 / PDF 9페이지",
                "source_columns_compact": columns,
                "verified_against_raw": True,
            }
        )
    rule_files = [
        ROOT / "data/assets/banned_terms.json",
        ROOT / "data/assets/rule_patterns.json",
    ]
    rules = [
        r
        for path in rule_files
        for r in walk_rules(json.loads(path.read_text(encoding="utf-8")))
    ]
    descriptions = [
        "의약품 오인",
        "기능성화장품 오인",
        "의약 전문가 등의 지정·공인·추천 등",
        "제품 원산지 오인",
        "외국 기술제휴 오인",
        "비교 기준·최상급 표현",
        "소비자 기만·오인",
        "객관적 확인 없는 품질·효능 또는 화장품 범위 이탈",
        "저속·혐오 표현",
        "멸종위기종 가공품 함유 표현",
        "다른 제품 비방",
    ]
    mapping = []
    for letter, description in zip(all_items, descriptions):
        law_id = f"LAW_시행규칙_별표5-2{letter}"
        actual_types = sorted({r["type"] for r in rules if r["law_id"] == law_id})
        mapping.append(
            {
                "law_id": law_id,
                "rule_item": f"2{letter}",
                "schedule_id": groups[0 if letter in "가나카" else 1]["schedule_id"],
                "description": description,
                "violation_types": actual_types,
                "type_source": "현재 규칙 자산의 명시적 law_id/type 연결; 미연결은 빈 목록",
                "selection_requires_law_id": True,
            }
        )
    for group in groups:
        group["violation_types"] = sorted(
            {
                t
                for row in mapping
                if row["schedule_id"] == group["schedule_id"]
                for t in row["violation_types"]
            }
        )
    general = text7[text7.index("1. 일반기준") : text7.index("2. 개별기준")]
    qualifications = [
        {
            "item": "1가",
            "summary": "복수 위반: 무거운 처분 기준 적용. 복수 업무정지면 가장 무거운 기간에 나머지 각 기간의 1/2 가산, 최대 12개월",
        },
        {
            "item": "1나",
            "summary": "업무정지와 품목업무정지의 기간에 따라 전체 업무정지 적용 또는 병과",
        },
        {
            "item": "1다·라",
            "summary": "같은 위반의 차수는 최근 1년간 처분 이력 기준(머목은 2년). 실제 처분일/과징금 통보일과 재적발일 기준. 품목이 다르면 품목업무정지의 차수 기준 적용 제외. 전 차수 다음 차수 적용",
        },
        {
            "item": "1마",
            "summary": "처분 절차 중 같은 위반 반복: 진행 중 기준 기간의 1/2씩 가산, 최대 12개월",
        },
        {"item": "1바", "summary": "같은 위반 3차 이상은 과징금 부과대상 제외"},
        {
            "item": "1사",
            "summary": "등록 소재지에 제조시설이 전혀 없는 경우 등록취소; 본 광고 문구 표의 자동 계산 범위 밖",
        },
        {
            "item": "1아",
            "summary": "영 제2조제2호라목 책임판매업은 판매금지/판매업무정지를 수입대행금지/수입대행업무정지로 읽음",
        },
        {
            "item": "1자1",
            "summary": "공익상 필요, 기소유예/선고유예, 광고주 의사와 무관한 무단 광고 등은 1/2까지 감경 또는 면제 가능",
        },
        {
            "item": "1자2",
            "summary": "유통 보관 중 기능성 원료 변화에 의한 함량 미달, 위해 없는 비병원성 일반세균 오염 인정 등은 1/2까지 감경 가능; 모든 광고 위반에 일괄 적용하지 않음",
        },
    ]
    evidence = OUT / "penalty_schedule_source_excerpt.txt"
    evidence.write_text(
        "SOURCE: "
        + LAW.relative_to(ROOT).as_posix()
        + "\n\n"
        + general
        + "\n"
        + part
        + "\n\n"
        + text5[text5.index("2. 화장품 표시") :],
        encoding="utf-8",
    )
    pdf_url = "https://www.law.go.kr" + annex7.findtext("별표서식PDF파일링크")
    return {
        "schema_version": "1.0",
        "dataset_id": "D1",
        "built_date": DATE,
        "source": {
            "file": LAW.relative_to(ROOT).as_posix(),
            "sha256": digest(LAW),
            "law_id": root.findtext("기본정보/법령ID"),
            "promulgated_date": root.findtext("기본정보/공포일자"),
            "effective_date": root.findtext("기본정보/시행일자"),
            "annex_revision_date": "2025-02-07",
            "official_pdf_url": pdf_url,
            "official_pdf_table_visually_checked": True,
            "visual_check_date": DATE,
            "visually_checked_pdf_sha256": VISUALLY_AUDITED_PDF_SHA256,
            "latest_law_version_verified": False,
            "version_note": "기존 XML 스냅샷과 그 XML이 연결한 공식 별표 PDF 대조. 최신 본문 전체를 확인했다는 의미는 아님",
            "excerpt_file": evidence.relative_to(ROOT).as_posix(),
        },
        "schedules": groups,
        "law_id_mapping": mapping,
        "general_criteria": qualifications,
        "mapping_policy": {
            "lookup_key": "구체적인 별표5 law_id + 표시/광고 + 위반 차수",
            "violation_type_only_lookup_allowed": False,
            "unmapped_law_id_months": None,
            "blank_source_cell_months": None,
            "multiple_violations_auto_combined": False,
        },
        "limitations": [
            "level 2는 법적 적발 확정이 아니다. 처분 종류·차수·감경·가중은 개별 사실관계 및 처분권자 판단이 필요",
            "광고업무정지는 판매업무정지와 다름. 광고 정지 개월 수만으로 품목 매출이 0이 된다고 가정할 수 없음",
            "기준 매출×기간은 별도 가정에 따른 노출 시나리오일 뿐 법령이 정한 손실액이나 실제 최대 손실액이 아님",
            "가·나·카목 4차 이상 칸은 공란으로 null 유지. 직전 차수 값으로 채우지 않음",
        ],
        "detection_probability": None,
        "revenue_loss": None,
        "verified_against_raw": True,
        "rule_asset_hashes": {
            p.relative_to(ROOT).as_posix(): digest(p) for p in rule_files
        },
    }


def quantile(values, p):
    """Linear interpolation, h=(n-1)*p, equivalent to NumPy default linear."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (position - lo) * (ordered[hi] - ordered[lo])


def summarize_pairs(rows):
    ratios, signed, intervals = [], [], []
    zero_baselines = invalid_intervals = 0
    for row in rows:
        a, b = row["a"], row["b"]
        for arm in (a, b):
            if arm["impressions"] <= 0 or not 0 <= arm["clicks"] <= arm["impressions"]:
                raise ValueError("Invalid impressions/clicks in source")
        if a["clicks"] == 0:
            zero_baselines += 1
        else:
            effect = (b["clicks"] / b["impressions"]) / (
                a["clicks"] / a["impressions"]
            ) - 1
            signed.append(effect)
            ratios.append(abs(effect))
        interval = row.get("observed", {}).get("difference_95_interval_pp")
        if (
            interval is None
            or len(interval) != 2
            or not all(math.isfinite(x) for x in interval)
            or interval[0] > interval[1]
        ):
            invalid_intervals += 1
        else:
            intervals.append(not (interval[0] <= 0 <= interval[1]))
    points = {
        name: quantile(ratios, p)
        for name, p in [("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("p90", 0.9)]
    }
    return {
        "input_pair_count": len(rows),
        "relative_change_defined_count": len(ratios),
        "zero_baseline_pairs_excluded_from_relative_distribution": zero_baselines,
        "absolute_relative_ctr_change": {
            "formula": "abs((clicks_B / impressions_B) / (clicks_A / impressions_A) - 1)",
            "unit": "ratio",
            "quantiles": points,
            "quantiles_percent": {
                k: v * 100 if v is not None else None for k, v in points.items()
            },
        },
        "direction_counts": {
            "b_higher": sum(x > 0 for x in signed),
            "b_lower": sum(x < 0 for x in signed),
            "equal": sum(x == 0 for x in signed),
        },
        "interval_zero_exclusion": {
            "valid_interval_count": len(intervals),
            "invalid_or_missing_interval_count": invalid_intervals,
            "count": sum(intervals),
            "proportion": sum(intervals) / len(intervals) if intervals else None,
            "percent": 100 * sum(intervals) / len(intervals) if intervals else None,
            "definition": "기존 CTR 차이의 95% 구간이 0을 포함하지 않는 쌍의 비율",
            "multiple_comparison_adjusted": False,
        },
    }


def build_d5():
    rows = [
        json.loads(line)
        for line in PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({r["experiment_id"] for r in rows}) != len(rows):
        raise ValueError("Expected one comparison per experiment")
    result = summarize_pairs(rows)
    return {
        "schema_version": "1.0",
        "dataset_id": "D5",
        "built_date": DATE,
        "source": {
            "file": PAIRS.relative_to(ROOT).as_posix(),
            "sha256": digest(PAIRS),
            "official_url": "https://osf.io/download/3vqmp/",
            "documentation_url": "https://upworthy.natematias.com/about-the-archive.html",
            "quality_update_url": "https://upworthy.natematias.com/2024-06-upworthy-archive-update.html",
            "domain": "US news headline clicks",
            "subset": "exploratory; 148 prefiltered comparisons; no holdout access",
        },
        "method": {
            "weighting": "unweighted; one selected comparison per experiment",
            "quantile": "linear interpolation h=(n-1)*p; no winsorization or trimming",
            "arm_order": "lexicographic headline order; not winner/loser order",
            "confidence_interval": "reuse previously calculated Newcombe/Wilson unadjusted 95% difference intervals",
        },
        **result,
        "display_label": "다른 분야 실험에서 관찰된 문구 효과 크기를 참고한 가정 범위",
        "interpretation": [
            "148개 선별 표본의 기술통계. 뉴스 제목 문구의 일반적인 인과 효과 추정치가 아님",
            "절댓값 분포는 상승·하락을 모두 포함. 양수 분위수를 매출 상승률로 읽지 않음",
            "B/A 분모에 의존하므로 A/B를 교환하면 절대 상대 차이 크기도 달라짐",
            "0 미포함 비율은 다중비교 보정 전 개별 구간의 기술통계이며 확인된 효과의 비율로 단정하지 않음",
            "분포 수치에 표본 오차·선별 조건·시대·분야·언어 차이가 포함. 제품별 예측 구간이 아님",
        ],
        "allowed_use": "문구 변화 크기 설명 및 명시적으로 선택한 가정 범위의 참고",
        "automatic_cosmetics_revenue_transfer_allowed": False,
        "cosmetics_conversion_uplift": None,
        "cosmetics_revenue_uplift": None,
        "recommended_copy_specific_effects": None,
    }


def main():
    d1 = build_d1()
    save(OUT / "penalty_schedule.json", d1)
    d5 = build_d5()
    save(OUT / "copy_effect_size_distribution.json", d5)
    print(
        json.dumps(
            {
                "D1_schedules": len(d1["schedules"]),
                "D1_law_ids": len(d1["law_id_mapping"]),
                "D5_pairs": d5["input_pair_count"],
                "D5_percentiles": d5["absolute_relative_ctr_change"][
                    "quantiles_percent"
                ],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
