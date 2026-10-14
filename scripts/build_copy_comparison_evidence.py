"""Reproducible, exploratory headline comparisons; never cosmetics sales labels.

The optional download is one official public CSV, not a scraping loop.
Selection is based on experiment metadata and sample sizes, never CTR/winner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sales_forecast_reference" / "copy_comparison"
RAW = OUT.parent / "raw" / "upworthy_exploratory.csv"
URL = "https://osf.io/download/3vqmp/"
DOCS = "https://upworthy.natematias.com/about-the-archive.html"
UPDATE = "https://upworthy.natematias.com/2024-06-upworthy-archive-update.html"


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def wilson(clicks, impressions):
    """95% Wilson interval for a binomial proportion."""
    p = clicks / impressions
    z = 1.959963984540054
    den = 1 + z * z / impressions
    center = (p + z * z / (2 * impressions)) / den
    half = z * math.sqrt(p * (1 - p) / impressions + z * z / (4 * impressions**2)) / den
    return max(0.0, center - half), min(1.0, center + half)


def comparison(a, b):
    pa, pb = a["clicks"] / a["impressions"], b["clicks"] / b["impressions"]
    la, ua = wilson(a["clicks"], a["impressions"])
    lb, ub = wilson(b["clicks"], b["impressions"])
    # Newcombe hybrid-score interval for two independent proportions (B minus A).
    delta = pb - pa
    low = delta - math.sqrt((pb - lb) ** 2 + (ua - pa) ** 2)
    high = delta + math.sqrt((ub - pb) ** 2 + (pa - la) ** 2)
    return {
        "ctr_a": pa,
        "ctr_b": pb,
        "difference_b_minus_a_pp": 100 * delta,
        "difference_95_interval_pp": [100 * low, 100 * high],
        "relative_difference": (pb / pa - 1) if pa else None,
        "interval_includes_zero": low <= 0 <= high,
        "interval_method": "Newcombe hybrid score; Wilson 95%; unadjusted exploratory interval",
    }


def select_pairs(rows):
    by_test = defaultdict(list)
    for row in rows:
        if row.get("clickability_test_id"):
            by_test[row["clickability_test_id"]].append(row)
    counts = defaultdict(int)
    selected = []
    for test_id, arms in sorted(by_test.items()):
        # Entire test excluded if any package date is suspect or unknown.
        try:
            days = [date.fromisoformat(r["created_at"][:10]) for r in arms]
        except (KeyError, ValueError):
            counts["tests_excluded_missing_date"] += 1
            continue
        if any(date(2013, 6, 25) <= d <= date(2014, 1, 10) for d in days):
            counts["tests_excluded_randomization_risk_period"] += 1
            continue
        if any(str(r.get("problem", "0")) == "1" for r in arms):
            counts["tests_excluded_problem_flag"] += 1
            continue
        groups = defaultdict(list)
        for row in arms:
            if row.get("eyecatcher_id"):
                groups[row["eyecatcher_id"]].append(row)
        for image_id, group in sorted(groups.items()):
            if len(group) != 2 or len({r["headline"].strip() for r in group}) != 2:
                continue
            ordered = sorted(group, key=lambda r: r["headline"].strip())
            normalized = []
            for row in ordered:
                try:
                    n, k = int(row["impressions"]), int(row["clicks"])
                except (ValueError, KeyError):
                    break
                if n < 1000 or not 0 <= k <= n:
                    break
                normalized.append(
                    {
                        "copy_text": row["headline"].strip(),
                        "impressions": n,
                        "clicks": k,
                    }
                )
            if len(normalized) != 2:
                continue
            a, b = normalized
            # Allocation audit only; this does not establish that randomization succeeded.
            ratio = max(a["impressions"], b["impressions"]) / min(
                a["impressions"], b["impressions"]
            )
            if ratio > 1.2:
                counts["candidate_pairs_excluded_allocation_ratio_gt_1_2"] += 1
                continue
            selected.append(
                {
                    "comparison_id": f"UPW_{test_id}_{image_id}",
                    "experiment_id": test_id,
                    "image_id": image_id,
                    "created_dates": sorted({d.isoformat() for d in days}),
                    "domain": "US_news_headline; not cosmetics",
                    "evidence_scope": "exploratory_same_test_same_image_click_comparison",
                    "selection": "exactly_two_packages_per_image; >=1000_impressions_each; ratio<=1.2; first_image_id_per_test",
                    "arm_order": "headline_lexicographic; not chosen by outcome",
                    "a": a,
                    "b": b,
                    "observed": comparison(a, b),
                    "price": None,
                    "promotion": None,
                    "audience_details": None,
                    "orders": None,
                    "units_sold": None,
                    "revenue": None,
                    "eligible_for_cosmetics_sales_prediction": False,
                    "judge_level": None,
                    "source_url": URL,
                }
            )
            break  # At most one comparison per test; no repeated-test pseudo-replication.
    counts["input_tests"] = len(by_test)
    counts["eligible_comparisons"] = len(selected)
    return selected, dict(counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_bytes(urlopen(URL, timeout=60).read())
    with RAW.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    pairs, counts = select_pairs(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "headline_comparisons.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs),
        encoding="utf-8",
    )
    write_json(
        OUT / "manifest.json",
        {
            "collected_date": "2026-10-14",
            "download_url": URL,
            "sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
            "raw_rows": len(rows),
            "raw_bytes": RAW.stat().st_size,
            "license": "CC BY 4.0; attribute Matias, Munger, Le Quere, Ebersole (2021)",
            "doi": "https://doi.org/10.1038/s41597-021-00934-7",
            "documentation_url": DOCS,
            "quality_update_url": UPDATE,
            "raw_problem_column_present": "problem" in rows[0],
            "risk_exclusion": "2013-06-25 through 2014-01-10 inclusive; entire tests",
            "counts": counts,
            "holdout_accessed": False,
            "confirmatory_accessed": False,
            "display_selection": "first 3 eligible IDs; not strongest effects",
            "use": "method demonstration, not cosmetics forecast calibration",
        },
    )
    write_json(OUT / "display_examples.json", pairs[:3])
    market = ROOT / "data" / "top_product_copies" / "wrinkle_serum_sample"
    with (market / "products.csv").open(encoding="utf-8-sig", newline="") as stream:
        products = list(csv.DictReader(stream))
    copies = [
        json.loads(line)
        for line in (market / "copies.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    cards = []
    for product in products:
        product_copies = [c for c in copies if c["product_id"] == product["product_id"]]
        cards.append(
            {
                "product_id": product["product_id"],
                "brand": product["brand"],
                "product_name": product["product_name"],
                "market_observed_date": product["collected_date"],
                "market_source_url": product["product_url"],
                "market_conditions": {
                    k: product.get(k)
                    for k in [
                        "ranking",
                        "ranking_type",
                        "ranking_period",
                        "sale_price_krw",
                        "discount_percent_displayed",
                        "bundle",
                        "sale_event",
                        "review_count",
                        "rating",
                        "celebrity_badge_exposed",
                        "functional_type_status",
                    ]
                },
                "observed_copies": [
                    {
                        k: c.get(k)
                        for k in [
                            "copy_id",
                            "copy_text",
                            "위치",
                            "문구 유형",
                            "시험 조건 표기 여부",
                            "source_url",
                        ]
                    }
                    for c in product_copies
                ],
                "comparison_status": "cosmetics_copy_effect_not_measured",
                "hypothesis": "동일 SKU·가격·구성·이미지·타깃·기간을 고정하고, 승인된 문구의 소구 방식만 바꿔 CTR을 비교한다.",
                "required_controls": [
                    "SKU",
                    "price",
                    "discount",
                    "bundle",
                    "image",
                    "placement",
                    "audience",
                    "period",
                    "attribution_window",
                ],
                "required_observations_per_arm": [
                    "copy_text",
                    "impressions",
                    "clicks",
                    "orders",
                    "units",
                    "net_revenue",
                    "ad_cost",
                ],
                "upworthy_link_type": "comparison_method_only; no transferred_uplift",
                "predicted_revenue": None,
                "predicted_units": None,
                "copy_uplift": None,
                "judge_level": None,
            }
        )
    write_json(OUT / "cosmetics_evidence_cards.json", cards)
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
