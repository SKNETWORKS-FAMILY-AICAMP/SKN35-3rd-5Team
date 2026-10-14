"""
[app/services/market_judgements.py]
시장 문구 판정 결과(scripts/judge_market_copies.py 출력)를 화면에서 읽는 도우미.

판정은 공개 정보 기준 시스템 출력이다. 브랜드의 법 위반을 확정하지 않는다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JUDGEMENTS = ROOT / "data" / "sales_forecast_reference" / "copy_comparison" / "market_copy_judgements.jsonl"

# st.badge(color=..., icon=...) 에 바로 넣는 값
JUDGE_BADGE = {0: ("green", ":material/check_circle:"), 1: ("orange", ":material/help:"), 2: ("red", ":material/error:")}


def load_copy_judgements(path: Path = JUDGEMENTS) -> dict:
    """copy_id → 판정 행. 파일이 없으면 빈 dict (화면은 판정 없이 동작)."""
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["copy_id"]: row for row in rows}


def judgement_counts(judgements: dict, product_ids=None) -> dict:
    """판정 수준별 문구 수. product_ids 를 주면 해당 제품만 센다."""
    counts = {0: 0, 1: 0, 2: 0}
    for row in judgements.values():
        if product_ids is None or row["product_id"] in product_ids:
            counts[row["judge_level"]] += 1
    return counts
