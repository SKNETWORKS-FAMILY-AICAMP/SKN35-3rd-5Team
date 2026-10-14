"""Explicit links from project fixtures to external market references.

External product evidence and sales never become the internal product's labels.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
COMPARISON = DATA / "sales_forecast_reference" / "copy_comparison"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_reference_catalog():
    """Reuse already-collected market snapshots, including creams and toner."""
    cards = read_json(COMPARISON / "cosmetics_evidence_cards.json")
    catalog = {c["product_id"]: c for c in cards}
    market = DATA / "market_reference"
    expansion = read_json(market / "platform_expansion.json")
    products = read_json(market / "products.json") + expansion["products"]
    sources = {
        s["source_id"]: s
        for s in read_json(market / "sources.json") + expansion["sources"]
    }
    offers = read_json(market / "offers.json") + expansion["offers"]
    copies = [
        json.loads(line)
        for line in (market / "copy_observations.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    copies += expansion["copy_observations"]
    for product in products:
        pid = product["product_id"]
        source = sources[product["source_id"]]
        own_offers = [o for o in offers if o["product_id"] == pid]
        own_copies = [c for c in copies if c.get("product_id") == pid]
        # One existing offer snapshot per reference; retain its source and qualifier.
        offer = own_offers[0] if own_offers else {}
        offer_source = sources.get(offer.get("source_id"), source)
        catalog[pid] = {
            "product_id": pid,
            "brand": product["brand"],
            "product_name": product["name"],
            "market_observed_date": offer_source.get("accessed_on"),
            "market_source_url": offer_source["url"],
            "market_conditions": {
                "ranking": None,
                "ranking_type": "해당 수집에서 순위 미확인",
                "ranking_period": None,
                "sale_price_krw": offer.get("displayed_price_krw"),
                "discount_percent_displayed": offer.get("displayed_discount_pct"),
                "bundle": offer.get("bundle_note"),
                "sale_event": offer.get("price_qualifier"),
                "review_count": None,
            },
            "observed_copies": [
                {
                    "copy_id": c["observation_id"],
                    "copy_text": c["copy_text"],
                    "위치": c["placement"],
                    "문구 유형": c.get("appeal_tags", []),
                    "시험 조건 표기 여부": c.get("qualification") or "미확인",
                    "source_url": sources[c["source_id"]]["url"],
                }
                for c in own_copies
            ],
        }
    return catalog


def references_for(product_id, catalog, links):
    """Unknown/unmapped products do not silently fall back to unrelated serums."""
    from cosmetic_agent.domain.ingredients import matched_references

    target, accepted, excluded = matched_references(product_id)
    profile = dict(links.get("links", {}).get(product_id, {}))
    profile.update(ingredient_profile=target, excluded_ingredient_references=excluded)
    if not target:
        profile["collection_gap"] = (
            "전성분 미등록으로 성분 기반 참고 연결 보류. 사이드바에서 ‘키엘 울트라 훼이셜 크림 · 성분 공개 샘플’을 선택해 확인하세요."
        )
        return profile, []
    profile["purpose"] = "공식 전성분이 공개된 실제 제품의 성분 기반 문구 분석"
    profile["match_basis"] = (
        "동일 제형 + 전성분 확인 + 공통 주요 소구 성분이 있는 제품만 참고"
    )
    profile["collection_gap"] = None
    result = []
    for match in accepted:
        ref = match["profile"]
        card = {
            "product_id": match["reference_id"],
            "brand": "Biossance" if ref["market"] == "US" else "KIEHLS",
            "product_name": ref["name"],
            "market_observed_date": "2026-10-14",
            "market_source_url": ref["source_url"],
            "ingredient_comparison": match["comparison"],
            "ingredient_profile": ref,
            "market_conditions": {
                "sale_price_krw": None,
                "discount_percent_displayed": None,
                "bundle": "공식 성분 페이지 기준",
                "sale_event": "가격·행사 비교 대상 아님",
                "ranking": None,
            },
            "observed_copies": [
                {
                    "copy_id": f"{match['reference_id']}_ING_{i}",
                    "copy_text": c["text"],
                    "위치": "공식 상품명/제품 설명",
                    "문구 유형": ["성분 소구형"],
                    "시험 조건 표기 여부": c["analysis"],
                    "source_url": ref["source_url"],
                }
                for i, c in enumerate(ref["reference_copies"])
            ],
        }
        result.append(card)
    return profile, result
