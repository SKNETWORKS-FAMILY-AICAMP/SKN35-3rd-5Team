from app.services.candidate_compare import classify_appeal, compare_candidates, judge_copy
from cosmetic_agent.market_reference import appeal_summary, find_peers

AMPOULE = {
    "product_id": "CUSTOM_001", "name": "비타민A 브라이트닝 앰플", "category": "기능성",
    "functional_type": "피부 미백, 주름 개선", "key_ingredients": ["레티놀", "나이아신아마이드", "아데노신"],
    "form": "세럼·앰플", "price_krw": 32000,
    "owned_evidence": [{"test_type": "인체적용시험", "item": "눈가 주름 개선",
                        "value": "8주 사용 후 눈가 주름 15% 개선", "institute": "예시 피부임상연구소"}],
}


def test_classify_appeal_types():
    assert "효능 수치형" in classify_appeal("8주 사용 후 눈가 주름 15% 개선", AMPOULE)
    assert "성분 소구형" in classify_appeal("레티놀을 담은 앰플", AMPOULE)
    assert "사용감형" in classify_appeal("끈적임 없이 스며드는 앰플", AMPOULE)
    assert "비교·순위형" in classify_appeal("판매 1위 앰플", AMPOULE)


def test_empty_copy_is_not_judged():
    assert judge_copy("", AMPOULE)["level"] is None


def test_recommends_strongest_rule_safe_candidate_and_never_risky_one():
    rows_market = appeal_summary(find_peers(AMPOULE))
    candidates = [
        {"text": "주름이 사라지는 기적의 앰플", "tier": "strong"},
        {"text": "밤사이 피부 결을 정돈\\n레티놀과 아데노신을 담은 2중 기능성 앰플", "tier": "balanced",
         "creative_reference_ids": ["C4"]},
        {"text": "피부에 부드럽게 스며드는 앰플", "tier": "safe"},
    ]
    rows = compare_candidates(AMPOULE, candidates, rows_market)
    best = next(r for r in rows if r["recommended"])
    assert rows[0]["level"] >= 1 and not rows[0]["recommended"]
    assert best["index"] == 1 and best["level"] == 0
    assert best["creative"] == ["성분 이야기"] and best["peer_total"] >= 3
    assert "규칙상 쓸 수 있는 후보" in best["why"]
