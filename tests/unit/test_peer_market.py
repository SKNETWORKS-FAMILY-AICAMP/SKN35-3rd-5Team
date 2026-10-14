from app.services.peer_market import (appeal_summary, candidate_copies, find_peers, ingredient_groups,
                                      judge_candidates, price_benchmark)

VITAMIN_A_AMPOULE = {
    "product_id": "CUSTOM_001", "name": "비타민A 브라이트닝 앰플", "category": "기능성",
    "functional_type": "피부 미백, 주름 개선", "key_ingredients": ["레티놀", "나이아신아마이드", "아데노신"],
    "form": "세럼·앰플", "price_krw": 32000,
    "owned_evidence": [{"test_type": "인체적용시험", "item": "눈가 주름 개선",
                        "value": "8주 사용 후 눈가 주름 15% 개선", "institute": "예시 피부임상연구소"}],
}


def test_vitamin_a_synonyms_group_together():
    for word in ["레티놀", "레틴알(0.1%)", "비타티놀", "더 비타 A 레티날"]:
        assert "비타민A(레티노이드)" in ingredient_groups(word)


def test_vitamin_a_ampoule_finds_retinoid_serums_first_and_no_duplicates():
    peers = find_peers(VITAMIN_A_AMPOULE)
    brands = [p["brand"] for p in peers]
    assert len(brands) == len(set(brands))           # 공식몰·올리브영 같은 제품은 하나로
    retinoid = [p for p in peers if "비타민A(레티노이드)" in p["shared_ingredients"]]
    assert {p["brand"] for p in retinoid} >= {"프리메라", "셀리맥스", "온그리디언츠", "아이오페"}
    assert peers.index(retinoid[0]) == 0
    bench = price_benchmark(peers)
    assert bench["min"] <= bench["median"] <= bench["max"]


def test_unrelated_product_gets_no_peers():
    assert find_peers({"name": "데일리 프레시 샴푸", "key_ingredients": []}) == []


def test_hydrating_toner_does_not_borrow_serums_with_shared_ingredients():
    toner = {"name": "수분 진정 수딩 토너", "form": "토너",
             "key_ingredients": ["히알루론산", "판테놀"]}
    peers = find_peers(toner)
    assert len(peers) == 1
    assert peers[0]["product_id"] == "MKT_ANUA_HEARTLEAF_HA_TONER_250_RENEWAL"
    assert peers[0]["form"] == "토너"
    assert set(peers[0]["shared_ingredients"]) == {"히알루론산", "판테놀"}
    assert all(c["level"] is None for c in peers[0]["copies"])


def test_existing_pdrn_toner_is_connected_without_cross_form_matches():
    toner = {"name": "PDRN 수딩 토너", "form": "토너", "key_ingredients": ["PDRN"]}
    peers = find_peers(toner)
    assert len(peers) == 1
    assert peers[0]["product_id"] == "MKT_ROUNDLAB_PDRN_TONER"
    assert peers[0]["shared_ingredients"] == ["PDRN"]


def test_appeal_summary_counts_types_and_judgements():
    rows = {r["type"]: r for r in appeal_summary(find_peers(VITAMIN_A_AMPOULE))}
    numeric = rows["효능 수치형"]
    assert numeric["products"] >= 3 and numeric["caution"] >= 1


def test_recommendation_uses_own_evidence_and_is_rule_safe():
    peers = find_peers(VITAMIN_A_AMPOULE)
    judged = judge_candidates(VITAMIN_A_AMPOULE, candidate_copies(VITAMIN_A_AMPOULE), peers)
    best = next(j for j in judged if j["recommended"])
    assert best["level"] == 0 and best["type"] == "효능 수치형" and "15%" in best["copy"]
    no_evidence = dict(VITAMIN_A_AMPOULE, owned_evidence=[])
    judged = judge_candidates(no_evidence, candidate_copies(no_evidence), peers)
    assert all(j["type"] != "효능 수치형" for j in judged)
    assert next(j for j in judged if j["recommended"])["type"] == "효능 서술형"
