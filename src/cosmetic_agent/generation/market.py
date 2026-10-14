"""Market observations are copy inspiration, never regulatory or owned evidence."""
import json

from ..market_reference import find_peers


def market_references(product: dict, limit: int = 6) -> list[dict]:
    rows = []
    for peer in find_peers(product):
        # 기능성만 겹친 사례보다 실제 공통 성분이 확인된 사례를 사용한다.
        if not peer["shared_ingredients"]:
            continue
        for copy in peer["copies"][:2]:
            rows.append({
                "reference_id": f"M{len(rows) + 1}", "product_id": peer["product_id"],
                "brand": peer["brand"], "product_name": peer["name"],
                "form": peer["form"], "shared_ingredients": peer["shared_ingredients"],
                "ingredient_basis": peer.get("ingredient_basis") or "공개 주요 성분 키워드",
                "copy_id": copy["copy_id"], "copy_text": copy["copy_text"],
                "copy_types": copy["types"], "placement": copy.get("placement"),
                "conditions": copy.get("conditions"),
                "source_url": copy.get("source_url") or peer.get("url"),
                "observed_on": copy.get("observed_on") or peer.get("observed_on"),
                "market": peer.get("market", "KR"),
                "allowed_as_owned_evidence": False,
            })
            if len(rows) == limit:
                return rows
    return rows


def market_prompt(rows: list[dict]) -> str:
    return json.dumps(rows, ensure_ascii=False) if rows else "비교 조건에 맞는 시장 문구 없음. 우리 제품 정보만 사용."
