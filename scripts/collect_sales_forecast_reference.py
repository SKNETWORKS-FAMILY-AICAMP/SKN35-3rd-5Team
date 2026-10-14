"""Curated public evidence plus one author-published experiment; no scraping loop.

Run with --download-benchmark to retrieve the author's linked CSV (about 4 MB).
No API keys, Qdrant writes, synthetic outcomes, or cosmetics forecasts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sales_forecast_reference"
COLLECTED = "2026-10-14"
HILLSTROM = (
    "https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html"
)
SOURCES = [
    {
        "source_id": "KIS_QOO10_20250915",
        "url": "https://file.koreainvestment.com/Storage/research/research05/20250915065938043_ko.pdf",
        "publisher": "한국투자증권",
        "source_kind": "secondary_research_table",
        "published_date": "2025-09-15",
        "locator": "PDF 3페이지 표2, 큐텐 자료 인용",
        "reuse_note": "보고서 원본 및 표 전체는 재배포하지 않음. 관련 제품의 제한된 수치 사실만 출처와 기록",
    },
    {
        "source_id": "TIKTOK_VISIONARY",
        "url": "https://ads.tiktok.com/business/en/inspiration/visionary-seed",
        "publisher": "TikTok for Business",
        "source_kind": "platform_case_study",
        "published_date": None,
        "locator": "The Result; July 2024 Numbuzin",
        "reuse_note": "원문 복사 대신 성과 수치·조건 요약",
    },
    {
        "source_id": "CRITEO_ALLBEAUTY",
        "url": "https://www.criteo.com/success-stories/allbeauty/",
        "publisher": "Criteo",
        "source_kind": "platform_case_study",
        "published_date": None,
        "locator": "Allbeauty 사례 본문과 상단 지표",
        "reuse_note": "상대 지표; 원시 로그 미공개",
    },
    {
        "source_id": "CRITEO_BIODERMA",
        "url": "https://www.criteo.com/success-stories/bioderma/",
        "publisher": "Criteo",
        "source_kind": "platform_case_study",
        "published_date": None,
        "locator": "Bioderma 사례 Results",
        "reuse_note": "상대 지표; 원시 로그 미공개",
    },
    {
        "source_id": "REDDIT_ULTA",
        "url": "https://www.business.reddit.com/success-stories/advertisers/ulta-dpa",
        "publisher": "Reddit for Business",
        "source_kind": "platform_case_study",
        "published_date": None,
        "locator": "Ulta DPA 사례 상단 지표와 광고 예시",
        "reuse_note": "짧은 광고 문구 1개만 발췌; 문구별 성과는 미공개",
    },
    {
        "source_id": "AMAZON_EOS",
        "url": "https://advertising.amazon.com/en-us/library/case-studies/tinuiti-skai-eos-category-launch",
        "publisher": "Amazon Ads; 실적 자료 제공 eos",
        "source_kind": "platform_case_study",
        "published_date": None,
        "locator": "Results; Sources: eos U.S. 2026",
        "reuse_note": "캠페인 수준의 성과 요약; 원시 측정 데이터 미공개",
    },
    {
        "source_id": "HILLSTROM_2008",
        "url": HILLSTROM,
        "publisher": "Kevin Hillstrom / MineThatData",
        "source_kind": "author_published_randomized_dataset",
        "published_date": "2008-03-20",
        "locator": "원저자 실험 설명 및 CSV 링크",
        "reuse_note": "표준 재배포 라이선스 미확인. 원본 CSV는 로컬 raw/에 보관하고 Git 제외",
    },
    {
        "source_id": "CRITEO_UPLIFT",
        "url": "https://ailab.criteo.com/criteo-uplift-prediction-dataset/",
        "publisher": "Criteo AI Lab",
        "source_kind": "author_published_randomized_dataset",
        "published_date": "2018-05-31",
        "locator": "ERRATUM 이후 unbiased release",
        "reuse_note": "약297MB 압축본은 이번에 다운로드하지 않음. 익명 피처·광고 처리 실험으로 문구별 매출 모델 아님",
    },
]


def save_json(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def save_jsonl(name, rows):
    (OUT / name).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def collect_curated():
    OUT.mkdir(parents=True, exist_ok=True)
    source_urls = {s["source_id"]: s["url"] for s in SOURCES}
    save_json("sources.json", [{**s, "accessed_date": COLLECTED} for s in SOURCES])
    product_sales = []
    for identity, name, amount, rank, reference in [
        (
            "QOO10_ANUA_PDRN_202509",
            "아누아 PDRN 히알루론산 100+ 세럼",
            120000000,
            16,
            "OY_A000000222698",
        ),
        ("QOO10_AESTURA_202509", "에스트라 아토베리어365 크림", 110000000, 19, None),
    ]:
        product_sales.append(
            {
                "observation_id": identity,
                "source_id": "KIS_QOO10_20250915",
                "product_label": name,
                "platform": "Qoo10 Japan",
                "market": "JP",
                "period_start": "2025-08-31T17:00:00+09:00",
                "period_end": "2025-09-12T23:59:00+09:00",
                "collected_date": COLLECTED,
                "event": "メガ割/메가와리",
                "metric": "reported_event_sales_amount",
                "value": amount,
                "currency": "JPY",
                "value_precision": "보고서0.1억엔 단위;정확한 원장 금액 아님",
                "event_rank": rank,
                "net_revenue": None,
                "units_sold": None,
                "sales_definition": "보고서 판매액;반품·취소로 실제 기업 실적과 다를 수 있음",
                "copy_text": None,
                "price_during_event": None,
                "bundle_during_event": None,
                "linked_sample_product_id": reference,
                "link_type": "product_family_reference_only" if reference else None,
                "exact_sku_match_verified": False,
                "same_period_copy_available": False,
                "eligible_for_copy_sales_training": False,
                "copy_effect_identified": False,
                "source_url": source_urls["KIS_QOO10_20250915"],
                "limitations": "2025일본 행사 제품 표기와 2026한국 올리브영 구성은 동일 판매 SKU로 확정할 수 없음.현 가격으로 나눠 수량 추정 금지",
            }
        )
    save_jsonl("product_sales_observations.jsonl", product_sales)

    cases = [
        {
            "case_id": "NUMBUZIN_TIKTOK_MY",
            "source_id": "TIKTOK_VISIONARY",
            "brand": "Numbuzin/넘버즈인",
            "platform": "TikTok Shop",
            "market": "MY",
            "period": "2024-07",
            "scope": "brand_campaign_ad_format",
            "conditions": [
                "제휴 크리에이터 영상",
                "소재 A/B 테스트 후 예산 배분",
                "LIVE/Video/Product Shopping Ads",
            ],
            "copy_text": None,
            "metrics": [
                {
                    "metric": "ROAS",
                    "value": 23,
                    "unit": "ratio",
                    "operator": "gt",
                    "format": "PSA",
                    "definition": "헤더는>23x,본문은23x로 표기;하한으로 보수적 기록",
                },
                {
                    "metric": "ROAS",
                    "value": 19,
                    "unit": "ratio",
                    "operator": "gt",
                    "format": "VSA affiliate",
                    "definition": "헤더는>19x,본문은19x로 표기;하한으로 기록",
                },
                {
                    "metric": "ROAS",
                    "value": 5.2,
                    "unit": "ratio",
                    "operator": "gt",
                    "format": "LSA",
                    "definition": "평균 ROAS 하한",
                },
                {
                    "metric": "purchase_rate",
                    "value": 18.2,
                    "unit": "percent",
                    "operator": "eq",
                    "format": "combined",
                    "definition": "공개 평균 구매율;분모와 귀속 기간 세부 미공개",
                },
            ],
            "limitations": "같은 글에 ANUA가 등장하지만 수치 성과는 넘버즈인.아누아 및 개별 문구에 전용 금지",
        },
        {
            "case_id": "ALLBEAUTY_CRITEO",
            "source_id": "CRITEO_ALLBEAUTY",
            "brand": "Allbeauty",
            "platform": "Criteo / retailer website",
            "market": "EMEA;UK retailer",
            "period": None,
            "scope": "retailer_campaign",
            "conditions": [
                "블랙프라이데이·크리스마스 시즌",
                "리타게팅",
                "동시에 웹사이트 UX 개선",
            ],
            "copy_text": None,
            "metrics": [
                {
                    "metric": "cost_of_sales_change",
                    "value": -22,
                    "unit": "percent",
                    "operator": "eq",
                },
                {
                    "metric": "sales_change_source_label",
                    "value": 7,
                    "unit": "percent",
                    "operator": "eq",
                    "definition": "원문 Sales;상품 판매 수량으로 바꾸지 않음",
                },
                {
                    "metric": "revenue_change",
                    "value": 14,
                    "unit": "percent",
                    "operator": "eq",
                },
            ],
            "limitations": "집계 범위·연도·절대 매출·Sales의 주문/수량 정의 미공개.문구만 변경한 실험 아님",
        },
        {
            "case_id": "BIODERMA_CRITEO",
            "source_id": "CRITEO_BIODERMA",
            "brand": "Bioderma",
            "platform": "Criteo / marketplaces",
            "market": "TR",
            "period": None,
            "scope": "brand_full_funnel_campaign",
            "conditions": [
                "마켓플레이스 데이터 활용",
                "0~60일 관심자 세그먼트",
                "공동 브랜드 소재·딥링크",
                "오프사이트 리타게팅",
            ],
            "copy_text": None,
            "metrics": [
                {
                    "metric": "ROAS_ratio_vs_previous_setup",
                    "value": 4,
                    "unit": "multiple",
                    "operator": "approx",
                },
                {
                    "metric": "CPC_change",
                    "value": -65,
                    "unit": "percent",
                    "operator": "eq",
                },
            ],
            "limitations": "약4배는 ROAS 절대값4와 다름.정확 기간·소재별 수치·원시 로그 미공개",
        },
        {
            "case_id": "ULTA_REDDIT_DPA",
            "source_id": "REDDIT_ULTA",
            "brand": "Ulta Beauty",
            "platform": "Reddit DPA",
            "market": "US",
            "period": "holiday season;연도 미공개",
            "scope": "retailer_catalog_campaign",
            "conditions": [
                "DPA 카탈로그 자동 상품 선택",
                "리타게팅",
                "추수감사절·연말 시즌",
            ],
            "copy_text": "It's an add to bag kind of day/week/month/year.",
            "metrics": [
                {
                    "metric": "ROAS_change_vs_previous_year",
                    "value": 66,
                    "unit": "percent",
                    "operator": "eq",
                },
                {
                    "metric": "ROAS",
                    "value": 9,
                    "unit": "ratio",
                    "operator": "eq",
                    "definition": "추수감사절 DPA 피크",
                },
                {
                    "metric": "ROAS_change_post_holiday",
                    "value": 34,
                    "unit": "percent",
                    "operator": "eq",
                    "definition": "비교 기준 세부 미공개",
                },
            ],
            "limitations": "광고 예시와 캠페인 성과가 같은 페이지에 있지만 해당 문구 단독 성과가 아님.효능 주장 없는 혜택/구매 유도 예시",
        },
        {
            "case_id": "EOS_AMAZON_2026",
            "source_id": "AMAZON_EOS",
            "brand": "eos body mist line",
            "platform": "Amazon Ads",
            "market": "US",
            "period": "2026-01~2026-02",
            "scope": "product_line_launch_campaign",
            "conditions": [
                "검색60%·DSP40% 매체 구성",
                "상위 퍼널 Big Game 광고",
                "예산 자동화·dayparting",
                "파트너 iROAS 측정",
            ],
            "copy_text": None,
            "metrics": [
                {
                    "metric": "ROAS",
                    "value": 12,
                    "unit": "ratio",
                    "operator": "eq",
                    "definition": "검색+Amazon DSP",
                },
                {
                    "metric": "search_share_of_voice",
                    "value": 6,
                    "unit": "percent",
                    "operator": "eq",
                },
                {
                    "metric": "launch_sales_above_forecast",
                    "value": 42,
                    "unit": "percent",
                    "operator": "eq",
                    "definition": "전년 대비 증가 또는 문구 개선율 아님",
                },
                {
                    "metric": "incremental_share_of_branded_search_sales",
                    "value": 81,
                    "unit": "percent",
                    "operator": "eq",
                    "definition": "Big Game branded search 귀속 판매 중;전체 판매의81%로 해석 금지",
                },
                {
                    "metric": "iROAS_change_vs_historical_branded_search",
                    "value": 197,
                    "unit": "percent",
                    "operator": "eq",
                },
            ],
            "limitations": "플랫폼 공개 사례의 파트너 측정치.실험 원시 자료·표본·오차 미공개;문구 단독 효과 아님",
        },
    ]
    for case in cases:
        case.update(
            {
                "collected_date": COLLECTED,
                "source_url": source_urls[case["source_id"]],
                "eligible_for_copy_sales_training": False,
                "copy_effect_identified": False,
                "absolute_revenue": None,
                "units_sold": None,
                "ad_spend": None,
                "raw_logs_available": False,
            }
        )
    save_jsonl("beauty_campaign_cases.jsonl", cases)
    sample_path = ROOT / "data/top_product_copies/wrinkle_serum_sample/products.csv"
    with sample_path.open(encoding="utf-8-sig", newline="") as stream:
        products = list(csv.DictReader(stream))
    coverage = []
    for product in products:
        coverage.append(
            {
                "product_id": product["product_id"],
                "brand": product["brand"],
                "copy_reference_file": "../top_product_copies/wrinkle_serum_sample/copies.jsonl",
                "copy_collected_date": product["collected_date"],
                "price_snapshot_krw": float(product["sale_price_krw"]),
                "price_is_from": product["price_is_from"].lower() == "true",
                "impressions": None,
                "clicks": None,
                "purchases": None,
                "units_sold": None,
                "net_revenue": None,
                "same_period_copy_performance_rows": 0,
                "related_public_observation_ids": [
                    s["observation_id"]
                    for s in product_sales
                    if s["linked_sample_product_id"] == product["product_id"]
                ],
                "forecast_readiness": "insufficient_matched_data",
                "allowed_output": "조건을 입력한 가정 기반 시나리오;문구별 검증 예측 불가",
            }
        )
    save_jsonl("sample_product_coverage.jsonl", coverage)
    save_json(
        "benchmark_catalog.json",
        [
            {
                "dataset_id": "hillstrom_2008",
                "source_id": "HILLSTROM_2008",
                "expected_rows": 64000,
                "domain": "mens/womens merchandise retail email;cosmetics 아님",
                "treatment": "Mens E-Mail/Womens E-Mail/No E-Mail 무작위 배정",
                "outcomes": ["visit", "conversion", "spend"],
                "post_period": "2주",
                "can_validate": [
                    "구매자 비율 추정",
                    "고객당 금액·불확실성",
                    "발송 대 미발송 실험 비교",
                ],
                "cannot_validate": [
                    "화장품 문구 효과",
                    "원화 매출",
                    "판매 상품 개수",
                    "세럼 제품별 전환율",
                ],
                "download_requested": True,
            },
            {
                "dataset_id": "criteo_uplift_unbiased",
                "source_id": "CRITEO_UPLIFT",
                "expected_rows": 13979592,
                "downloaded": False,
                "reason": "압축 약297MB;원시 수집은 보류",
                "outcomes": ["visit", "conversion"],
                "cannot_validate": [
                    "광고 원문·이미지에 따른 매출",
                    "상품 개수",
                    "금액 예측",
                ],
                "warning": "구버전 누수 수정본 선택.비균일 서브샘플링으로 원래 절대 광고 증분 수준 복원 불가",
            },
        ],
    )
    save_json(
        "forecast_input_template.json",
        {
            "record_kind": "scenario_assumptions_not_observed",
            "status": "awaiting_explicit_assumptions",
            "product_id": None,
            "copy_id": None,
            "period_start": None,
            "period_end": None,
            "forecast_population": "planned_clicks",
            "planned_clicks": None,
            "purchase_probability": {
                "low": None,
                "central": None,
                "high": None,
                "denominator": "clicks",
                "basis_source": None,
            },
            "orders_per_buyer": None,
            "units_per_order": None,
            "net_revenue_per_order_krw": None,
            "price_krw": None,
            "bundle": None,
            "discount_pct": None,
            "audience": None,
            "placement": None,
            "copy_lift": {"value": None, "identified": False},
            "expected_buyers": None,
            "expected_orders": None,
            "expected_units": None,
            "expected_net_revenue_krw": None,
            "display_label": "가정 기반 시나리오;학습된 화장품 문구 성과 예측이 아님",
            "formulas": {
                "expected_buyers": "planned_clicks * purchase_probability",
                "expected_orders": "expected_buyers * orders_per_buyer",
                "expected_units": "expected_orders * units_per_order",
                "expected_net_revenue_krw": "expected_orders * net_revenue_per_order_krw",
            },
            "guardrails": [
                "미확인 값은0으로 채우지 않음",
                "구매자 수·주문 수·상품 개수 구분",
                "ROAS 상대 개선율을 CVR로 바꾸지 않음",
                "다른 업종 실험의 구매율을 자사 제품에 전용하지 않음",
                "미식별 문구별 증가율을 만들지 않음",
            ],
        },
    )
    print(
        json.dumps(
            {
                "sources": len(SOURCES),
                "product_sales_observations": len(product_sales),
                "beauty_campaign_cases": len(cases),
                "campaign_metrics": sum(len(c["metrics"]) for c in cases),
                "sample_product_coverage": len(coverage),
                "matched_copy_sales_training_rows": 0,
            }
        )
    )


class CsvLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and "DataMiningChallenge" in href and ".csv" in href:
            self.links.append(urljoin(HILLSTROM, href))


def fetch(url):
    request = Request(url, headers={"User-Agent": "SKN-Cosmetic-Project-Research/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read(10_000_001), response.geturl()


def download_benchmark():
    manifest = {
        "dataset_id": "hillstrom_2008",
        "accessed_date": COLLECTED,
        "source_page": HILLSTROM,
        "status": "not_downloaded",
        "license": "원저자 공개 연구 과제;표준 재배포 라이선스 미확인",
        "allowed_use": "local_method_validation_only;not_cosmetics_forecast",
    }
    try:
        html, _ = fetch(HILLSTROM)
        parser = CsvLinks()
        parser.feed(html.decode("utf-8", errors="replace"))
        if not parser.links:
            raise ValueError("Author CSV link not found")
        url = parser.links[0]
        if urlparse(url).hostname not in {"www.minethatdata.com", "minethatdata.com"}:
            raise ValueError("Unexpected CSV host")
        manifest["author_link_url"] = url
        # Use the exact public link published by the author; no credentials are sent.
        # HTTPS on that host failed certificate validation; validation is never disabled.
        data, final_url = fetch(url)
        if len(data) > 10_000_000:
            raise ValueError("Unexpected download size")
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        expected = {
            "recency",
            "history_segment",
            "history",
            "mens",
            "womens",
            "zip_code",
            "newbie",
            "channel",
            "segment",
            "visit",
            "conversion",
            "spend",
        }
        if len(rows) != 64000 or set(rows[0]) != expected:
            raise ValueError("Unexpected row count or columns")
        for row in rows:
            assert row["segment"] in {"Mens E-Mail", "Womens E-Mail", "No E-Mail"}
            assert int(row["conversion"]) in (0, 1) and int(row["visit"]) in (0, 1)
            assert float(row["spend"]) >= 0
        raw = OUT / "raw"
        raw.mkdir(exist_ok=True)
        (raw / "hillstrom.csv").write_bytes(data)
        groups = defaultdict(list)
        for row in rows:
            groups[row["segment"]].append(row)
        totals = []
        for group, records in sorted(groups.items()):
            buyers = sum(int(r["conversion"]) for r in records)
            spend = sum(float(r["spend"]) for r in records)
            totals.append(
                {
                    "arm": group,
                    "customers": len(records),
                    "buyers": buyers,
                    "buyer_rate": buyers / len(records),
                    "spend_total_source_dollars": round(spend, 2),
                    "mean_spend_per_customer_source_dollars": spend / len(records),
                    "units_sold": None,
                    "currency_note": "원저자 표기 dollars;KRW 환산하지 않음",
                }
            )
        save_json(
            "hillstrom_group_summary.json",
            {
                "record_kind": "observed_external_experiment_aggregate",
                "domain": "non_cosmetics_retail",
                "measurement_period": "이메일 발송 후2주",
                "groups": totals,
                "use": "방법 검증용;화장품 문구 성과 예측으로 사용 금지",
            },
        )
        manifest.update(
            {
                "status": "downloaded_and_validated",
                "download_url": final_url,
                "rows": len(rows),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "columns": sorted(expected),
                "local_file": "raw/hillstrom.csv",
                "git_ignored": True,
                "transport": "원저자 공개 HTTP 링크;키·개인정보 전송 없음;인증서 검증 비활성화 없음",
            }
        )
    except (OSError, ValueError, KeyError, AssertionError) as error:
        manifest.update(
            {
                "status": "download_failed",
                "error_type": type(error).__name__,
                "note": "원저자가 아닌 미러로 대체하지 않음;원시 데이터 확보 완료로 표시하지 않음",
            }
        )
    save_json("hillstrom_download_manifest.json", manifest)
    print(
        json.dumps(
            {
                "benchmark_status": manifest["status"],
                "rows": manifest.get("rows"),
                "error_type": manifest.get("error_type"),
            }
        )
    )


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--download-benchmark", action="store_true")
    options = args.parse_args()
    collect_curated()
    if options.download_benchmark:
        download_benchmark()
