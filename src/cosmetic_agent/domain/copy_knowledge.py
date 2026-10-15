"""광고문 생성용 '써도 되는 재료'를 모은다.

흩어져 있던 데이터를 성분·제품 기준으로 연결한다.
- 식약처 원료사전(21,945개): 성분 영문명과 유래 정의 → 사실 기반 유래 묘사
- 기능성 심사규정 고시 성분표: 성분이 기능성 고시 성분인지 → 제품 구분별로 쓸 수 있는 말이 달라짐
- 효능 단계(claim_ladder): 실증 없이도 쓸 수 있는 기본 사용감 표현(lv0)과 절대 불가 표현(lv9)
- 기능성 상한(functional_claims): 심사 효능 문구와 금지 표현
- 표현 각도(expression_bank): 장면·구성·사실 소구 각도
- 시장 문구 판정(market_copy_judgements): 규칙상 걸리지 않은 실제 상위 제품 문구 → 말투 참고
- 적발 보도자료(01_raw/cases): 실제 적발된 표현 → 피할 표현
"""
from __future__ import annotations

import json
import os
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[3] / "data"
ASSETS = DATA / "assets"


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _norm(name: str) -> str:
    return re.sub(r"[\s·,()]+", "", name or "").casefold()


@lru_cache(maxsize=1)
def ingredient_index() -> dict[str, dict[str, Any]]:
    """성분명(국문·이명·영문) → {kor, eng, origin}. 원본 6.8MB 를 한 번만 읽고 필요한 필드만 남긴다."""
    raw = _read(DATA / "01_raw" / "api" / "cosmetic_ingredients.json", {})
    index: dict[str, dict[str, Any]] = {}
    for item in raw.get("items", []):
        kor = (item.get("kor_name") or "").strip()
        if not kor:
            continue
        entry = {"kor": kor, "eng": item.get("eng_name"), "origin": origin_phrase(item.get("origin_definition"), kor)}
        for key in [kor, *(item.get("synonyms") or []), item.get("eng_name") or ""]:
            if key and _norm(key) not in index:
                index[_norm(key)] = entry
    return index


@lru_cache(maxsize=1)
def ingredient_names() -> list[str]:
    """제품 등록 화면의 성분 검색용 이름 목록 (식약처 원료사전 국문명).

    자주 쓰는 성분(기능성 고시 성분·성분 역할 카드·예시 제품 성분)을 앞에 두고 나머지는 가나다순.
    """
    raw = _read(DATA / "01_raw" / "api" / "cosmetic_ingredients.json", {})
    names = sorted({(x.get("kor_name") or "").strip() for x in raw.get("items", []) if (x.get("kor_name") or "").strip()})
    common: list[str] = []
    for group in _classes().get("functional_notified", {}).values():
        common += group
    cards = _read(DATA / "ingredient_knowledge" / "ingredient_cards.json", {}).get("cards", [])
    common += [a for card in cards for a in card.get("aliases", []) if re.fullmatch(r"[가-힣0-9\-]+", a)]
    for path in (ASSETS / "mock_products.json", ASSETS / "sample_products.json"):
        common += [i for prod in _read(path, []) for i in prod.get("key_ingredients") or []]
    known = set(names)
    head = [n for n in dict.fromkeys(common) if n in known]
    return head + [n for n in names if n not in set(head)]


