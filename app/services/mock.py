"""
[app/services/mock.py]
데모용 Mock 판정 엔진. 실제 AI 판정이 아니다 — 응답에 mock=True 를 붙이고 화면이 "데모 데이터"로 표시한다.

- 규칙 자산(data/assets)과 원문(data/01_raw)만으로 결정적으로 판정한다. 같은 입력이면 같은 출력이다.
- 근거 조항 발췌는 data_sources 가 법령 XML · 관리지침 · 보도자료에서 그대로 뽑는다. 지어낸 조문은 없다.
- 백엔드가 붙으면(UI_DATA_MODE=api) 이 파일은 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.services import data_sources as ds
from app.services.contract import PIPELINE_STEPS


# ── 위험 표현 후보 ────────────────────────────────────────────────────
@dataclass
class Hit:
    start: int
    end: int
    text: str
    kind: str                      # risk · verified
    label: str
    violation: str | None
    level: int | None
    reason: str
    group: str                     # 근거 묶음: medical · scope · functional · exaggeration · superlative · proof · compare · doctor · verified
    guide_key: str | None = None   # 관리지침 금지 표현 행을 찾을 낱말
    case_date: str | None = None   # 관련 적발 사례
    cites: list[int] = field(default_factory=list)
    decisive: bool = False


# (정규식, 관리지침 행 낱말, 적발 사례 날짜, 이유)  — 의약품 오인 (level 2)
_MEDICAL: list[tuple[str, str | None, str | None, str]] = [
    (r"(?:완벽(?:하게|히|한)?\s*)?(?:피부|세포|진피|모발)?\s?재생(?:시켜|시킵니다|시키는|효과)?",
     "피부재생", "2025-08-06", "관리지침이 금지한 표현 '피부재생, 세포 재생'에 해당합니다."),
    (r"(?:여드름|아토피|피부염|염증|무좀|질염|흉터|트러블)\s*(?:을|를)?\s*(?:치료|완치)(?:\s*효과)?",
     None, "2026-07-24", "질병을 치료한다는 표현은 의약품으로 오인될 수 있습니다."),
    (r"(?:치료|완치)(?:\s*효과)?", None, "2026-07-24", "질병을 치료한다는 표현은 의약품으로 오인될 수 있습니다."),
    (r"(?:항염|소염|염증\s*(?:완화|억제|개선))(?:\s*(?:효과|작용))?", "항염", "2025-08-06",
     "관리지침이 금지한 의학적 효능 표현 '항염·진통'에 해당합니다."),
    (r"살균|소독", "살균", None, "관리지침이 금지한 의학적 효능 표현 '살균·소독'에 해당합니다."),
    (r"아토피", "아토피", "2026-07-24", "관리지침이 금지한 질병 관련 표현 '아토피'에 해당합니다."),
    (r"(?:흉터|흔적)\S{0,3}\s*(?:제거|없애|지워)", "흔적을", None, "흉터·흔적을 없앤다는 표현은 관리지침이 금지합니다."),
    (r"디톡스|독소\s*(?:제거|배출)", "디톡스", None, "피부 독소를 제거한다는 표현은 관리지침이 금지합니다."),
    (r"혈액\s*순환", "혈액순환", None, "관리지침이 금지한 생리활성 표현 '혈액순환'에 해당합니다."),
    (r"(?:발모|육모|양모)(?:\s*효과)?|모발\s*(?:이\s*)?(?:자라|성장|굵기\s*증가)", "발모", "2025-12-22",
     "관리지침이 금지한 모발 관련 표현 '발모·육모·양모'에 해당합니다."),
    (r"탈모\s*(?:방지|예방|치료)(?:\s*효과)?", "탈모방지", "2025-04-14",
     "관리지침이 금지한 모발 관련 표현 '탈모방지, 탈모치료'에 해당합니다."),
    (r"(?:기미|주근깨)\S{0,2}\s*(?:완벽(?:하게|히)?\s*)?(?:제거|없애|치료)", "기미", None,
     "기미·주근깨를 없앤다는 표현은 의학적 효능으로 오인될 수 있습니다."),
    (r"(?:홍조|홍반)\s*(?:개선|제거|완화)", "홍조", None, "홍조·홍반을 개선한다는 표현은 관리지침이 금지합니다."),
    (r"(?:콜라겐|엘라스틴)\s*(?:생성|증가|촉진|활성)|세포\s*(?:활력|활성화|성장)", "세포 활력", None,
     "피부 구성 물질을 늘리거나 세포를 활성화한다는 표현은 관리지침이 금지합니다."),
    (r"보톡스(?:\s*효과)?|필러\s*효과|시술\s*효과", None, None, "시술 효과를 표방하는 표현은 의약품으로 오인될 수 있습니다."),
]

# 화장품 범위 이탈 (level 2)
_SCOPE: list[tuple[str, str | None, str]] = [
    (r"다이어트|체중\s*감량|지방\s*분해|살\s*(?:이\s*)?빠", "다이어트", "체중·체형 변화는 화장품의 범위를 벗어난 표현입니다."),
    (r"셀룰라이트", "셀룰라이트", "관리지침이 금지한 표현 '셀룰라이트'에 해당합니다."),
    (r"얼굴\s*(?:크기|윤곽)|브이\s*라인|V\s*라인", "얼굴 크기", "얼굴 크기·윤곽을 바꾼다는 표현은 화장품의 범위를 벗어납니다."),
]

# 일반 화장품이 말하면 기능성 오인이 되는 효능 (효능 분류, 정규식)
_FUNCTIONAL: list[tuple[str, str]] = [
    ("미백", r"미백|화이트닝|(?:기미|잡티|주근깨)\s*(?:개선|완화|옅게)|피부\s*톤\s*(?:개선|밝게)"),
    ("주름", r"주름\s*(?:개선|완화|감소|싹|펴|없애)|잔주름"),
    ("탈모", r"탈모\s*(?:증상\s*)?(?:완화|개선)"),
    ("여드름", r"여드름\s*(?:성\s*피부\s*)?(?:완화|개선|진정)"),
]

_EXAGGERATION = (r"(?:폭발적|획기적|극적|드라마틱|놀라운|기적(?:의|적인|처럼)?|완벽(?:하게|히|한)?|100\s*%|영구(?:적|히)?"
                 r"|즉시|즉각(?:적)?|단숨에|순식간에)(?:\s*(?:개선|효과|변화|흡수|진정))?")
_SUPERLATIVE = r"최고|최상|넘버\s*원|No\.?\s*1|1\s*위|유일(?:한|무이)?|단\s*하나뿐"
_COMPARE = r"타사[^,.!?]{0,15}?대비(?:\s*\d+(?:\.\d+)?\s*배)?|(?:경쟁|기존|일반)\s*제품\s*(?:대비|보다)|\d+(?:\.\d+)?\s*배\s*(?:더|이상)?"
_DOCTOR = r"피부과\s*(?:급|전문의)|(?:의사|전문의|약사)\s*(?:추천|인증|개발)"
_DURATION = r"\d+\s*시간[^,.!?]{0,8}?지속"
_NUMBER = r"\d+(?:\.\d+)?\s*(?:%|퍼센트|주|일|시간|개월|회)"
_NOVEL = r"엑소좀|줄기\s*세포|PDRN|연어\s*DNA|마이크로\s*니들|성장\s*인자|EGF"

_LABEL = {
    "medical": "의약품 오인", "scope": "범위 이탈", "functional": "기능성 오인", "exaggeration": "과장 표현",
    "superlative": "최상급 표현", "proof": "실증 필요", "compare": "비교 표현", "doctor": "전문가 표방",
}


def iga(word: str) -> str:
    """받침에 맞는 주격 조사 '이/가'."""
    last = re.sub(r"\s*\([^)]*\)\s*$", "", word or "").rstrip()[-1:]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "이(가)"


def _flat(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _case_for(word: str, default: str | None) -> str | None:
    if re.search(r"여드름|질염|트러블", word):
        return "2026-07-24"
    if re.search(r"탈모|발모|모발", word):
        return "2025-12-22"
    if re.search(r"재생|염증|항염|소염", word):
        return "2025-08-06"
    return default


def _guide_for(word: str, default: str | None) -> str | None:
    for key, pat in (("여드름", r"여드름"), ("아토피", r"아토피"), ("항염", r"염증|항염|소염"),
                     ("탈모방지", r"탈모"), ("피부재생", r"재생")):
        if re.search(pat, word):
            return key
    return default


def _numbers_in(text: str) -> list[str]:
    return [_flat(m.group(0)) for m in re.finditer(_NUMBER, text or "")]


def _candidates(text: str, product: dict) -> list[Hit]:
    """문장에서 판정 후보를 모두 뽑는다 (겹침 정리 전)."""
    own_claim = ds.claim_of_product(product)
    out: list[Hit] = []

    def add(m: re.Match, **kw) -> None:
        span = m.group(0).strip()
        if not span:
            return
        start = m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
        out.append(Hit(start=start, end=start + len(span), text=span, **kw))

    for pat, guide, case, reason in _MEDICAL:
        for m in re.finditer(pat, text):
            word = m.group(0)
            if own_claim == "여드름" and re.search(r"여드름", word) and not re.search(r"치료|완치", word):
                continue
            add(m, kind="risk", label=_LABEL["medical"], violation="의약품오인", level=2, reason=reason,
                group="medical", guide_key=_guide_for(word, guide), case_date=_case_for(word, case))
    for entry in ds.functional_claims():                      # 기능성 표현 금지어 (functional_claims.json)
        for phrase in entry["banned"]:
            for part in re.split(r"[/]", re.sub(r"\(.*?\)", "", phrase)):
                part = part.strip()
                if len(part) >= 2:
                    for m in re.finditer(re.escape(part).replace(r"\ ", r"\s*"), text):
                        add(m, kind="risk", label=_LABEL["medical"], violation="의약품오인", level=2,
                            reason=f"'{part}'는 {entry['type']} 기능성 범위를 넘는 금지 표현입니다.", group="medical",
                            guide_key=_guide_for(part, None), case_date=_case_for(part, None))
    for key, meaning in ds.term_map().items():                 # 은어·변형 표현 (term_map.json)
        for m in re.finditer(re.escape(key).replace(r"\ ", r"\s*"), text):
            medical = "의약품" in meaning
            add(m, kind="risk", label=_LABEL["medical" if medical else "functional"],
                violation="의약품오인" if medical else "기능성오인", level=2,
                reason=f"'{key}'는 {meaning} 표현으로 봅니다.", group="medical" if medical else "functional",
                case_date=_case_for(key, None))
    for term in ds.banned_terms():                            # 금지 표현 사전 (banned_terms.json)
        for m in re.finditer(term["pattern"], text):
            add(m, kind="risk", label=_LABEL["medical"], violation=term.get("type", "의약품오인"),
                level=int(term.get("level", 2)), reason=f"금지 표현 사전 '{term['term']}'에 해당합니다.",
                group="medical", guide_key=_guide_for(m.group(0), None), case_date=_case_for(m.group(0), None))
    for pat, guide, reason in _SCOPE:
        for m in re.finditer(pat, text):
            add(m, kind="risk", label=_LABEL["scope"], violation="범위이탈", level=2, reason=reason,
                group="scope", guide_key=guide)
    for claim, pat in _FUNCTIONAL:
        if claim == own_claim:
            continue
        for m in re.finditer(pat, text):
            what = ds.CLAIM_TO_FUNCTIONAL.get(claim, claim)
            reason = (f"일반 화장품이 '{what}' 기능성 효능을 말하면 기능성화장품으로 오인됩니다." if product.get("category") != "기능성"
                      else f"이 제품의 심사 효능은 '{product.get('functional_type')}'입니다. '{what}' 효능은 쓸 수 없습니다.")
            add(m, kind="risk", label=_LABEL["functional"], violation="기능성오인", level=2, reason=reason,
                group="functional", case_date="2025-06-20")
    for m in re.finditer(_DOCTOR, text):
        add(m, kind="risk", label=_LABEL["doctor"], violation="의약품오인", level=2,
            reason="의사·전문가가 추천하거나 개발했다는 표현은 쓸 수 없습니다.", group="doctor")
    for m in re.finditer(_SUPERLATIVE, text):
        add(m, kind="risk", label=_LABEL["superlative"], violation="소비자오인", level=2,
            reason="'최고·1위' 같은 배타적 절대 표현은 객관적으로 확인되지 않으면 쓸 수 없습니다.", group="superlative")
    for m in re.finditer(_EXAGGERATION, text):
        add(m, kind="risk", label=_LABEL["exaggeration"], violation="소비자오인", level=1,
            reason="효과를 부풀려 소비자를 오인하게 하는 과장 표현입니다.", group="exaggeration")
    for m in re.finditer(_COMPARE, text):
        add(m, kind="risk", label=_LABEL["compare"], violation="비교광고", level=1,
            reason="비교 대상과 기준, 객관적 시험 결과를 밝혀야 하는 비교 표현입니다.", group="compare")

    evidence = product.get("owned_evidence") or []
    for m in re.finditer(_DURATION, text):
        owned = any(_flat(re.search(r"\d+\s*시간", m.group(0)).group(0)) in _flat(ev.get("value") or "") for ev in evidence)
        if not owned:
            add(m, kind="risk", label=_LABEL["proof"], violation="실증필요", level=1,
                reason="보습 지속 시간은 보유한 실증 자료로 뒷받침되지 않습니다.", group="proof")
    for m in re.finditer(_NUMBER, text):
        num = _flat(m.group(0))
        matched = [ev for ev in evidence if num in _flat(ev.get("value") or "")]
        if matched and all(ds.evidence_kind(ev) == "survey" for ev in matched):
            add(m, kind="risk", label=_LABEL["proof"], violation="실증필요", level=1,
                reason="만족도 조사는 효능을 뒷받침하는 실증자료로 인정되지 않습니다(실증규정 제3조 ③).", group="proof")
        elif matched:
            ev = matched[0]
            add(m, kind="verified", label="실증 일치", violation=None, level=None,
                reason=f"보유한 {ev['test_type']} 결과({ev.get('value')})와 일치합니다.", group="verified")
        else:
            add(m, kind="risk", label=_LABEL["proof"], violation="실증필요", level=1,
                reason="체크한 실증 자료에 없는 수치입니다. 시험 결과가 있어야 쓸 수 있습니다.", group="proof")
    return out


def detect(text: str, product: dict) -> list[Hit]:
    """겹치는 후보를 정리한 최종 표현 목록 (원문 순서). 높은 단계·긴 표현이 우선한다."""
    cands = _candidates(text, product)
    cands.sort(key=lambda h: (0 if h.kind == "risk" else 1, -(h.level or 0), -(h.end - h.start), h.start))
    kept: list[Hit] = []
    for h in cands:
        if any(h.start < k.end and k.start < h.end for k in kept):
            continue
        kept.append(h)
    kept.sort(key=lambda h: h.start)
    risks = [h for h in kept if h.kind == "risk"]
    if risks:
        top = max(h.level or 0 for h in risks)
        next(h for h in risks if h.level == top).decisive = True
    return kept


# ── 근거 조항 (원문 발췌) ─────────────────────────────────────────────
def _law13(ho: str) -> dict:
    return {"chunk_id": "LAW_화장품법_제13조", "source": "화장품법", "article": f"제13조 제1항 제{ho}호", "authority": 1,
            "content_snippet": ds.article_excerpt("화장품법", "제13조", "①", (f"{ho}.",))}


def _law14() -> dict:
    return {"chunk_id": "LAW_화장품법_제14조", "source": "화장품법", "article": "제14조 제1항", "authority": 1,
            "content_snippet": ds.article_excerpt("화장품법", "제14조", "①")}


def _law4() -> dict:
    return {"chunk_id": "LAW_화장품법_제4조", "source": "화장품법", "article": "제4조 제1항(기능성화장품의 심사)", "authority": 1,
            "content_snippet": ds.clip(ds.article_excerpt("화장품법", "제4조", "①"), 260)}


def _annex5(mok: str) -> dict:
    return {"chunk_id": f"LAW_시행규칙_별표5-2{mok}", "source": "화장품법 시행규칙", "article": f"[별표 5] 제2호 {mok}목",
            "authority": 1, "content_snippet": ds.clip(ds.annex_excerpt("시행규칙", "5", "2", mok), 300)}


def _notice3(survey: bool = False) -> dict:
    text = ds.article_excerpt("실증규정", "제3조", "③", examples=1 if survey else 0)
    return {"chunk_id": "NOTICE_실증규정_제3조", "source": "화장품 표시·광고 실증에 관한 규정", "article": "제3조(실증자료)",
            "authority": 2, "content_snippet": ds.clip(text, 300)}


def _notice4() -> dict:
    return {"chunk_id": "NOTICE_실증규정_제4조", "source": "화장품 표시·광고 실증에 관한 규정", "article": "제4조(시험 결과의 요건)",
            "authority": 2, "content_snippet": ds.clip(ds.article_excerpt("실증규정", "제4조"), 260)}


def _guide(key: str | None) -> dict | None:
    row = ds.find_guide_row(key) if key else None
    if not row:
        return None
    idx = ds.guide_rows().index(row) + 1
    note = f" (비고: {row['note']})" if row.get("note") else ""
    return {"chunk_id": f"GUIDE_관리지침_별표1-{idx}", "source": "화장품 표시·광고 관리 지침",
            "article": f"[별표 1] {row['category']}", "authority": 3,
            "content_snippet": ds.clip(f"금지 표현: {row['text']}{note}", 300)}


def _case(date: str | None, keywords: tuple[str, ...]) -> dict | None:
    case = ds.case_document(date) if date else None
    if not case:
        return None
    return {"chunk_id": f"CASE_{date}", "source": "식약처 보도자료", "article": f"{date} {case['title']}", "authority": 4,
            "content_snippet": ds.case_excerpt(f"CASE_{date}", keywords, 260)}


def _citations_for(h: Hit) -> list[dict]:
    words = (h.text,)
    if h.group == "medical":
        return [c for c in (_law13("1"), _annex5("가"), _guide(h.guide_key), _case(h.case_date, words)) if c]
    if h.group == "doctor":
        return [_law13("1"), _annex5("다")]
    if h.group == "scope":
        return [c for c in (_law13("1"), _annex5("아"), _guide(h.guide_key)) if c]
    if h.group == "functional":
        return [c for c in (_law13("2"), _annex5("나"), _law4(), _case(h.case_date, words)) if c]
    if h.group == "superlative":
        return [_annex5("바"), _law13("4")]
    if h.group == "exaggeration":
        return [_law13("4"), _annex5("사")]
    if h.group == "compare":
        return [_annex5("바"), _notice3()]
    if h.group == "proof":
        return [_law14(), _notice3(survey="만족도" in h.reason), _notice4()]
    return []


def _assemble_citations(hits: list[Hit]) -> list[dict]:
    """결정 표현의 근거가 먼저 오게 모으고, 권위 순으로 정렬해 최대 5개. 표현마다 근거 번호를 단다."""
    risks = sorted([h for h in hits if h.kind == "risk"], key=lambda h: (not h.decisive, -(h.level or 0), h.start))
    pool: dict[str, dict] = {}
    order: list[str] = []
    per_hit: dict[int, list[str]] = {}
    for h in risks:
        ids = []
        for c in _citations_for(h):
            if not c.get("content_snippet"):
                continue
            if c["chunk_id"] not in pool:
                pool[c["chunk_id"]] = c
                order.append(c["chunk_id"])
            ids.append(c["chunk_id"])
        per_hit[id(h)] = ids
    chosen = order[:5]
    chosen.sort(key=lambda cid: (pool[cid]["authority"], order.index(cid)))
    number = {cid: i + 1 for i, cid in enumerate(chosen)}
    for h in risks:
        h.cites = sorted({number[cid] for cid in per_hit[id(h)] if cid in number})
    for h in hits:
        if h.kind == "verified":
            proof = [number[c] for c in ("NOTICE_실증규정_제3조",) if c in number]
            h.cites = proof
    return [pool[cid] for cid in chosen]


# ── 제안 문구 ────────────────────────────────────────────────────────
def _first(text: str) -> str:
    return text.split(" / ")[0].strip()


def _polish(phrase: str) -> str:
    """사다리 예시 표현을 광고 문장 끝맺음으로."""
    p = phrase.strip()
    if p.endswith("도움"):
        return p + "을 줍니다"
    if p.endswith("줌"):
        return p[:-1].rstrip() + " 줍니다"
    if p.endswith("세정"):
        return p + "합니다"
    if p.endswith("정돈"):
        return p + "해 줍니다"
    if p.endswith("예방"):
        return p + "에 도움을 줍니다"
    return p


def _evidence_phrase(ev: dict) -> str | None:
    """인체적용시험 결과 수치를 그대로 쓴 문장. 수치가 없으면 None."""
    value = (ev.get("value") or "").strip()
    if not re.search(r"\d", value) or "유의" in value:
        return None
    return re.sub(r"(?<!피부 )보습력", "피부 보습력", value)


def _suggestion(claim: str | None, ladder: dict | None, product: dict, text: str, hits: list[Hit]) -> tuple[str | None, str, str]:
    """(제안 문구, 출처 괄호, 제안 방향)."""
    if ladder:
        reach = ladder["reachable"]
        rung = next(r for r in ladder["rungs"] if r["lv"] == reach)
        if reach == 2 and "인체적용시험" in rung["needs"]:
            for ev in ds.evidence_for(product, claim):
                if ds.evidence_kind(ev) == "human":
                    phrase = _evidence_phrase(ev)
                    if phrase:
                        src = f"({ev['test_type']}, {ev.get('institute')})" if ev.get("institute") else f"({ev['test_type']})"
                        direction = f"보유한 {ev['test_type']} 결과({ev.get('value')}) 범위 안에서 수치와 출처를 밝혀 표현합니다."
                        return phrase, src, direction
        if reach == 2 and "기능성" in rung["needs"]:
            src = f"(기능성화장품 · {product.get('functional_type')})"
            return _first(rung["text"]), src, "심사(보고)받은 기능성 효능 표현 그대로 씁니다."
        phrase = _polish(_first(rung["text"]))
        if "N" in phrase:
            phrase = _polish(_first(ladder["rungs"][max(0, reach - 1)]["text"]))
        return phrase, "", f"실증 자료 없이 쓸 수 있는 Lv{reach} 표현으로 낮춰 씁니다."
    risky = [h for h in hits if h.kind == "risk"]
    if any(h.group not in ("exaggeration", "superlative", "compare") for h in risky):
        return None, "", "문제 표현을 빼고, 근거가 있는 효능만 남겨 다시 써야 합니다."
    cleaned = text
    for h in sorted(risky, key=lambda h: -h.start):
        cleaned = cleaned[:h.start] + cleaned[h.end:]
    cleaned = re.sub(r"\s+", " ", re.sub(r"\s*([!?.,])\s*(?=[!?.,]|$)", "", cleaned)).strip(" ,.!?·")
    if len(cleaned) < 6:
        return None, "", "근거가 확인되는 사실만 남겨 다시 씁니다."
    return cleaned, "", "근거로 확인되지 않는 표현을 덜어 내고 사실만 남깁니다."


def _next_test(claim: str | None, ladder: dict | None, hits: list[Hit], level: int) -> tuple[str | None, dict | None]:
    if ladder:
        reach = ladder["reachable"]
        nxt = next((r for r in ladder["rungs"] if r["lv"] == reach + 1), None)
        if nxt is not None:
            phrase = nxt["text"].replace(" / ", " · ")
            need = nxt["needs"].replace("/", "·")
            return f"'{phrase}' 표현을 쓰려면 {need}{iga(need)} 필요합니다.", {"phrase": phrase, "need": need, "rung": nxt["lv"]}
        if claim == "보습":
            need = "지속 시간을 측정한 인체적용시험 보고서 + 시험 대상·조건 표기"
            return f"보습 지속 시간(24시간) 표현을 쓰려면 {need}{iga(need)} 필요합니다.", {"phrase": "24시간 보습", "need": need, "rung": 2}
    if level == 1:
        groups = {h.group for h in hits if h.kind == "risk"}
        if "compare" in groups:
            return "비교 표현을 쓰려면 비교 대상·기준을 밝힌 객관적 시험 자료가 필요합니다.", None
        return "수치나 효능을 쓰려면 이를 뒷받침하는 인체적용시험 보고서 또는 시험성적서가 필요합니다.", None
    return None, None


def _alternatives(ladder: dict | None, suggestion: str | None) -> list[str]:
    if not ladder:
        return []
    out = []
    for r in sorted(ladder["rungs"], key=lambda r: -(r["lv"] if r["lv"] != "X" else -1)):
        if r["lv"] == "X" or r["lv"] > ladder["reachable"] or "인체적용시험" in r["needs"] or "시험" in r["needs"] and "기능성" not in r["needs"]:
            continue
        for part in r["text"].split(" / "):
            phrase = _polish(part)
            if "N" in phrase or phrase == suggestion or phrase in out:
                continue
            out.append(phrase)
    return out[:3]


_SUMMARY = {
    "medical": "의약품으로 오인될 수 있는 표현이 있어 이대로는 게재할 수 없습니다.",
    "doctor": "전문가 추천을 표방하는 표현이 있어 이대로는 게재할 수 없습니다.",
    "scope": "화장품의 범위를 벗어나는 표현이 있어 이대로는 게재할 수 없습니다.",
    "functional": "기능성화장품으로 오인될 수 있는 표현이 있어 이대로는 게재할 수 없습니다.",
    "superlative": "객관적으로 확인되지 않은 최상급 표현이 있어 이대로는 게재할 수 없습니다.",
    "exaggeration": "과장된 표현을 덜어 내야 쓸 수 있습니다.",
    "compare": "비교 대상과 기준을 밝힌 객관적 자료가 있어야 쓸 수 있습니다.",
    "proof": "수치·효능을 뒷받침하는 실증 자료가 있어야 쓸 수 있습니다.",
}


def _steps(status: str, level: int | None, retrieval_ms: float, llm_ms: float) -> list[dict]:
    skip = set()
    if status == "판단보류":
        skip = {"organize_evidence", "suggest_copy", "verify_copy"}
    elif level == 0:
        skip = {"suggest_copy", "verify_copy"}
    timed = {"retrieve_rules": retrieval_ms, "judge_claim": llm_ms}
    return [{"key": k, "name": n, "status": "skip" if k in skip else "done", "ms": None if k in skip else timed.get(k)}
            for k, n in PIPELINE_STEPS]


def _validate(resp: dict) -> None:
    """팀 결과 계약(schemas.ReviewResponse) 검증. 패키지가 없으면 건너뛴다."""
    try:
        from cosmetic_agent.domain.schemas import ReviewResponse
    except Exception:
        return
    ReviewResponse.model_validate({k: resp[k] for k in ("request_id", "input_text", "result", "timing")})


# ── 공개 함수 ────────────────────────────────────────────────────────
def review(copy_text: str, product: dict) -> dict:
    """광고 문구 한 개를 Mock 으로 판정한다. contract.ReviewResponse 모양 + mock=True."""
    text = (copy_text or "").strip()
    hits = detect(text, product)
    risks = [h for h in hits if h.kind == "risk"]
    claim = (ds.detect_claim(text, product) or ds.claim_of_product(product)
             or ds.detect_claim(product.get("name", ""), product)
             or next((ds.evidence_claim(ev, product) for ev in product.get("owned_evidence") or []
                      if ds.evidence_claim(ev, product)), None))
    ladder = ds.ladder_for(claim, product)
    novel = re.search(_NOVEL, text)

    if not risks and novel:
        status, level = "판단보류", None
    else:
        status, level = "판정", max((h.level or 0 for h in risks), default=0)
    decisive = next((h for h in risks if h.decisive), None)
    citations = _assemble_citations(hits) if level else []

    suggestion = src = direction = None
    next_text, next_ui = None, None
    if status == "판정" and level:
        suggestion, src, direction = _suggestion(claim, ladder, product, text, hits)
        next_text, next_ui = _next_test(claim, ladder, hits, level)

    if ladder:
        if decisive and decisive.level == 2 and decisive.group in ("medical", "scope", "doctor"):
            original = "X"
        elif re.search(r"\d|지속", text):
            original = 2
        elif "도움" in text:
            original = 1
        else:
            original = 0
        ladder = {**ladder, "original": original, "proposal": ladder["reachable"] if suggestion else None}

    if status == "판단보류":
        summary = "근거 조항을 충분히 찾지 못했습니다. 전문가 검토가 필요합니다."
        notes = "신뢰할 수 있는 법령 근거를 찾지 못하여 RA 전문가 검토가 필요합니다."
    elif not level:
        summary = "그대로 써도 됩니다."
        notes = "위반 소지가 있는 표현을 찾지 못했습니다."
    else:
        summary = _SUMMARY.get(decisive.group, _SUMMARY["medical"]) if decisive else ""
        notes = f"'{decisive.text}' — {decisive.reason}" if decisive else None

    seed = int(hashlib.sha1(f"{text}|{product.get('product_id')}|{len(product.get('owned_evidence') or [])}".encode()).hexdigest()[:8], 16)
    retrieval_ms = float(260 + min(len(text), 120) * 3 + seed % 90)
    llm_ms = float(820 + min(len(text), 120) * 11 + seed % 240)
    total_ms = retrieval_ms + llm_ms + 110 + (seed % 60)

    diff = []
    if suggestion:
        for h in risks:
            why = "실증 없는 수치 삭제" if h.group == "proof" else f"{h.label} 삭제"
            diff.append({"op": "-", "text": h.text, "why": why})
        if src:
            diff.append({"op": "+", "text": src.strip("()"), "why": "실증 출처 표기"})
        else:
            diff.append({"op": "+", "text": suggestion, "why": "근거 범위 안의 표현으로 교체"})

    reverify = None
    if suggestion:
        nums = _numbers_in(suggestion)
        values = [_flat(ev.get("value") or "") for ev in (product.get("owned_evidence") or [])]
        ok = sum(1 for n in nums if any(n in v for v in values))
        banned = sum(1 for h in detect(suggestion, product) if h.kind == "risk" and h.level == 2)
        reverify = {"numbers_ok": ok, "numbers_total": len(nums), "banned": banned}

    ui = {
        "summary": summary,
        "highlights": [
            {"start": h.start, "end": h.end, "text": h.text, "kind": h.kind, "label": h.label, "reason": h.reason,
             "violation_type": h.violation, "level": h.level, "decisive": h.decisive, "cites": h.cites}
            for h in hits
        ],
        "steps": _steps(status, level, retrieval_ms, llm_ms),
    }
    if ladder:
        ui["ladder"] = ladder
    if suggestion:
        ui.update(diff=diff, reverify=reverify, suggestion_source=src or "", direction=direction,
                  alternatives=_alternatives(ladder, suggestion))
    elif level == 0 and ladder:
        ui["alternatives"] = _alternatives(ladder, None)
    if next_ui:
        ui["next_test"] = next_ui

    resp = {
        "request_id": f"MOCK_{seed:08x}",
        "input_text": text,
        "result": {
            "status": status,
            "level": level,
            "violation_type": decisive.violation if decisive else "없음",
            "claim_type": claim,
            "citations": citations,
            "suggestion": suggestion,
            "next_test": next_text,
            "review_notes": notes,
        },
        "timing": {"retrieval_ms": retrieval_ms, "llm_ms": llm_ms, "total_ms": total_ms},
        "ui": ui,
        "mock": True,
    }
    _validate(resp)
    return resp


@lru_cache(maxsize=1)
def _df() -> tuple[dict[str, int], int]:
    """검색어 가중치용: 낱말이 나오는 청크 수 (자주 나오는 낱말일수록 점수를 덜 준다)."""
    return {}, len(ds.search_chunks())


def search(query: str, scope: str = "공통", limit: int = 8) -> list[dict]:
    """Mock 조항 검색 — 검색어 일치(드문 낱말일수록 가중) + 붙여 쓴 구절 일치 + 권위 가중. /search 응답 모양."""
    terms = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    if not terms:
        return []
    chunks = ds.search_chunks()
    df_cache, total = _df()
    flat_terms = [_flat(t) for t in terms]
    for ft in flat_terms:
        if ft not in df_cache:
            df_cache[ft] = sum(1 for c in chunks if ft in c["_norm"])
    phrase = _flat(query)
    weight = {1: 1.3, 2: 1.2, 3: 1.1, 4: 1.0}
    scored = []
    for c in chunks:
        if scope not in ("공통", None) and c["product_scope"] not in ("공통", scope):
            continue
        matched = [t for t, ft in zip(terms, flat_terms) if ft and ft in c["_norm"]]
        if not matched:
            continue
        score = 0.0
        for t, ft in zip(terms, flat_terms):
            n = c["_norm"].count(ft)
            if n:
                idf = math.log(1 + total / (1 + df_cache[ft]))
                score += (1 + math.log(n)) * idf
        if len(terms) > 1 and phrase in c["_norm"]:
            score *= 1.8
        score *= weight.get(c["authority"], 1.0)
        scored.append((score, c, matched))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, c, matched in scored[:limit]:
        out.append({
            "content": ds.strip_revisions(c["content"]),
            "metadata": {"id": c["id"], "source": c["source"], "doc_type": c["doc_type"], "authority": c["authority"],
                         "article": c["article"], "product_scope": c["product_scope"],
                         "effective_date": c["effective_date"], "matched_terms": matched, "score": round(score, 3)},
        })
    return out
