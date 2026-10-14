"""
[app/services/product_market.py]
선택한 제품(사이드바 「내 제품」)을 실제 시장 수집 자료와 연결한다 — 예상 매출 시나리오의 기본값 출처.

연결 순서: 제품 카드의 ingredient_profile_id (예: PUBLIC_KIEHLS_UFC → MKT_KIEHLS_UFC)
  · 가격      data/market_reference/offers.json          (공식몰·올리브영 페이지 표시가)
  · 실제 문구  data/sales_forecast_reference/copy_comparison/market_copy_judgements.jsonl (규칙 판정 포함)
  · 판매 실적  data/sales_forecast_reference/product_sales_observations.jsonl (제품군 참고만, 수량 추정 금지)

매출·판매량은 공개 자료에 없다(SALES_AVAILABILITY.md) → 화면에서는 가정 입력으로 남기고 '공개 자료 없음'을 표시한다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFERS = ROOT / "data" / "market_reference" / "offers.json"
PRODUCTS = ROOT / "data" / "market_reference" / "products.json"
JUDGEMENTS = ROOT / "data" / "sales_forecast_reference" / "copy_comparison" / "market_copy_judgements.jsonl"
SALES_OBS = ROOT / "data" / "sales_forecast_reference" / "product_sales_observations.jsonl"

CHANNEL_LABEL = {"brand_store": "공식몰", "oliveyoung": "올리브영"}


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def _tables() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    return _json(OFFERS), _json(PRODUCTS), _jsonl(JUDGEMENTS), _jsonl(SALES_OBS)


def market_id_for(product: dict | None) -> str | None:
    """앱 제품 카드 → 시장 수집 자료의 product_id. 연결이 없으면 None."""
    if not product:
        return None
    for key in ("ingredient_profile_id", "market_product_id", "product_id"):
        value = product.get(key)
        if value and str(value).startswith("MKT_"):
            return value
    return None


def market_profile(product: dict | None) -> dict | None:
    """선택 제품의 실제 가격·실제 문구·판매 자료 여부. 연결된 시장 자료가 없으면 None."""
    mid = market_id_for(product)
    if mid is None:
        return None
    offers, products, judgements, sales = _tables()
    info = next((p for p in products if p["product_id"] == mid), {})
    offer_rows = []
    for o in offers:
        if o["product_id"] != mid or not o.get("displayed_price_krw"):
            continue
        offer_rows.append({
            "offer_id": o["offer_id"],
            "price_krw": int(o["displayed_price_krw"]),
            "listed_price_krw": o.get("listed_price_krw"),
            "channel": CHANNEL_LABEL.get(o.get("channel"), o.get("channel") or "판매처 미상"),
            "bundle_note": o.get("bundle_note") or "",
            "qualifier": o.get("price_qualifier") or "",
            "label": f'{CHANNEL_LABEL.get(o.get("channel"), o.get("channel"))} · {o.get("bundle_note") or ""} · '
                     f'{int(o["displayed_price_krw"]):,}원',
        })
    copies = [
        {
            "copy_id": j["copy_id"],
            "copy_text": j["copy_text"],
            "level": j.get("judge_level"),
            "label": j.get("display_label"),
            "placement": j.get("위치"),
        }
        for j in judgements
        if j.get("product_id") == mid and j.get("copy_text")
    ]
    observations = [s for s in sales if s.get("linked_sample_product_id") in (mid, (product or {}).get("product_id"))]
    return {
        "market_product_id": mid,
        "brand": info.get("brand"),
        "name": info.get("name"),
        "offers": offer_rows,
        "copies": copies,
        "sales_observations": observations,
        # 수집 범위에서 이 제품의 매출·판매량은 확인되지 않았다 (SALES_AVAILABILITY.md)
        "units_public": any(s.get("units_sold") is not None for s in observations),
        "revenue_public": any(s.get("net_revenue") is not None for s in observations),
    }


def latest_review_pair(threads: list[dict] | None, product_id: str) -> dict | None:
    """검토 대화에서 이 제품으로 가장 최근에 검토한 (원문, 엔진 제안 문구, 판정 등급)."""
    best = None
    for thread in threads or []:
        msgs = thread.get("messages", [])
        for i, m in enumerate(msgs):
            if m.get("role") != "assistant" or "resp" not in m:
                continue
            user = next((u for u in reversed(msgs[:i]) if u.get("role") == "user"), None)
            if not user or (user.get("ctx") or {}).get("product_id") != product_id:
                continue
            result = m["resp"].get("result", {})
            pair = {"original": user.get("text", ""), "suggestion": result.get("suggestion"),
                    "level": result.get("level"), "at": m.get("at") or ""}
            if best is None or str(pair["at"]) >= str(best["at"]):
                best = pair
    return best