def origin_phrase(definition: str | None, name: str = "") -> str | None:
    """'이 원료는 병풀 (Centella asiatica)의 전초에서 추출한 것이다.' → '병풀 전초에서 추출한 원료'.

    식물·미생물 유래처럼 출처가 분명한 경우만 만든다. 화학 구조 설명은 광고 재료가 아니므로 None.
    """
    text = definition or ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[A-Za-z][A-Za-z .,'\-]*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"이 원료는 (?:[가-힣 ]+?인 )?([가-힣]+) ?의 ([가-힣 ]{1,12}?)(?:을|를)? ?(?:증류하여|압착하여|발효하여)? ?(?:에서 )?(추출|얻)", text)
    if m:
        verb = "추출한" if m.group(3) == "추출" else "얻은"
        part = m.group(2).strip()
        if not part.endswith("에서"):
            part = re.sub(r"(을|를)$", "", part)
        return f"{m.group(1)} {part.removesuffix('에서')}에서 {verb} 원료"
    m = re.search(r"이 원료는 (?:[가-힣 ]+?인 )?([가-힣]+) ([가-힣]{1,3})에서 (?:추출|압착|얻)", text)
    if m:
        return f"{m.group(1)} {m.group(2)}에서 얻은 원료"
    m = re.search(r"미생물(?:인|의 일종인) ([가-힣]+)", text)
    if m and "발효" in text:
        return f"미생물 {m.group(1)} 발효로 얻은 원료"
    # 정의에서 출처를 못 읽은 식물 추출물은 이름에서 유래만 밝힌다 (예: 어성초추출물 → 어성초에서 얻은 추출물)
    if re.fullmatch(r"[가-힣]{2,10}(잎|꽃|뿌리|열매|씨)?추출물", name or ""):
        return f"{name.removesuffix('추출물')}에서 얻은 추출물"
    return None


@lru_cache(maxsize=1)
def _classes() -> dict[str, Any]:
    return _read(ASSETS / "ingredient_classes.json", {})


def _functional_kind(name: str) -> str | None:
    for kind, names in _classes().get("functional_notified", {}).items():
        if _norm(name) in {_norm(n) for n in names}:
            return kind
    return None


def _product_kinds(product: dict[str, Any]) -> set[str]:
    if product.get("category") != "기능성":
        return set()
    ftype = product.get("functional_type") or ""
    return {k for k, words in _classes().get("functional_type_keywords", {}).items() if any(w in ftype for w in words)}


def ingredient_card(name: str, product: dict[str, Any]) -> str:
    """성분 하나의 사실·허용 범위를 한 줄로."""
    found = ingredient_index().get(_norm(name))
    parts = [name]
    if found and found.get("eng"):
        parts[0] += f" ({found['eng']})"
    origin = found.get("origin") if found else origin_phrase(None, name)
    if origin:
        parts.append(f"유래: {origin}")
    if not found:
        parts.append("식약처 원료사전에서 이름을 찾지 못함 → 함유 사실만 쓰고 유래·영문명은 쓰지 말 것")
    kind = _functional_kind(name)
    if re.search(_classes().get("human_derived_pattern", "^$"), name):
        parts.append("인체 유래 원료 → 줄기세포·재생 연상 표현 금지, 성분명 표기만")
    elif kind and kind in _product_kinds(product):
        parts.append(f"{kind} 기능성 고시 성분 → '{kind} 기능성 성분 ○○ 함유'로 심사 문구와 연결 가능")
    elif kind:
        parts.append(f"{kind} 기능성 고시 성분이지만 이 제품은 {kind} 기능성이 아님 → 함유 사실만, '{kind}' 효능·'{kind} 성분' 표현 금지")
    else:
        parts.append("원료의 일반 효능을 제품 효과로 쓰지 말 것")
    return "- " + " · ".join(parts)


@lru_cache(maxsize=1)
def _ladder() -> list[dict[str, Any]]:
    return _read(ASSETS / "claim_ladder.json", [])


def sensory_phrases(product: dict[str, Any] | None = None) -> list[str]:
    """효능 단계 lv0 (실증 없이 쓸 수 있는 기본 표현). 모발·색조 전용 표현은 해당 제품에만 준다."""
    out = []
    for claim in _ladder():
        for level in claim.get("levels", []):
            if level.get("lv") == 0:
                out += [t.strip() for t in str(level.get("text", "")).split("/") if t.strip()]
    if product is not None:
        name = f"{product.get('name', '')} {product.get('form', '')}"
        hair = bool(re.search(r"샴푸|헤어|트리트먼트|두피|모발|린스|염모", name))
        makeup = bool(re.search(r"쿠션|파운데이션|팩트|립|틴트|색조|베이스", name))
        out = [t for t in out if (hair or not re.search(r"모발|두피|머릿결", t)) and (makeup or "색조" not in t)
               and (not hair or not re.search(r"피부톤|피부로", t))]
    # 진정은 실증 없이 쓰지 않는다 (준호 '일반 화장품 효능 어휘' 기준과 맞춤)
    out = [t for t in out if "진정" not in t]
    return list(dict.fromkeys(out))


def form_words(product: dict[str, Any]) -> tuple[str, list[str]]:
    """제형별 사용감 어휘 (data/assets/form_vocab.json). 제형·제품명으로 제형을 알 수 있을 때만 준다."""
    text = f"{product.get('form') or ''} {product.get('name') or ''}"
    for row in _read(ASSETS / "form_vocab.json", {}).get("forms", []):
        if re.search(row["match"], text):
            return row["form"], list(row.get("words", []))
    return "", []


def with_request_form(product: dict[str, Any], *texts: str) -> dict[str, Any]:
    """제품명·제형으로 제형을 모를 때 요청 문장('선크림 광고 만들어줘')에서 제형을 찾아 재료용 제품 정보에 붙인다.

    빠른 생성은 제품명이 '나의 화장품'이라 요청 문장 말고는 제형 단서가 없다. 재료(어휘·태그) 고르기에만 쓰고 제품 사실로 넣지 않는다."""
    if form_words(product)[0]:
        return product
    form = form_words({"name": " ".join(t for t in texts if t)})[0]
    return dict(product, form=form) if form else product


def market_tags(product: dict[str, Any]) -> list[str]:
    """같은 제형의 올리브영 랭킹 홍보 태그어 (효능·순위·수치 없는 말만, form_vocab.json market_tags)."""
    text = f"{product.get('form') or ''} {product.get('name') or ''}"
    for row in _read(ASSETS / "form_vocab.json", {}).get("forms", []):
        if re.search(row["match"], text):
            return list(row.get("market_tags", []))
    return []


@lru_cache(maxsize=1)
def _bank_rows() -> tuple[dict[str, Any], ...]:
    path = ASSETS.parent / "copy_bank" / "bank.jsonl"
    if not path.exists():
        return ()
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def copy_bank(product: dict[str, Any], rng: random.Random, per_type: int = 3) -> dict[str, list[str]]:
    """표현 은행(data/copy_bank/bank.jsonl)에서 같은 제형 + 공통 항목을 종류별로 몇 개씩 고른다. 같은 제형을 먼저 채운다."""
    form = form_words(product)[0]
    out: dict[str, list[str]] = {}
    for kind in ("scene", "template", "sensory_vocab", "angle"):
        own = [r["text"] for r in _bank_rows() if r["type"] == kind and form and r.get("form") == form]
        common = [r["text"] for r in _bank_rows() if r["type"] == kind and not r.get("form")]
        picked = rng.sample(own, min(per_type, len(own)))
        picked += rng.sample(common, min(per_type - len(picked), len(common)))
        if picked:
            out[kind] = picked
    return out


def forbidden_examples(product: dict[str, Any]) -> list[str]:
    """lv9(불가) 표현 + 기능성 금지 표현 + 실제 적발 보도자료 속 따옴표 표현."""
    out = [t.strip() for c in _ladder() for lv in c.get("levels", []) if lv.get("lv") == 9
           for t in str(lv.get("text", "")).split("/") if t.strip()]
    for claim in _read(ASSETS / "functional_claims.json", []):
        out += claim.get("banned", [])[:3]
    out += case_phrases()
    return list(dict.fromkeys(out))


@lru_cache(maxsize=1)
def case_phrases() -> list[str]:
    """식약처 적발 보도자료에서 따옴표로 인용된 위반 표현."""
    phrases = []
    for path in sorted((DATA / "01_raw" / "cases").glob("case_*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        phrases += [p.strip() for p in re.findall(r"[“\"‘']([^”\"’'\n]{2,20})[”\"’']", text)]
    # 보도자료에는 허용 예시·주의 문구·웹페이지 잔여물도 따옴표로 섞여 있다. 위반 표현만 남긴다.
    violation = re.compile(r"치료|예방|재생|염증|무좀|세포|침투|약$|약\s|발모|탈모\s*(방지|개선|예방)|완치|살균")
    noise = re.compile(r"[+,]|사용하지|인증마크|민･관|도움")
    return list(dict.fromkeys(p for p in phrases if violation.search(p) and not noise.search(p)))[:40]


@lru_cache(maxsize=1)
def market_examples() -> list[dict[str, Any]]:
    """규칙상 걸리지 않은(judge_level 0) 실제 상위 제품 문구."""
    path = DATA / "sales_forecast_reference" / "copy_comparison" / "market_copy_judgements.jsonl"
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        types = row.get("문구 유형") or []
        text = (row.get("copy_text") or "").strip()
        # 성분·사용감 소구 방식만 참고한다. 효능·순위·구성 문구는 우리 제품 근거와 무관하고, 짧은 조각은 말투 참고가 안 된다.
        usable = set(types) & {"사용감형", "성분 소구형"} and not set(types) & {"효능 서술형", "효능 수치형", "비교·순위형"}
        if row.get("judge_level") == 0 and usable and len(text) >= 6 and not re.search(r"\d", text):
            rows.append({"text": text, "type": "·".join(t for t in types if t in ("사용감형", "성분 소구형"))})
    return rows


@lru_cache(maxsize=1)
def expression_bank() -> dict[str, Any]:
    return _read(ASSETS / "expression_bank.json", {"angles": [], "channel_hints": {}})


def pick_angles(product: dict[str, Any], has_origin: bool, rng: random.Random, n: int = 3) -> list[dict[str, Any]]:
    """후보마다 다른 각도. strong 은 근거·기능성 각도를 우선 배정한다."""
    has_evidence = bool(product.get("owned_evidence"))
    functional = product.get("category") == "기능성" and bool(product.get("functional_type"))
    has_ingredients = bool(product.get("key_ingredients"))
    usable = [a for a in expression_bank().get("angles", [])
              if (a.get("requires") or "") in ("", "evidence" if has_evidence else "-",
                                              "functional" if functional else "-", "origin" if has_origin else "-",
                                              "ingredients" if has_ingredients else "-")]
    strong_pool = [a for a in usable if a.get("requires") in ("evidence", "functional")]
    rest = [a for a in usable if a not in strong_pool]
    rng.shuffle(strong_pool)
    rng.shuffle(rest)
    # 원료사전 유래 정보가 있으면 성분 유래 각도를 반드시 한 후보에 배정한다 (데이터 연결의 핵심 재료)
    origin = [a for a in rest if a["id"] == "origin_story"]
    rest = origin + [a for a in rest if a["id"] != "origin_story"]
    ordered = (strong_pool[:2] + rest) if strong_pool else rest
    return ordered[:n]


def _role_suffix(name: str, profiles: list[dict[str, Any]]) -> str:
    """준호 님 성분 역할 카드(연구 출처 있음)가 연결된 성분이면 역할·표현 방향·주장 금지를 덧붙인다."""
    for prof in profiles:
        if name in prof.get("matched_ingredients", []):
            return (f" · [{prof['reference_id']}] 역할: {'·'.join(prof.get('roles', []))}"
                    f" / 표현 방향: {' / '.join(prof.get('copy_angles', []))}"
                    f" / 주장 금지: {'·'.join(prof.get('avoid_claims', []))}")
    return ""


def _usable_market_copy(text: str, types: list[str]) -> bool:
    """말투 참고로 쓸 만한 시장 문구: 구성·순위·수치 소구 문구와 짧은 조각은 뺀다.

    같은 제형·공통 성분으로 매칭된 문구는 상품명 속 숫자(예: 어성초 77)를 허용하고, 숫자는 프롬프트에서 옮기지 못하게 한다.
    """
    return len(text.strip()) >= 6 and not set(types) & {"구성·혜택형", "비교·순위형", "효능 수치형"}


def build_generation_knowledge(
    product: dict[str, Any],
    channel: str = "",
    rng: random.Random | None = None,
    market_refs: list[dict[str, Any]] | None = None,
    profiles: list[dict[str, Any]] | None = None,
    tone: str = "",
) -> str:
    """생성 프롬프트에 넣을 [쓸 수 있는 재료] 블록.

    market_refs·profiles 는 준호 님 생성 연결(같은 제형·공통 성분 시장 문구 M번호, 연구 출처 성분 역할 카드 I번호).
    """
    rng = rng or random.Random()
    profiles = profiles or []
    mz = channel in ("SNS", "라이브커머스", "배너") or bool(re.search(r"MZ|엠지|트렌디|발랄|재치|친근|힙", tone or "", re.I))
    ingredients = list(dict.fromkeys(product.get("key_ingredients") or []))
    cards = [ingredient_card(name, product) + _role_suffix(name, profiles) for name in ingredients[:8]]
    has_origin = any("유래:" in c for c in cards)
    slots = ["strong", "strong", "balanced", "balanced", "safe", "safe"]
    angles = pick_angles(product, has_origin, rng, n=len(slots))
    angles += angles[: len(slots) - len(angles)]  # 쓸 수 있는 각도가 6개보다 적으면 앞에서부터 다시 쓴다
    lines = ["[성분 카드 - 식약처 원료사전·기능성 고시 성분표 기준]", *(cards or ["- 입력된 성분 없음 (성분 이야기는 하지 말 것)"])]
    lines += ["", "[이번 후보별 표현 각도 - 후보 6개가 서로 다른 각도로 쓴다]"]
    lines += [f"- 후보 {i} ({tier}): {a['name']} — {a['how']} (예: {a['example']})"
              for i, (tier, a) in enumerate(zip(slots, angles), 1)]
    # 실증 수치가 없는 제품에 '숫자 전면 배치'를 주면 모델이 숫자를 지어내다 탈락한다
    hooks = [h for h in expression_bank().get("hooks", [])
             if h.get("requires") != "evidence" or product.get("owned_evidence")]
    if hooks:
        lines += ["", "[끌림 기법 - 모든 후보의 첫 구절에 하나 이상 쓴다. 기법을 썼다고 효능 주장이 허용되지는 않는다]"]
        lines += [f"- {h['name']}: {h['how']} (예: {h['example']})" for h in rng.sample(hooks, min(6, len(hooks)))]
    bank = expression_bank()
    if mz and bank.get("mz_ok"):
        lines += ["", f"[MZ 말투 - {bank.get('mz_note', '')}]",
                  "- 써도 됨: " + ", ".join(bank["mz_ok"]),
                  "- 쓰지 않음(효과·최고 보증): " + ", ".join(bank.get("mz_avoid", []))]
        tags = market_tags(product)
        if tags:
            lines.append("- 같은 제형 올리브영 랭킹 태그어(헤드라인 앞 [ ] 태그나 해시태그로 1개까지): " + ", ".join(tags))
    hint = expression_bank().get("channel_hints", {}).get(channel)
    if hint:
        lines += ["", f"[채널 문법 - {channel}] {hint}"]
    sensory = sensory_phrases(product)
    if sensory:
        lines += ["", "[쓸 수 있는 사용감 표현 - 효능 단계 lv0, 실증 없이 가능]", "- " + ", ".join(rng.sample(sensory, min(8, len(sensory))))]
    form, words = form_words(product)
    if words:
        lines += ["", f"[제형 사용감 어휘 - {form}. 제품 사실(질감·향)과 다르면 제품 사실이 우선]",
                  "- " + ", ".join(rng.sample(words, min(6, len(words))))]
    matched = [f"- {r['reference_id']} ({'·'.join(r.get('copy_types') or []) or '시장 문구'}) {r['copy_text']}"
               for r in (market_refs or []) if _usable_market_copy(r.get("copy_text") or "", r.get("copy_types") or [])][:4]
    # 일반 예시는 우리 제품에 없는 성분(PDRN·히알루론산 등)을 부르는 문구를 빼고 채운다.
    # 그런 예시가 들어가면 모델이 다른 성분을 끼워 넣고, 미확인 성분 검사에 걸려 후보가 줄어든다.
    from ..market_reference import ingredient_groups

    own = ingredient_groups(" ".join([product.get("name", ""), *ingredients]))
    general = [m for m in market_examples() if ingredient_groups(m["text"]) <= own]
    fill = [f"- ({m['type']}) {m['text']}" for m in rng.sample(general, min(max(0, 4 - len(matched)), len(general)))]
    # 표현 은행은 기본으로 끈다: 블라인드 비교에서 끌림 승률 46%로 제품 사실만 쓸 때보다 낫지 않았다 (COPY_BANK=1 로 켬)
    bank = copy_bank(product, rng) if os.environ.get("COPY_BANK") == "1" else {}
    if bank:
        names = {"scene": "사용 장면", "template": "문장 구조", "sensory_vocab": "감각 어휘", "angle": "설득 각도"}
        lines += ["", "[수집 표현 재료 - 실제 광고에서 뽑아 추상화한 장면·구조. 문장을 그대로 쓰지 말고 우리 제품 사실로 채운다]"]
        lines += [f"- {names[k]}: " + " / ".join(v) for k, v in bank.items()]
        fill = fill[:1]  # 표현 은행이 있으면 일반 시장 예시는 하나만 (프롬프트 길이·베끼기 방지)
    if matched or fill:
        lines += ["", "[말투 참고 - 실제 시장 문구. 문장·제품명·수치를 베끼지 말고 구성만 참고. M번호는 같은 제형·공통 성분 제품]"]
        lines += matched + fill
    avoid = forbidden_examples(product)
    if avoid:
        lines += ["", "[실제 적발·불가 표현 - 이런 말은 돌려서도 쓰지 않는다]", "- " + ", ".join(rng.sample(avoid, min(12, len(avoid))))]
    return "\n".join(lines)


POWER_RE = re.compile(r"[가-힣]{1,12}의\s*(힘|에너지|기운)")
NATURAL_RE = re.compile(r"천연|자연\s*그대로|100\s*%\s*자연|순수한\s*자연|자연의\s*[가-힣]{1,6}|자연이\s*(준|주는|담은)|자연을\s*담")
ORIGIN_WORD_RE = re.compile(r"(자연|식물|천연)\s*(에서\s*)?(유래|온|얻은)")
FUNCTIONAL_WORD_RE = re.compile(r"기능성\s*(고시\s*)?(성분|원료)")


def material_claim_notes(text: str, product: dict[str, Any]) -> list[str]:
    """재료를 쓰면서 생기기 쉬운 잘못을 생성 단계에서 되돌려 보낸다 (검토용 판정 규칙은 아님).

    - 원료·자연의 '힘'으로 효과를 내는 것처럼 쓰기 (원료 효능 → 제품 효과)
    - 천연·자연 그대로 (천연화장품 기준 충족 여부를 모름)
    - 기능성 고시 성분이 아닌 원료를 '기능성 성분'이라고 부르기
    """
    notes = []
    if POWER_RE.search(text):
        notes.append("원료·자연의 '힘'으로 효과를 내는 것처럼 썼습니다. 유래는 사실로만 쓰고 효과와 잇지 마세요.")
    if NATURAL_RE.search(text):
        notes.append("천연·자연 그대로 표현은 천연화장품 기준 확인이 필요합니다. 원료 유래 사실로 바꾸세요.")
    if ORIGIN_WORD_RE.search(text):
        unknown = [name for name in product.get("key_ingredients") or []
                   if name in text and not (ingredient_index().get(_norm(name)) or {}).get("origin")
                   and not origin_phrase(None, name)]
        if unknown:
            notes.append(f"원료사전에 유래 정보가 없는 원료({', '.join(unknown)})에 자연·식물 유래를 붙였습니다. 성분 카드의 유래만 쓰세요.")
    if len(re.sub(r"#\S+|[^가-힣]", "", text)) < 8:
        notes.append("해시태그·기호만 있는 후보입니다. 문장으로 된 광고 문구를 쓰세요.")
    if FUNCTIONAL_WORD_RE.search(text):
        kinds = _product_kinds(product)
        wrong = [name for name in product.get("key_ingredients") or []
                 if name in text and _functional_kind(name) not in kinds]
        if wrong:
            notes.append(f"기능성 고시 성분이 아닌 원료({', '.join(wrong)})를 기능성 성분처럼 썼습니다. 고시 성분만 그렇게 부르세요.")
    return notes
