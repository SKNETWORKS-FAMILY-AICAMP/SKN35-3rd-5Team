"""
[cosmetic_agent/market_reference.py]
새로 등록한 우리 제품 → 비슷한 시장 제품(경쟁 제품) 찾기 → 그 제품들의 광고 문구 분석 → 우리 제품에 쓸 최적 문구 후보.

시장 제품(이미 수집한 공개 자료만 사용):
  · data/top_product_copies/wrinkle_serum_sample/products.csv   올리브영 스킨케어 랭킹 세럼·앰플 (순위·리뷰·가격·성분)
  · data/market_reference/products.json + platform_expansion.json (공식몰·플랫폼 제품, 가격 offers)
  · data/sales_forecast_reference/copy_comparison/market_copy_judgements.jsonl (실제 문구 + 규칙 판정)
  · data/market_reference/public_outcomes.json, platform_expansion.json public_outcomes (공개 판매 신호)

정직하게 지키는 선:
  · 경쟁 제품의 매출은 거의 공개되지 않는다. 판매 랭킹 순위·리뷰 수는 '인기 신호'이지 매출이 아니다.
  · 경쟁 제품의 시험 수치·효능은 우리 제품 근거로 옮기지 않는다. 문구의 '유형(소구 방식)'만 참고한다.
  · 후보 문구는 우리 제품 정보(성분·기능성·보유 실증)로만 만들고, 규칙 엔진으로 다시 판정한다.
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OY_PRODUCTS = DATA / "top_product_copies" / "wrinkle_serum_sample" / "products.csv"
MARKET = DATA / "market_reference"
JUDGEMENTS = DATA / "sales_forecast_reference" / "copy_comparison" / "market_copy_judgements.jsonl"
SALES_OBS = DATA / "sales_forecast_reference" / "product_sales_observations.jsonl"

# ── 성분 동의어: 표기가 달라도 같은 성분군으로 본다 ─────────────────────────────
INGREDIENT_GROUPS: dict[str, list[str]] = {
    "비타민A(레티노이드)": ["비타민a", "비타민 a", "비타 a", "레티놀", "레티날", "레틴알", "레티닐", "레티노이드",
                       "레티노에이트", "비타티놀", "retinol", "retinal"],
    "PDRN": ["pdrn", "피디알엔", "소듐디엔에이", "디엔에이", "c-pdrn"],
    "나이아신아마이드": ["나이아신아마이드", "비타민b3", "niacinamide"],
    "비타민C": ["비타민c", "비타민 c", "아스코빅", "아스코빌", "vitamin c"],
    "히알루론산": ["히알루론", "하이알루로", "hyaluron"],
    "아데노신": ["아데노신", "adenosine"],
    "펩타이드": ["펩타이드", "peptide"],
    "콜라겐": ["콜라겐", "collagen"],
    "바쿠치올": ["바쿠치올", "바쿠", "bakuchiol"],
    "스쿠알란": ["스쿠알란", "squalane"],
    "세라마이드": ["세라마이드", "ceramide"],
    "시카(병풀)": ["시카", "병풀", "마데카", "센텔라", "cica"],
    "판테놀": ["판테놀", "panthenol"],
    "어성초(약모밀)": ["어성초", "약모밀", "houttuynia"],
}

# 제형: 세럼·앰플·에센스·부스터는 같은 묶음으로 본다
FORM_GROUPS: dict[str, list[str]] = {
    "세럼·앰플": ["세럼", "앰플", "에센스", "부스터", "샷", "serum", "ampoule"],
    "크림": ["크림", "cream"],
    "토너": ["토너", "스킨", "toner"],
    "로션": ["로션", "에멀전", "lotion"],
    "마스크": ["마스크", "mask"],
    "클렌저": ["클렌저", "클렌징", "폼", "cleanser"],
    "미스트": ["미스트", "스프레이", "mist"],
}
FORMS = list(FORM_GROUPS)
CATEGORY_FORM = {"serum": "세럼·앰플", "cream": "크림", "toner": "토너", "lotion": "로션", "sheet_mask": "마스크",
                 "cleanser": "클렌저", "mist_serum": "미스트"}

FUNCTION_WORDS = {"미백": ["미백", "브라이트닝", "톤업", "화이트닝"], "주름 개선": ["주름"],
                  "자외선 차단": ["자외선"], "탈모 증상 완화": ["탈모"], "여드름성 피부 완화": ["여드름"],
                  "피부장벽 기능 회복": ["장벽", "가려움"]}

# 문구 유형 — 화면에 보여줄 순서와 쉬운 설명
APPEAL_TYPES = {
    "효능 수치형": "‘8주 후 주름 15% 개선’처럼 시험 수치로 효과를 말함",
    "효능 서술형": "‘주름 개선에 도움’처럼 효과를 말로 설명",
    "성분 소구형": "‘레티놀 함유’처럼 성분을 앞세움",
    "사용감형": "‘산뜻하게 스며드는’처럼 바르는 느낌을 말함",
    "구성·혜택형": "‘리필 증정’처럼 구성·가격 혜택을 말함",
    "비교·순위형": "‘판매 1위’처럼 다른 제품과 비교하거나 순위를 말함",
    "시험·검사 표방형": "‘피부과 테스트 완료’처럼 검사를 거쳤다고 말함",
}


BRAND_KO = {"ANUA": "아누아", "KIEHLS": "키엘", "AESTURA": "에스트라", "DALBA": "달바", "ROUNDLAB": "라운드랩",
            "MEDICUBE": "메디큐브", "REJURAN_COSMETICS": "리쥬란", "MEDIHEAL": "메디힐", "TORRIDEN": "토리든"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def ingredient_groups(text: str) -> set[str]:
    tokens = [s.strip() for s in re.split(r"[,;]", text or "") if s.strip()]
    aliases = ingredient_aliases()
    canonical = [aliases.get(re.sub(r"\s+", "", s).casefold(), s) for s in tokens]
    t = _norm(" ".join([text or "", *canonical]))
    groups = {g for g, words in INGREDIENT_GROUPS.items() if any(w in t for w in words)}
    for name in canonical:
        if (name in aliases.values()
            and name not in {"정제수", "글리세린", "부틸렌글라이콜", "1,2-헥산다이올"}
            and not any(w in _norm(name) for words in INGREDIENT_GROUPS.values() for w in words)):
            groups.add(name)
    return groups


@lru_cache(maxsize=1)
def ingredient_aliases() -> dict[str, str]:
    """원료 사전의 모호하지 않은 표준명·영문명·동의어만 정확 일치로 대응한다."""
    path = DATA / "01_raw/api/cosmetic_ingredients.json"
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    candidates: dict[str, set[str]] = {}
    for row in raw.get("items", []):
        name = row.get("kor_name")
        if not name:
            continue
        for alias in [name, row.get("eng_name"), *(row.get("synonyms") or [])]:
            if isinstance(alias, str) and alias.strip():
                candidates.setdefault(re.sub(r"\s+", "", alias).casefold(), set()).add(name)
    return {alias: next(iter(names)) for alias, names in candidates.items() if len(names) == 1}


def form_of(text: str) -> str | None:
    t = _norm(text)
    for form, words in FORM_GROUPS.items():
        if any(w in t for w in words):
            return form
    return None


def functions_of(text: str) -> set[str]:
    t = _norm(text)
    return {f for f, words in FUNCTION_WORDS.items() if any(w in t for w in words)}


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def load_market_products() -> tuple[dict, ...]:
    """수집한 시장 제품을 같은 모양으로 정리한다."""
    judgements = _jsonl(JUDGEMENTS)
    copies_by: dict[str, list[dict]] = {}
    for j in judgements:
        copies_by.setdefault(j["product_id"], []).append({
            "copy_id": j["copy_id"], "copy_text": j["copy_text"], "types": [t for t in j.get("문구 유형") or [] if t != "기타"],
            "level": j.get("judge_level"), "label": j.get("display_label"), "placement": j.get("위치"),
        })
    expansion = _json(MARKET / "platform_expansion.json", {})
    sources = {s["source_id"]: s for s in _json(MARKET / "sources.json", []) + expansion.get("sources", [])}
    observations = _jsonl(MARKET / "copy_observations.jsonl") + expansion.get("copy_observations", [])
    observations += _jsonl(OY_PRODUCTS.parent / "copies.jsonl")
    originals = {c.get("copy_id") or c.get("observation_id"): c for c in observations}
    for copies in copies_by.values():
        for copy in copies:
            original = originals.get(copy["copy_id"], {})
            source = sources.get(original.get("source_id"), {})
            copy.update(source_url=original.get("source_url") or source.get("url"),
                        conditions=original.get("시험 조건 표기 여부") or original.get("qualification"),
                        observed_on=original.get("collected_date") or source.get("accessed_on"))
    outcomes = _json(MARKET / "public_outcomes.json", []) + expansion.get("public_outcomes", [])
    sales_obs = _jsonl(SALES_OBS)

    def signals(pid: str, brand_keys: set[str]) -> list[str]:
        out = []
        for o in outcomes:
            if o.get("product_id") == pid:
                out.append(_signal_text(o))
            elif o.get("product_id") is None and o.get("brand") in brand_keys and o.get("metric") == "annual_sales_krw":
                out.append(f"브랜드 · 올리브영 {o['period']}년 연매출 {o['value'] / 1e8:,.0f}억 원 이상")
        for s in sales_obs:
            if s.get("linked_sample_product_id") == pid:
                out.append(f"{s['platform']} {s['event']} 판매액 약 {s['value'] / 1e8:,.1f}억 {s['currency']} (제품군 참고)")
        return out

    products: list[dict] = []
    if OY_PRODUCTS.exists():
        with OY_PRODUCTS.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pid = r["product_id"]
                text = " ".join([r["product_name"], r["key_ingredients"]])
                products.append({
                    "product_id": pid, "brand": r["brand"], "name": r["product_name"],
                    "form": form_of(r["product_name"]) or "세럼·앰플",
                    "functions": functions_of(r.get("functional_type", "")),
                    "ingredients": ingredient_groups(text),
                    "ingredient_text": r["key_ingredients"].replace(";", ", "),
                    "price_krw": _int(r["sale_price_krw"]), "list_price_krw": _int(r["list_price_krw"]),
                    "discount_pct": _int(r["discount_percent_displayed"]),
                    "ranking": _int(r["ranking"]), "ranking_label": "올리브영 스킨케어 오늘의 랭킹",
                    "review_count": _int(r["review_count"]), "rating": _float(r["rating"]),
                    "volume": r["volume"], "channel": "올리브영", "url": r["product_url"],
                    "observed_on": r.get("collected_date"),
                    "copies": copies_by.get(pid, []),
                    "signals": signals(pid, {r["brand"]}),
                })
    offers = _json(MARKET / "offers.json", []) + expansion.get("offers", [])
    for p in _json(MARKET / "products.json", []) + expansion.get("products", []):
        pid = p["product_id"]
        offer = next((o for o in offers if o["product_id"] == pid and o.get("displayed_price_krw")), {})
        copies = copies_by.get(pid, [])
        # 광고에 등장한 성분명을 실제 배합 성분으로 간주하지 않는다.
        all_text = " ".join(p.get("ingredient_tags", []))
        products.append({
            "product_id": pid, "brand": BRAND_KO.get(p["brand"], p["brand"]), "name": p["name"],
            "form": CATEGORY_FORM.get(p.get("category")) or form_of(p["name"]),
            "functions": functions_of(" ".join(c["copy_text"] for c in copies)),
            "ingredients": ingredient_groups(all_text),
            "ingredient_text": ", ".join(p.get("ingredient_tags", [])) or "상품명 기준 미확인",
            "price_krw": _int(offer.get("displayed_price_krw")), "list_price_krw": _int(offer.get("listed_price_krw")),
            "discount_pct": _int(offer.get("displayed_discount_pct")),
            "ranking": None, "ranking_label": None, "review_count": None, "rating": None,
            "volume": offer.get("bundle_note"), "channel": {"brand_store": "공식몰", "oliveyoung": "올리브영"}.get(offer.get("channel"), offer.get("channel")), "url": sources.get(p.get("source_id"), {}).get("url"),
            "copies": copies,
            "signals": signals(pid, {p["brand"]}),
        })
    for p in _json(MARKET / "supplemental_products.json", {}).get("products", []):
        products.append({
            "product_id": p["product_id"], "brand": p["brand"], "name": p["name"],
            "form": p["form"], "functions": functions_of(p.get("functional_type") or ""),
            "ingredients": ingredient_groups(p["ingredient_text"]),
            "ingredient_text": p["ingredient_text"],
            "price_krw": p.get("price_krw"), "list_price_krw": p.get("list_price_krw"),
            "discount_pct": None, "ranking": None, "ranking_label": None,
            "review_count": None, "rating": None, "volume": p.get("volume"),
            "channel": "공식몰", "url": p["source_url"], "signals": [],
            "observed_on": p["collected_on"],
            "copies": [{"copy_id": c["copy_id"], "copy_text": c["copy_text"],
                        "types": c["types"], "level": None, "label": "미판정",
                        "placement": c["placement"], "source_url": p["source_url"],
                        "conditions": c.get("note"), "observed_on": p["collected_on"]} for c in p["copies"]],
        })
    profiles = _json(DATA / "sales_forecast_reference/copy_comparison/ingredient_profiles.json", {})
    for pid, profile in profiles.get("profiles", {}).items():
        row = next((r for r in products if r["product_id"] == pid), None)
        if row is None:
            row = {"product_id": pid, "brand": "Biossance", "name": profile["name"],
                   "form": CATEGORY_FORM.get(profile["form"]), "functions": set(),
                   "price_krw": None, "list_price_krw": None, "discount_pct": None,
                   "ranking": None, "ranking_label": None, "review_count": None,
                   "rating": None, "volume": None, "channel": "해외 공식몰", "signals": [],
                   "url": profile["source_url"], "copies": [
                       {"copy_id": f"{pid}_PROFILE_{i}", "copy_text": c["text"],
                        "types": ["성분 소구형"], "level": None, "label": "미판정",
                        "placement": "공식 제품 설명", "conditions": c["analysis"],
                        "source_url": profile["source_url"]}
                       for i, c in enumerate(profile.get("reference_copies", []))]}
            products.append(row)
        row.update(ingredient_text=profile["ingredient_text"],
                   ingredients=ingredient_groups(" ".join(profile.get("focus_ingredients", []))),
                   ingredient_basis="공식 전성분·주요 소구 성분", market=profile.get("market"),
                   observed_on=profiles.get("collected_date"))
    return tuple(products)


def _signal_text(o: dict) -> str:
    metric, value = o.get("metric"), o.get("value")
    if metric == "cumulative_units_sold":
        return f"누적 판매 {value / 1e4:,.0f}만 개 (제품군 공개 발표)"
    if metric == "event_units_sold":
        return f"행사 기간 판매 약 {value:,}개 ({o.get('period', '')})"
    if metric in ("award_rank_cream", "event_product_sales_value_rank", "sales_rank_derma_category"):
        return f"공개 순위·수상 {value}위 ({o.get('period') or o.get('signal_id')})"
    if metric == "annual_sales_krw":
        return f"연매출 {value / 1e8:,.0f}억 원 이상"
    return f"{metric}: {value}"


def product_profile(product: dict) -> dict:
    """우리 제품 카드 → 비교용 특징."""
    text = " ".join([product.get("name", ""), " ".join(product.get("key_ingredients", []) or [])])
    functional = product.get("functional_type") or ""
    return {
        "form": product.get("form") or form_of(product.get("name", "")),
        "ingredients": ingredient_groups(text),
        "functions": functions_of(functional + " " + (product.get("name") or "")) if product.get("category") == "기능성"
        else functions_of(product.get("name", "")),
    }


def find_peers(product: dict, limit: int = 8) -> list[dict]:
    """비슷한 시장 제품. 공통 성분이 없고 제형·기능도 다르면 넣지 않는다(엉뚱한 제품으로 채우지 않음)."""
    me = product_profile(product)
    profile_map = _json(DATA / "sales_forecast_reference/copy_comparison/ingredient_profiles.json", {}).get("project_profile_ids", {})
    target_id = profile_map.get(product.get("product_id"), product.get("product_id"))
    peers = []
    for p in load_market_products():
        if p["product_id"] == target_id:
            continue
        shared_ing = sorted(me["ingredients"] & p["ingredients"])
        shared_fn = sorted(me["functions"] & p["functions"])
        same_form = bool(me["form"]) and me["form"] == p["form"]
        if not same_form or not (shared_ing or shared_fn):
            continue
        score = 3 * len(shared_ing) + 2 * len(shared_fn) + (1 if same_form else 0)
        reasons = ([f"같은 성분 · {', '.join(shared_ing)}"] if shared_ing else []) + \
                  ([f"같은 기능 · {', '.join(shared_fn)}"] if shared_fn else []) + (["같은 제형"] if same_form else [])
        peers.append(dict(p, score=score, shared_ingredients=shared_ing, shared_functions=shared_fn,
                          same_form=same_form, reasons=reasons))
    peers.sort(key=lambda p: (-p["score"], p["ranking"] or 999, -(p["review_count"] or 0)))
    return _merge_same_product(peers)[:limit]


def _merge_same_product(peers: list[dict]) -> list[dict]:
    """같은 브랜드·같은 제형·같은 성분군이면 같은 제품의 다른 판매처 자료로 보고 합친다
    (예: 올리브영 랭킹 행 + 공식몰 행). 순위가 있는 행을 대표로 남긴다."""
    kept: list[dict] = []
    for p in sorted(peers, key=lambda x: x["ranking"] is None):
        # 확인된 동일 본품만 합친다. 같은 브랜드·성분인 다른 SKU는 별개다.
        aliases = {"MKT_ANUA_PDRN_SERUM": "OY_A000000222698"}
        identity = aliases.get(p["product_id"], p["product_id"])
        twin = next((k for k in kept if aliases.get(k["product_id"], k["product_id"]) == identity), None)
        if twin is None:
            kept.append(dict(p, also_seen=[]))
            continue
        seen = {c["copy_text"] for c in twin["copies"]}
        twin["copies"] = twin["copies"] + [c for c in p["copies"] if c["copy_text"] not in seen]
        twin["signals"] = twin["signals"] + [x for x in p["signals"] if x not in twin["signals"]]
        twin["also_seen"].append(f'{p.get("channel") or "다른 판매처"} {p["price_krw"]:,}원' if p.get("price_krw") else p["name"])
        twin["functions"] = twin["functions"] | p["functions"]
    kept.sort(key=lambda p: (-p["score"], p["ranking"] or 999, -(p["review_count"] or 0)))
    return kept


def price_benchmark(peers: list[dict]) -> dict | None:
    prices = [p["price_krw"] for p in peers if p.get("price_krw")]
    if not prices:
        return None
    return {"min": min(prices), "median": int(median(prices)), "max": max(prices), "n": len(prices)}


def appeal_summary(peers: list[dict]) -> list[dict]:
    """문구 유형별: 몇 개 제품이 쓰는지, 인기 상위 제품이 쓰는지, 규칙 판정이 어떤지."""
    popular = {p["product_id"] for p in peers if (p.get("ranking") or 999) <= 10}
    rows = []
    for t, desc in APPEAL_TYPES.items():
        users = [p for p in peers if any(t in c["types"] for c in p["copies"])]
        copies = [c | {"brand": p["brand"]} for p in peers for c in p["copies"] if t in c["types"]]
        levels = [c["level"] for c in copies if c["level"] is not None]
        rows.append({
            "type": t, "desc": desc, "products": len(users), "peers": len(peers),
            "popular_products": len([p for p in users if p["product_id"] in popular]),
            "copies": copies,
            "safe": sum(1 for x in levels if x == 0), "caution": sum(1 for x in levels if x == 1),
            "risky": sum(1 for x in levels if x == 2),
        })
    return rows


# ── 우리 제품용 후보 문구 ───────────────────────────────────────────────────
FORM_NOUN = {"세럼·앰플": "앰플", "크림": "크림", "토너": "토너", "로션": "로션", "마스크": "마스크",
             "클렌저": "클렌저", "미스트": "미스트"}
FUNCTION_CLAIM = {"미백": "피부 미백에 도움을 주는", "주름 개선": "피부 주름 개선에 도움을 주는"}


def candidate_copies(product: dict) -> list[dict]:
    """우리 제품 정보만으로 유형별 후보를 만든다 (강한 표현 → 안전한 표현 순)."""
    me = product_profile(product)
    name = product.get("name") or ""
    last = name.split()[-1] if name else ""
    noun = last if last and form_of(last) else FORM_NOUN.get(me["form"] or "", "") or last or "제품"
    skin = me["form"] is not None   # 샴푸 등 피부 제형이 아니면 피부 보습 표현을 만들지 않는다
    ingredients = product.get("key_ingredients") or []
    lead = ingredients[0] if ingredients else None
    out: list[dict] = []
    for ev in product.get("owned_evidence") or []:
        if ev.get("value") and ev.get("test_type") != "자사 설문":
            source = ", ".join(x for x in (ev.get("test_type"), ev.get("institute")) if x)
            out.append({"type": "효능 수치형", "copy": f"{ev['value']} ({source})",
                        "why": "보유 실증 수치를 그대로 쓰고 출처를 붙임"})
            break
    if product.get("category") == "기능성" and me["functions"]:
        claims = [FUNCTION_CLAIM[f] for f in ("미백", "주름 개선") if f in me["functions"]]
        if len(claims) == 2:
            out.append({"type": "효능 서술형", "copy": f"피부 미백과 주름 개선에 도움을 주는 2중 기능성 {noun}",
                        "why": "심사받은 기능성 범위 안의 효능 표현"})
        elif claims:
            out.append({"type": "효능 서술형", "copy": f"{claims[0]} 기능성 {noun}",
                        "why": "심사받은 기능성 범위 안의 효능 표현"})
    elif skin:
        out.append({"type": "효능 서술형", "copy": f"피부에 수분을 채워 촉촉하게 가꿔주는 {noun}",
                    "why": "일반 화장품이 쓸 수 있는 보습·가꿈 표현"})
    if lead:
        pair = " · ".join(ingredients[:2])
        out.append({"type": "성분 소구형", "copy": f"{pair} 함유 {noun}", "why": "들어 있는 성분 사실만 말함"})
    feel = f"끈적임 없이 산뜻하게 스며드는 {noun}" if skin else f"산뜻한 사용감의 {noun}"
    out.append({"type": "사용감형", "copy": feel, "why": "효능 주장 없이 사용감만 말함"})
    return out


STRENGTH = {"효능 수치형": 4, "효능 서술형": 3, "성분 소구형": 2, "사용감형": 1}


def judge_candidates(product: dict, candidates: list[dict], peers: list[dict], rule_engine: Any = None) -> list[dict]:
    """규칙 엔진으로 판정하고, 경쟁 제품 사용 현황을 붙여 추천 순서를 정한다."""
    if rule_engine is None:
        from cosmetic_agent.domain.rules import RuleEngine

        rule_engine = RuleEngine()
    summary = {row["type"]: row for row in appeal_summary(peers)}
    judged = []
    for c in candidates:
        report = rule_engine.evaluate(c["copy"], product)
        row = summary.get(c["type"], {})
        judged.append(c | {
            "level": report["level"], "violation_type": report.get("violation_type"),
            "next_test": report.get("next_test"),
            "peer_products": row.get("products", 0), "peer_popular": row.get("popular_products", 0),
        })
    usable = [j for j in judged if j["level"] == 0]
    best = max(usable, key=lambda j: (STRENGTH.get(j["type"], 0), j["peer_popular"], j["peer_products"]), default=None)
    for j in judged:
        j["recommended"] = j is best
    return judged
