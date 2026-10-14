"""
[scripts/judge_market_copies.py]
수집한 시장 문구(올리브영 상위 세럼 + 시장 참고 제품)를 우리 규칙 판정기(R0)로 검토한다.

목적
    "잘 팔리는 제품들은 어떤 문구를 쓰는가"(시장 관찰)와
    "그 문구가 규정상 어느 수준인가"(우리 판정 기준)를 같은 표에서 보여준다.

해석 원칙
- 외부 제품의 시험 원자료를 모르므로 보유 근거는 '없음'으로 둔다.
  → 수치·실증 표현은 '근거 확인 필요(1)'로 나온다. 위반 확정이 아니다.
- 기능성 유형은 공개 고시로 확인된 것만 쓴다. 확인되지 않은 제품은
  '일반'과 '기능성'으로 두 번 판정해 결과가 갈리면 '기능성 심사 여부 확인 필요'로 표시한다.
- 원본 수집 파일(copies.jsonl 등)의 judge_level 은 바꾸지 않는다. 결과는 별도 파일에 쓴다.
- 판정 결과를 매출·순위와 인과로 연결하지 않는다.

실행 (프로젝트 루트):  uv run python scripts/judge_market_copies.py
출력:
    data/sales_forecast_reference/copy_comparison/market_copy_judgements.jsonl
    data/sales_forecast_reference/copy_comparison/market_copy_judgement_summary.md
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services.market_evidence import load_reference_catalog  # noqa: E402
from cosmetic_agent.common.config import settings  # noqa: E402
from cosmetic_agent.domain.rules import RuleEngine  # noqa: E402
from cosmetic_agent.models.rule_judge import RuleJudgeModel  # noqa: E402

OUT_DIR = ROOT / "data" / "sales_forecast_reference" / "copy_comparison"
OUT_JSONL = OUT_DIR / "market_copy_judgements.jsonl"
OUT_MD = OUT_DIR / "market_copy_judgement_summary.md"
PRODUCTS_CSV = ROOT / "data" / "top_product_copies" / "wrinkle_serum_sample" / "products.csv"

# 공개 고시 표기 → 우리 기능성 유형 이름
FUNCTIONAL_ALIASES = {
    "미백": "피부 미백", "피부 미백": "피부 미백",
    "주름 개선": "주름 개선", "주름개선": "주름 개선",
    "탈모 증상 완화": "탈모 증상 완화", "여드름성 피부 완화": "여드름성 피부 완화",
    "자외선 차단": "자외선 차단",
}
ALL_FUNCTIONAL = ["피부 미백", "주름 개선", "탈모 증상 완화", "여드름성 피부 완화", "자외선 차단"]

# 두 수집본(상위 세럼 샘플 7종 / 시장 참고 appeal_tags)의 태그를 하나의 문구 유형 체계로 맞춘다
APPEAL_TYPES = ["효능 수치형", "시험·검사 표방형", "성분 소구형", "효능 서술형", "사용감형", "구성·혜택형", "비교·순위형", "기타"]
TAG_ALIASES = {
    "효능 수치형": "효능 수치형", "수치": "효능 수치형",
    "시험·검사 표방형": "시험·검사 표방형", "시험 언급": "시험·검사 표방형",
    "성분 소구형": "성분 소구형", "성분 강조": "성분 소구형",
    "효능 서술형": "효능 서술형", "보습": "효능 서술형", "장벽": "효능 서술형", "지속 시간": "효능 서술형",
    "층수": "효능 서술형", "토닝": "효능 서술형", "기능성 범위": "효능 서술형",
    "사용감형": "사용감형", "제형 강조": "사용감형", "제형 차별화": "사용감형", "복합 제형": "사용감형",
    "제형/pH": "사용감형", "사용 편의": "사용감형", "복합 용도": "사용감형",
    "구성·혜택형": "구성·혜택형", "증정/구성": "구성·혜택형", "구성/수량": "구성·혜택형", "리필": "구성·혜택형",
    "단독 구성": "구성·혜택형", "배송 혜택": "구성·혜택형", "용량": "구성·혜택형",
    "비교·순위형": "비교·순위형", "사회적 증거": "비교·순위형", "순위": "비교·순위형", "월간 순위": "비교·순위형",
}


def normalize_tags(tags: list[str]) -> list[str]:
    out = {TAG_ALIASES.get(t, "기타") for t in tags or []} or {"기타"}
    return [t for t in APPEAL_TYPES if t in out]


LEVEL_LABELS = {0: "규칙상 걸리는 표현 없음", 1: "근거 확인 필요", 2: "표현 주의"}
DISCLAIMER = "공개 정보로 검토한 시스템 출력이며, 해당 브랜드의 법 위반이나 시험 자료 부재를 확정하지 않습니다."


def _rules_version() -> str:
    h = hashlib.sha256()
    for path in (settings.BANNED_TERMS_PATH, settings.BANNED_TERMS_PATH.parent / "rule_patterns.json"):
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:12]


def _confirmed_functional() -> dict[str, list[str]]:
    """products.csv 에서 공개 고시로 확인된 기능성 유형만 읽는다."""
    if not PRODUCTS_CSV.exists():
        return {}
    out: dict[str, list[str]] = {}
    with open(PRODUCTS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = [t.strip() for t in (row.get("functional_type") or "").split(";") if t.strip()]
            types = [FUNCTIONAL_ALIASES[t] for t in raw if t in FUNCTIONAL_ALIASES]
            if types:
                out[row["product_id"]] = types
    return out


def judge_copy(judge: RuleJudgeModel, text: str, confirmed: list[str] | None) -> dict[str, Any]:
    """기능성 확인 여부에 따라 한 번 또는 두 번 판정한다."""
    if confirmed:
        res = judge.judge_product(text, {"category": "기능성", "functional_type": confirmed, "owned_evidence": []})
        return {"res": res, "functional_basis": "공개 고시 확인: " + ", ".join(confirmed),
                "depends_on_functional_status": False, "level_if_general": None}

    as_general = judge.judge_product(text, {"category": "일반", "functional_type": None, "owned_evidence": []})
    as_functional = judge.judge_product(
        text, {"category": "기능성", "functional_type": ALL_FUNCTIONAL, "owned_evidence": []})
    depends = as_general["model_level"] != as_functional["model_level"]
    # 확인되지 않은 쪽을 위반으로 단정하지 않도록, 결과가 갈리면 기능성 가정 결과를 대표로 쓰고 표시한다
    return {"res": as_functional if depends else as_general,
            "functional_basis": "기능성 유형 미확인",
            "depends_on_functional_status": depends,
            "level_if_general": as_general["model_level"] if depends else None,
            "type_if_general": as_general["violation_type"] if depends else None}


def build() -> list[dict[str, Any]]:
    catalog = load_reference_catalog()
    confirmed = _confirmed_functional()
    judge = RuleJudgeModel(RuleEngine())
    version = _rules_version()
    rows = []
    for pid, card in catalog.items():
        conditions = card.get("market_conditions") or {}
        for copy in card.get("observed_copies", []):
            out = judge_copy(judge, copy["copy_text"], confirmed.get(pid))
            res = out.pop("res")
            level = res["model_level"]
            label = LEVEL_LABELS[level]
            if out["depends_on_functional_status"]:
                label += " · 기능성 심사 여부 확인 필요"
            rows.append({
                "copy_id": copy["copy_id"],
                "product_id": pid,
                "brand": card.get("brand"),
                "copy_text": copy["copy_text"],
                "위치": copy.get("위치"),
                "문구 유형": normalize_tags(copy.get("문구 유형") or []),
                "원본 태그": copy.get("문구 유형") or [],
                "ranking": conditions.get("ranking"),
                "review_count": conditions.get("review_count"),
                "judge_backend": "rule-R0",
                "rules_version": version,
                "judged_on": date.today().isoformat(),
                "judge_level": level,
                "display_label": label,
                "violation_type": res["violation_type"],
                "matched": [h["matched"] for h in res.get("rule_hits", [])],
                "basis_ids": res.get("basis_ids", []),
                "next_test": res.get("next_test"),
                "owned_evidence_assumption": "외부 제품 시험 원자료 미확보 → 보유 근거 없음으로 판정",
                **out,
                "disclaimer": DISCLAIMER,
            })
    return rows


def summarize(rows: list[dict[str, Any]]) -> str:
    n = len(rows)
    by_level = Counter(r["judge_level"] for r in rows)
    by_type = defaultdict(Counter)
    for r in rows:
        for tag in r["문구 유형"]:
            by_type[tag][r["judge_level"]] += 1
    ranked = [r for r in rows if str(r.get("ranking") or "").isdigit()]
    lines = [
        "# 시장 문구 판정 분포 (R0 규칙 판정기)",
        "",
        f"판정일 {date.today().isoformat()} · 문구 {n}개 · 제품 {len({r['product_id'] for r in rows})}개 · 규칙 버전 `{rows[0]['rules_version'] if rows else '-'}`",
        "",
        f"> {DISCLAIMER} 외부 제품의 시험 원자료가 없으므로 수치·시험 표현은 '근거 확인 필요'로 분류됩니다.",
        "",
        "## 전체",
        "",
        "| 판정 | 문구 수 | 비율 |",
        "|---|---:|---:|",
    ]
    for lv in (0, 1, 2):
        lines.append(f"| {LEVEL_LABELS[lv]} ({lv}) | {by_level[lv]} | {by_level[lv] / n * 100:.0f}% |" if n else "")
    depends = sum(r["depends_on_functional_status"] for r in rows)
    lines += ["", f"기능성 심사 여부에 따라 판정이 갈리는 문구: {depends}개", "",
              "## 문구 유형별 (유형 복수 선택 허용)", "",
              "| 문구 유형 | 0 | 1 | 2 | 합계 |", "|---|---:|---:|---:|---:|"]
    for tag in [t for t in APPEAL_TYPES if t in by_type]:
        c = by_type[tag]
        lines.append(f"| {tag} | {c[0]} | {c[1]} | {c[2]} | {sum(c.values())} |")
    lines += ["", "## 1·2 판정 문구", "", "| 브랜드 | 순위 | 문구 | 판정 | 걸린 표현 |", "|---|---:|---|---|---|"]
    for r in sorted(rows, key=lambda r: (-r["judge_level"], r["product_id"])):
        if r["judge_level"] >= 1:
            text = r["copy_text"].replace("\n", " ").replace("|", "/")
            lines.append(f"| {r['brand']} | {r.get('ranking') or '-'} | {text} | {r['display_label']} ({r['violation_type']}) | "
                         f"{', '.join(r['matched']) or '-'} |")
    lines += ["", "## 해석 범위", "",
              f"- 순위가 확인된 제품의 문구 {len(ranked)}개 포함. 순위·리뷰는 매출이 아니며, 판정 결과와 판매 성과의 인과를 주장하지 않습니다.",
              "- 발표에서는 브랜드명을 가리고 '상위 제품 문구 중 N%가 근거 확인 필요 수준' 형태로만 인용합니다.",
              "- 규칙 판정기(R0)는 dev 골든셋에 맞춰 만든 규칙입니다. GPT 판정(R1·R2)과 비교해 보완합니다.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    rows = build()
    OUT_JSONL.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    OUT_MD.write_text(summarize(rows), encoding="utf-8")
    counts = Counter(r["judge_level"] for r in rows)
    print(f"{len(rows)} copies judged → 0:{counts[0]} 1:{counts[1]} 2:{counts[2]}")
    print(f"saved: {OUT_JSONL.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")
