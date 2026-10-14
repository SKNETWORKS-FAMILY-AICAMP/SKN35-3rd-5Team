import json
from pathlib import Path

from app.services.product_market import latest_review_pair, market_id_for, market_profile

ROOT = Path(__file__).resolve().parents[2]


def kiehls():
    return json.loads((ROOT / "data/assets/public_analysis_products.json").read_text(encoding="utf-8"))[0]


def test_kiehls_links_to_public_price_and_real_copies():
    profile = market_profile(kiehls())
    assert profile["market_product_id"] == "MKT_KIEHLS_UFC"
    assert profile["offers"][0]["price_krw"] == 95000
    texts = {c["copy_text"] for c in profile["copies"]}
    assert "72시간 보습 효과" in texts and "15년 연속 No.1" in texts
    # 공개 매출·판매량은 없다 → 화면은 가정 입력으로 남긴다
    assert profile["units_public"] is False and profile["revenue_public"] is False


def test_unlinked_product_has_no_market_profile():
    assert market_id_for({"product_id": "PROD_001"}) is None
    assert market_profile({"product_id": "PROD_001"}) is None


def test_latest_review_pair_picks_same_product_only():
    threads = [{"messages": [
        {"role": "user", "text": "A 문구", "at": "1", "ctx": {"product_id": "X"}},
        {"role": "assistant", "at": "2", "resp": {"result": {"suggestion": "A 제안", "level": 1}}},
        {"role": "user", "text": "B 문구", "at": "3", "ctx": {"product_id": "Y"}},
        {"role": "assistant", "at": "4", "resp": {"result": {"suggestion": "B 제안", "level": 2}}},
    ]}]
    assert latest_review_pair(threads, "X")["suggestion"] == "A 제안"
    assert latest_review_pair(threads, "Y")["original"] == "B 문구"
    assert latest_review_pair(threads, "Z") is None
