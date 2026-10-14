"""Validate public market references and export a separate, non-regulatory RAG corpus.

Run: uv run python scripts/build_market_reference.py
Does not call OpenAI, crawl websites, alter the regulatory corpus, or write Qdrant.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "data" / "market_reference"


def read_json(name: str, root: Path = ROOT) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


def build_context(root: Path = ROOT) -> list[dict[str, Any]]:
    expansion = read_json("platform_expansion.json", root)

    def rows(name: str) -> list[dict[str, Any]]:
        return read_json(f"{name}.json", root) + expansion.get(name, [])

    sources = rows("sources")
    products = rows("products")
    offers = rows("offers")
    assets = rows("creative_assets")
    business = read_json("business_context.json", root)
    signals = rows("public_outcomes")
    companies = read_json("companies.json", root)
    relations = read_json("company_relations.json", root)
    platforms = read_json("platforms.json", root)
    copies = [json.loads(line) for line in (root / "copy_observations.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    copies += expansion.get("copy_observations", [])
    for copy in copies:
        copy.setdefault("legal_status", "not_assessed")
        copy.setdefault("performance_status", "not_disclosed_in_collected_sources")
        copy.setdefault("publicly_stated_audience", None)
        copy.setdefault("audience_status", "unknown")

    def index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        result = {row[key]: row for row in rows}
        if len(result) != len(rows):
            raise ValueError(f"Duplicate {key}")
        return result

    source_by_id = index(sources, "source_id")
    product_by_id = index(products, "product_id")
    offer_by_id = index(offers, "offer_id")
    index(assets, "asset_id")
    index(copies, "observation_id")
    index(business, "context_id")
    index(signals, "signal_id")
    company_by_id = index(companies, "company_id")
    platform_by_id = index(platforms, "platform_id")
    index(relations, "relation_id")
    for row in products + offers + assets + business + copies + signals:
        if row["source_id"] not in source_by_id:
            raise ValueError("Unknown source_id")
    for company in companies:
        if any(source_id not in source_by_id for source_id in company["source_ids"]):
            raise ValueError("Unknown company source")
    for platform in platforms:
        if any(source_id not in source_by_id for source_id in platform["source_ids"]):
            raise ValueError("Unknown platform source")
    for relation in relations:
        if relation["company_id"] not in company_by_id or relation["source_id"] not in source_by_id:
            raise ValueError("Unknown relation endpoint/source")
        if relation.get("platform_id") and relation["platform_id"] not in platform_by_id:
            raise ValueError("Unknown relation platform")
        if relation.get("product_id") and company_by_id[relation["company_id"]]["role"] == "odm_oem_development_manufacturing":
            raise ValueError("SKU manufacturer needs separate product-label evidence, not company profile")
    for offer in offers:
        if offer["product_id"] not in product_by_id:
            raise ValueError("Unknown product_id")
    for asset in assets:
        if asset["offer_id"] not in offer_by_id:
            raise ValueError("Unknown image offer_id")
    for context in business:
        if context["usable_for_copy_performance"] or context.get("observation_id") or context.get("product_id"):
            raise ValueError("Company revenue cannot be used as product/copy performance")
    for signal in signals:
        if signal["copy_effect_established"]:
            raise ValueError("Public market outcomes are not copy effects")
        if signal["scope"].startswith("brand_") and signal.get("product_id"):
            raise ValueError("Brand sales cannot be assigned to a product")
        if signal.get("product_id") and signal["product_id"] not in product_by_id:
            raise ValueError("Unknown signal product_id")

    output = []
    for copy in copies:
        product = product_by_id.get(copy["product_id"])
        offer = offer_by_id.get(copy["offer_id"])
        if copy["product_id"] and product is None:
            raise ValueError("Unknown copy product_id")
        if copy["offer_id"] and offer is None:
            raise ValueError("Unknown copy offer_id")
        if offer and offer["product_id"] != copy["product_id"]:
            raise ValueError("Copy/offer product mismatch")
        if copy["legal_status"] != "not_assessed":
            raise ValueError("Public copy is not a legal approval label")
        source = source_by_id[copy["source_id"]]
        brand = product["brand"] if product else copy.get("brand") or source.get("brand")
        linked_signals = [
            {**signal, "source_url": source_by_id[signal["source_id"]]["url"],
             "relationship": "product_family_context_not_offer_performance" if signal.get("product_id")
             else "brand_context_not_product_performance"}
            for signal in signals if signal["brand"] == brand
            and (not signal.get("product_id") or signal["product_id"] == copy["product_id"])
        ]
        output.append({
            "id": f"MARKET_{copy['observation_id']}",
            "corpus_type": "market_reference",
            "authority": None,
            "allowed_as_regulatory_evidence": False,
            "allowed_as_product_efficacy_evidence": False,
            "allowed_as_copy_performance_label": False,
            "source_url": source["url"],
            "accessed_on": source["accessed_on"],
            "source_freshness": source["freshness"],
            "brand": brand,
            "platform": platform_by_id.get(offer["channel"]) if offer else None,
            "company_context": [
                {"company": company_by_id[relation["company_id"]], "relation": relation}
                for relation in relations if brand and relation.get("brand") == brand
            ],
            "product": product,
            "offer": offer,
            "observation_id": copy["observation_id"],
            "observation_file": "copy_observations.jsonl",
            "scope": copy["scope"],
            "appeal_tags": copy["appeal_tags"],
            "public_market_signals": linked_signals,
            "assets": [asset for asset in assets if offer and asset["offer_id"] == offer["offer_id"]],
            "performance": {
                "status": "not_disclosed_in_collected_sources",
                "impressions": None, "clicks": None, "purchases": None,
                "net_revenue_krw": None, "ad_spend_krw": None,
                "ctr": None, "purchase_cvr": None, "roas": None,
                "paid_targeting": None, "experiment_id": None,
            },
            "content": (
                f"외부 문구 관찰 ID: {copy['observation_id']} (원문은 copy_observations.jsonl에서 조회)\n"
                f"제품: {product['name'] if product else '브랜드/라인 캠페인'}\n"
                f"분석자 소구 태그: {', '.join(copy['appeal_tags'])}\n"
                f"조건/한계: {copy['qualification']}\n"
                "문구별 매출·전환·유료광고 타깃 미확인. 효능 입증·적법성·판매 인과 효과의 근거가 아님."
            ),
        })
    return output


def main() -> None:
    records = build_context()
    destination = ROOT / "market_context.jsonl"
    destination.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    lines = ["# 공개 화장품 문구 관찰표", "", "출처 열람일: 2026-10-13. 실제 광고 성과 순위표가 아닙니다.", "",
             "| ID | 브랜드/범위 | 관찰 문구 | 소구 태그(분석자) | 가격 표기 | 출처 |",
             "|---|---|---|---|---|---|"]
    raw_copies = {json.loads(line)["observation_id"]: json.loads(line)
                  for line in (ROOT / "copy_observations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    raw_copies.update({copy["observation_id"]: copy for copy in read_json("platform_expansion.json")["copy_observations"]})
    for row in records:
        observation, offer = raw_copies[row["observation_id"]], row["offer"]
        price = f"{offer['displayed_price_krw']:,}원" if offer and offer["displayed_price_krw"] is not None else "미확인"
        brand = row["brand"] or "브랜드/라인"
        lines.append(f"| {observation['observation_id']} | {brand} | {observation['copy_text']} | "
                     f"{', '.join(observation['appeal_tags'])} | {price} | [원문]({row['source_url']}) |")
    lines += ["", "가격은 옵션·구성·할인 조건이 다른 페이지 관찰값입니다. 직접 가격/매출 우열 비교에 사용하지 않습니다."]
    (ROOT / "OBSERVATIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    company_documents = [{
        "id": f"COMPANY_{company['company_id']}", "corpus_type": "company_industry_context",
        "allowed_as_regulatory_evidence": False, "allowed_as_product_efficacy_evidence": False,
        "allowed_as_copy_performance_label": False, "company": company,
        "content": f"{company['name']}: {company['summary']}\n주의: {company['caution']}",
    } for company in read_json("companies.json")]
    (ROOT / "company_context.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in company_documents), encoding="utf-8")
    expansion = read_json("platform_expansion.json")
    summary = {
        "collected_on": expansion["collected_on"],
        "platforms": len(read_json("platforms.json")),
        "companies": len(company_documents),
        "company_relations": len(read_json("company_relations.json")),
        **{name: len(read_json(f"{name}.json")) + len(expansion.get(name, []))
           for name in ("sources", "products", "offers", "creative_assets", "public_outcomes")},
        "copy_observations": len(records),
        "observed_internal_campaign_performance_rows": len(read_json("internal_performance.json")["records"]),
        "historical_offers": sum(row.get("record_type", "").startswith("historical_") for row in expansion["offers"]),
        "images_visually_reviewed": 0,
        "integrated_with_app_or_qdrant": False,
    }
    (ROOT / "coverage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Validated and exported {len(records)} market references; no performance labels fabricated.")


if __name__ == "__main__":
    main()
