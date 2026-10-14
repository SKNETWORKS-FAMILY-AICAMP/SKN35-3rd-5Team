"""
[app/services/data_sources.py]
저장소 data/ 의 규칙 자산·원문(법령·고시·지침·사례)을 읽어 화면과 Mock 이 쓰는 모양으로 정리한다.
반환값은 캐시된 원본이다. 고치지 말고 읽기만 한다.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── 경로 ──────────────────────────────────────────────────────────────
def _settings() -> Any:
    try:
        from cosmetic_agent.common.config import settings

        return settings
    except Exception:
        return None


def project_root() -> Path:
    s = _settings()
    return Path(s.PROJECT_ROOT_PATH) if s is not None else REPO_ROOT


def raw_dir() -> Path:
    return project_root() / "data" / "01_raw"


def _settings_path(name: str, fallback: str) -> Path:
    """settings 의 자산 경로를 쓰고, 설정을 못 읽으면 저장소 루트 기준 상대경로로 대신한다."""
    s = _settings()
    return Path(getattr(s, name)) if s is not None else REPO_ROOT / fallback


def rel(path: Path) -> str:
    """저장소 루트 기준 상대경로(화면 표시용)."""
    try:
        return path.resolve().relative_to(project_root().resolve()).as_posix()
    except ValueError:
        return path.name


# ── 규칙 자산 (data/assets/*.json 그대로) ─────────────────────────────
@lru_cache(maxsize=None)
def _load_json(path_key: str, fallback: str) -> Any:
    with open(_settings_path(path_key, fallback), encoding="utf-8") as f:
        return json.load(f)


def mock_products() -> list[dict]:
    original = _load_json("MOCK_PRODUCTS_PATH", "data/assets/mock_products.json")
    public_path = REPO_ROOT / "data" / "assets" / "public_analysis_products.json"
    public = json.loads(public_path.read_text(encoding="utf-8")) if public_path.exists() else []
    # 제형·기능성 유형별 예시 제품(골든셋 v2 개발용 제품 카드, holdout2 제품은 넣지 않음)
    sample_path = REPO_ROOT / "data" / "assets" / "sample_products.json"
    samples = json.loads(sample_path.read_text(encoding="utf-8")) if sample_path.exists() else []
    # 기본 선택(첫 제품)은 시연 시나리오의 자사 샘플(하이드라 워터 크림)로 두고, 예시·공개 분석 샘플은 뒤에 붙인다
    return original + samples + public


def banned_terms() -> list[dict]:
    return _load_json("BANNED_TERMS_PATH", "data/assets/banned_terms.json")


def claim_ladders() -> list[dict]:
    return _load_json("CLAIM_LADDER_PATH", "data/assets/claim_ladder.json")


def functional_claims() -> list[dict]:
    return _load_json("FUNCTIONAL_CLAIMS_PATH", "data/assets/functional_claims.json")


def term_map() -> dict[str, str]:
    return _load_json("TERM_MAP_PATH", "data/assets/term_map.json")


# ── 효능 분류 ─────────────────────────────────────────────────────────
# 효능 분류 → 감지 낱말. 동점이면 제품 기능성 → 먼저 나온 분류 순으로 고른다.
CLAIM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "보습": ("보습", "수분", "촉촉", "건조"),
    "진정": ("진정", "자극", "붉은", "붉어"),
    "탈모": ("탈모", "모발", "두피", "발모", "육모", "양모"),
    "주름": ("주름", "탄력"),
    "미백": ("미백", "기미", "잡티", "주근깨", "톤"),
    "여드름": ("여드름", "트러블", "피지"),
}

# 기능성 유형(functional_claims.json 의 type) ↔ 효능 분류
FUNCTIONAL_TO_CLAIM: dict[str, str] = {
    "탈모 증상 완화": "탈모",
    "여드름성 피부 완화": "여드름",
    "주름 개선": "주름",
    "피부 미백": "미백",
}
CLAIM_TO_FUNCTIONAL: dict[str, str] = {v: k for k, v in FUNCTIONAL_TO_CLAIM.items()}


def claim_of_product(product: dict | None) -> str | None:
    """기능성 제품이면 그 기능성 효능 분류, 아니면 None."""
    if not product or product.get("category") != "기능성":
        return None
    return FUNCTIONAL_TO_CLAIM.get(product.get("functional_type") or "")


def detect_claim(text: str, product: dict | None = None) -> str | None:
    """문장에서 효능 분류를 고른다. 낱말 일치 수가 많은 분류, 동점이면 제품 기능성 → 먼저 나온 분류."""
    scores: dict[str, tuple[int, int]] = {}
    for claim, words in CLAIM_KEYWORDS.items():
        positions = [m.start() for w in words for m in re.finditer(re.escape(w), text)]
        if positions:
            scores[claim] = (len(positions), min(positions))
    if not scores:
        return None
    own = claim_of_product(product)
    return max(scores, key=lambda c: (scores[c][0], c == own, -scores[c][1]))


# ── 실증 자료 분류 ────────────────────────────────────────────────────
_SURVEY = re.compile(r"만족도|설문|선호도|사용감|소비자\s*평가")
_IRRITATION = re.compile(r"자극|패치")


def evidence_text(ev: dict) -> str:
    return " ".join(str(ev.get(k) or "") for k in ("test_type", "item", "value", "institute"))


def evidence_kind(ev: dict) -> str:
    """survey(만족도·설문) · human(인체적용시험) · irritation(자극 시험) · basic(그 밖의 시험·성적서)."""
    if _SURVEY.search(evidence_text(ev)):
        return "survey"
    test_type = str(ev.get("test_type") or "")
    if "인체적용" in test_type or "인체 적용" in test_type or "임상" in test_type:
        return "human"
    if _IRRITATION.search(f"{test_type} {ev.get('item') or ''}"):
        return "irritation"
    return "basic"


def evidence_claim(ev: dict, product: dict | None = None) -> str | None:
    """실증 자료가 뒷받침하는 효능 분류. 항목·결과에서 못 찾으면 기능성 제품의 효능 분류."""
    found = detect_claim(f"{ev.get('item') or ''} {ev.get('value') or ''}", product)
    return found or claim_of_product(product)


def evidence_for(product: dict | None, claim: str | None) -> list[dict]:
    """제품의 (체크된) 실증 중 이 효능 분류를 뒷받침하는 것."""
    owned = (product or {}).get("owned_evidence") or []
    return [ev for ev in owned if claim and evidence_claim(ev, product) == claim]


# ── 표현 사다리 ───────────────────────────────────────────────────────
# claim_ladder.json 에 없는 효능(기능성 4종)의 Lv0~1 예시 표현. Lv2 = 기능성 심사 효능 표현(ceiling), X = banned.
_FUNCTIONAL_LOWER: dict[str, list[tuple[str, str]]] = {
    "탈모": [("두피·모발을 깨끗하게 세정", "근거 불필요"), ("건강한 두피·모발 관리에 도움", "성분·제형 근거")],
    "여드름": [("피부 노폐물을 말끔하게 세정", "근거 불필요"), ("피지·각질 정돈에 도움", "성분·제형 근거")],
    "주름": [("생기 있는 피부로 가꿔줌", "근거 불필요"), ("피부 탄력 관리에 도움", "성분·제형 근거")],
    "미백": [("맑고 화사한 피부로 가꿔줌", "근거 불필요"), ("칙칙한 피부 톤을 정돈", "성분·제형 근거")],
}


def functional_entry(claim: str | None) -> dict | None:
    """효능 분류에 해당하는 functional_claims.json 항목."""
    ftype = CLAIM_TO_FUNCTIONAL.get(claim or "")
    return next((f for f in functional_claims() if f["type"] == ftype), None)


def _ladder_template(claim: str) -> list[dict] | None:
    """사다리 칸 정의(owned 없음). 낮은 칸 → 높은 칸 → 불가 칸."""
    for entry in claim_ladders():
        if entry["claim"] == claim:
            return [{"lv": "X" if lv["lv"] == 9 else lv["lv"], "text": lv["text"], "needs": lv["needs"]}
                    for lv in entry["levels"]]
    fc = functional_entry(claim)
    if fc is None:
        return None
    lower = _FUNCTIONAL_LOWER[claim]
    return [
        {"lv": 0, "text": lower[0][0], "needs": lower[0][1]},
        {"lv": 1, "text": lower[1][0], "needs": lower[1][1]},
        {"lv": 2, "text": fc["ceiling"], "needs": f"{fc['type']} 기능성화장품 심사(보고)"},
        {"lv": "X", "text": " / ".join(fc["banned"][:3]), "needs": "불가 (의약품 오인 또는 기능성 범위 이탈)"},
    ]


def _rung_owned(needs: str, claim: str, product: dict | None) -> bool:
    """칸의 '필요한 근거' 문구로 지금 체크한 실증이 그 칸을 충족하는지 판단한다."""
    if "불가" in needs:
        return False
    if "기능성" in needs:
        return claim_of_product(product) == claim
    kinds = {evidence_kind(ev) for ev in evidence_for(product, claim)}
    if "자극" in needs and "irritation" in kinds:
        return True
    if "인체적용시험" in needs:
        return "human" in kinds
    return True   # 근거 불필요 · 성분·제형 기본 근거 (제품 처방으로 갖춘 것으로 본다)


def ladder_for(claim: str | None, product: dict | None) -> dict | None:
    """효능 분류의 사다리와 보유 실증으로 갈 수 있는 최고 칸. 사다리가 없는 분류면 None."""
    template = _ladder_template(claim) if claim else None
    if template is None:
        return None
    rungs = [{**r, "owned": _rung_owned(r["needs"], claim, product)} for r in template]
    reachable = 0
    for rung in rungs:   # 아래 칸부터 끊김 없이 이어진 칸까지만 도달로 본다
        if rung["lv"] == "X" or not rung["owned"]:
            break
        reachable = rung["lv"]
    return {"claim": claim, "rungs": rungs, "reachable": reachable}


# ── 글자 정리 ─────────────────────────────────────────────────────────
_SPACES = re.compile(r"[ \t　\xa0]+")
_REVISION = re.compile(r"\s*<(?:개정|신설|전문개정|본조신설|제목개정|종전|타법개정)[^>]*>")
_BOX = re.compile(r"[─━│┃┌┐└┘├┤┬┴┼┏┓┗┛┣┫┳┻╋┝┥┿┷┯┠┨]")
_LIST_MARK = re.compile(r"^(?:\d+(?:의\d+)?\.|[가-하]\.|\d+\)|[가-하]\)|\(\d+\)|\([가-하]\)|[①-⑳]|[■□○●◇◆※▶▸·ㆍ*]|비고|주\))")
# 줄 끝·줄 머리에 홀로 와도 낱말인 한 글자(이 글자에서 끊긴 줄은 띄어 잇는다)
_ONE_SYLLABLE_WORDS = frozenset("및 등 그 각 수 것 때 중 외 위 데 바 이 또 즉 단".split())


def strip_revisions(text: str) -> str:
    """'<개정 2018.3.13>' 같은 개정 표시를 지운다."""
    return _REVISION.sub("", text).strip()


def one_line(text: str) -> str:
    return _SPACES.sub(" ", " ".join(text.split())).strip()


def _join_wrapped(prev: str, nxt: str) -> str:
    """고정폭 줄바꿈으로 끊긴 두 줄을 잇는다. 낱말 중간에서 끊긴 줄은 붙이고, 어절 경계면 띄운다."""
    if prev.endswith(("ㆍ", "·", "(", "「", "“", "‘")) or nxt.startswith(("ㆍ", "·", ")", ",", ".", "」", "”", "’")):
        return prev + nxt
    last = re.split(r"[\sㆍ·\"“‘'(「]", prev)[-1]
    first = re.split(r"[\s,.)」”’]", nxt)[0]
    if re.fullmatch(r"[가-힣]", last) and last not in _ONE_SYLLABLE_WORDS:
        return prev + nxt
    if re.fullmatch(r"[가-힣]", first) and first not in _ONE_SYLLABLE_WORDS:
        return prev + nxt
    if re.search(r"\d$", prev) and re.match(r"(?:조|항|호|목|의\d)", nxt):
        return prev + nxt
    return f"{prev} {nxt}"


def unwrap_fixed_width(text: str) -> str:
    """법령 별표 본문(고정폭 줄바꿈)을 논리 줄로 다시 잇는다. 괘선 표 줄은 그대로 둔다."""
    physical = text.split("\n\n\n") if "\n\n\n" in text else text.split("\n")
    out: list[str] = []
    for raw in physical:
        line = raw.strip()
        if not line:
            if out and out[-1]:
                out.append("")
            continue
        joinable = (out and out[-1] and not out[-1].startswith("■") and not _LIST_MARK.match(line)
                    and not _BOX.search(line) and not _BOX.search(out[-1]))
        if joinable:
            out[-1] = _join_wrapped(out[-1], line)
        else:
            out.append(line if not _BOX.search(line) else raw.rstrip())
    return "\n".join(line for line in out if line)


def _tidy_block(text: str) -> str:
    """고시 본문·별표: 엔티티를 풀고 빈 줄을 지운다. 괘선 표 줄은 오른쪽 공백만 지운다."""
    lines = []
    for raw in html.unescape(text).splitlines():
        if not raw.strip():
            continue
        lines.append(raw.rstrip() if _BOX.search(raw) else raw.strip())
    return "\n".join(lines)


# ── 법령·고시 (data/01_raw/law/*.xml) ─────────────────────────────────
_ART_HEAD = re.compile(r"^제(\d+)조(?:의(\d+))?(?:\s*\(((?:[^()\n]|\([^()\n]*\))*)\))?\s*")
_ART_SPLIT = re.compile(r"(?m)^제\d+조(?:의\d+)?(?:\s*\((?:[^()\n]|\([^()\n]*\))*\))?")
_CHAPTER = re.compile(r"^제\d+장\s*\S")
_DOC_ORDER = ("화장품법", "화장품법_시행규칙", "표시광고_실증규정", "기능성화장품_심사규정", "화장품_안전기준규정")


def _txt(el: ET.Element, tag: str) -> str:
    return (el.findtext(tag) or "").strip()


def _date(yyyymmdd: str) -> str | None:
    d = re.sub(r"\D", "", yyyymmdd or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None


def _readme_rows() -> dict[str, list[str]]:
    """data/01_raw/README.md 수집 목록 표: 파일 경로 → [문서, 버전, 출처, 이용 조건]."""
    path = raw_dir() / "README.md"
    rows: dict[str, list[str]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = cells[1:5]
    return rows


def _law_article(unit: ET.Element) -> dict:
    """법령(lawService) 조문단위 하나 → {no, title, text, deleted}. 항·호·목을 들여쓰기로 정리한다."""
    head = _txt(unit, "조문내용")
    branch = _txt(unit, "조문가지번호")
    no = f"제{int(_txt(unit, '조문번호'))}조" + (f"의{int(branch)}" if branch.isdigit() and int(branch) else "")
    lines = [_ART_HEAD.sub("", head, count=1).strip()]
    for para in unit.findall("항"):
        lines.append(_txt(para, "항내용"))
        for item in para.findall("호"):
            lines.append("  " + _txt(item, "호내용"))
            lines.extend("    " + _txt(sub, "목내용") for sub in item.findall("목"))
    deleted = bool(re.match(r"^제\d+조(?:의\d+)?\s*삭제", head))
    title = _txt(unit, "조문제목") or ("삭제" if deleted else "")
    return {"no": no, "title": title, "text": "\n".join(l for l in lines if l.strip()), "deleted": deleted}


def _law_service_doc(root: ET.Element) -> dict:
    info = root.find("기본정보")
    kind_name = _txt(info, "법종구분")
    articles, chapter = [], None
    for unit in root.find("조문").findall("조문단위"):
        if _txt(unit, "조문여부") == "전문":
            chapter = one_line(_txt(unit, "조문내용"))
            continue
        articles.append({**_law_article(unit), "chapter": chapter})
    annexes = []
    holder = root.find("별표")
    for unit in holder.findall("별표단위") if holder is not None else []:
        if _txt(unit, "별표구분") != "별표":
            continue   # 서식은 판정에 쓰지 않는다
        no, branch = int(_txt(unit, "별표번호") or 0), int(_txt(unit, "별표가지번호") or 0)
        title = html.unescape(_txt(unit, "별표제목"))
        annexes.append({
            "no": f"{no}" + (f"의{branch}" if branch else ""),
            "title": title,
            "text": unwrap_fixed_width(html.unescape(unit.findtext("별표내용") or "")),
            "deleted": title.startswith("삭제"),
        })
    return {
        "title": _txt(info, "법령명_한글"),
        "kind": "법령",
        "authority": 1,
        "version": f"{kind_name} 제{int(_txt(info, '공포번호') or 0)}호",
        "promulgated": _date(_txt(info, "공포일자")),
        "effective_date": _date(_txt(info, "시행일자")),
        "articles": articles,
        "annexes": annexes,
    }


def _admrul_doc(root: ET.Element) -> dict:
    info = root.find("행정규칙기본정보")
    articles, chapter = [], None
    for el in root.findall("조문내용"):
        text = (el.text or "").strip()
        if _CHAPTER.match(text):
            chapter = one_line(text)
            continue
        starts = list(_ART_SPLIT.finditer(text))
        for i, start in enumerate(starts):
            block = text[start.start(): starts[i + 1].start() if i + 1 < len(starts) else len(text)].rstrip()
            head = _ART_HEAD.match(block)
            body = "\n".join(line.rstrip() for line in block[head.end():].splitlines()).strip("\n")
            deleted = body.strip().startswith("삭제")
            articles.append({
                "no": f"제{int(head.group(1))}조" + (f"의{int(head.group(2))}" if head.group(2) else ""),
                "title": (head.group(3) or "").strip() or ("삭제" if deleted else ""),
                "text": html.unescape(body),
                "deleted": deleted,
                "chapter": chapter,
            })
    annexes = []
    holder = root.find("별표")
    for unit in holder.findall("별표단위") if holder is not None else []:
        body = unit.findtext("별표내용") or ""
        if not body.strip():
            continue
        no = int(_txt(unit, "별표번호") or 0)
        annexes.append({
            "no": str(no) if no else "",
            "title": html.unescape(_txt(unit, "별표제목")),
            "text": _tidy_block(body),
            "deleted": False,
        })
    rule_kind = _txt(info, "행정규칙종류") or "고시"
    return {
        "title": _txt(info, "행정규칙명"),
        "kind": rule_kind,
        "authority": 2,
        "version": f"식약처 {rule_kind} 제{_txt(info, '발령번호')}호",
        "promulgated": _date(_txt(info, "발령일자")),
        "effective_date": _date(_txt(info, "시행일자")),
        "articles": articles,
        "annexes": annexes,
    }


@lru_cache(maxsize=1)
def law_documents() -> list[dict]:
    """법령·고시 XML 전부. [{key, short, title, kind, authority, version, effective_date, articles, annexes, ...}]"""
    readme = _readme_rows()
    docs = []
    for path in sorted((raw_dir() / "law").glob("*.xml")):
        root = ET.parse(path).getroot()
        doc = _law_service_doc(root) if root.tag == "법령" else _admrul_doc(root)
        row = readme.get(f"law/{path.name}", [])
        doc.update({
            "key": path.stem,
            "short": path.stem.split("_")[-1],            # chunk id 에 쓰는 약칭 (화장품법 · 시행규칙 · 실증규정 …)
            "prefix": "LAW" if doc["kind"] == "법령" else "NOTICE",
            "file": rel(path),
            "source": row[2] if len(row) > 2 else "국가법령정보센터",
            "license": row[3] if len(row) > 3 else None,
            "readme_version": row[1] if len(row) > 1 else None,
        })
        docs.append(doc)
    order = {k: i for i, k in enumerate(_DOC_ORDER)}
    return sorted(docs, key=lambda d: (d["authority"], order.get(d["key"], 99), d["key"]))


def law_document(key_or_short: str) -> dict | None:
    """파일 이름(화장품법_시행규칙) 또는 약칭(시행규칙)으로 문서 하나."""
    return next((d for d in law_documents() if key_or_short in (d["key"], d["short"], d["title"])), None)


def law_article(doc_key: str, no: str) -> dict | None:
    doc = law_document(doc_key)
    return next((a for a in doc["articles"] if a["no"] == no), None) if doc else None


def law_annex(doc_key: str, no: str) -> dict | None:
    doc = law_document(doc_key)
    return next((a for a in doc["annexes"] if a["no"] == no), None) if doc else None


def _block(lines: list[str], start_mark: str, stop: re.Pattern) -> list[str]:
    """start_mark 로 시작하는 줄부터 stop 패턴 줄 직전까지."""
    begin = next((i for i, line in enumerate(lines) if line.startswith(start_mark)), None)
    if begin is None:
        return []
    end = next((i for i in range(begin + 1, len(lines)) if stop.match(lines[i])), len(lines))
    return lines[begin:end]


_PARA_MARK = re.compile(r"^[①-⑳]")
_ITEM_MARK = re.compile(r"^\d+(?:의\d+)?\.")
_SUB_MARK = re.compile(r"^[가-하]\.")


def article_excerpt(doc_key: str, no: str, para: str | None = None, items: tuple[str, ...] = (),
                    examples: int = 0) -> str:
    """조문 발췌. para='③', items=('1.', '4.') 처럼 고른다. examples 는 남길 (예시) 줄 수."""
    art = law_article(doc_key, no)
    if not art:
        return ""
    lines = [line.strip() for line in art["text"].splitlines() if line.strip()]
    if para:
        lines = _block(lines, para, _PARA_MARK)
    if items:
        head = [line for line in lines[:1] if not _ITEM_MARK.match(line)]
        picked = [line for mark in items for line in _block(lines, mark, re.compile(r"^(?:\d+(?:의\d+)?\.|[①-⑳])"))]
        lines = head + picked
    kept, seen_examples = [], 0
    for line in lines:
        if line.startswith("(예시)") or line.startswith("·"):
            if line.startswith("(예시)"):
                seen_examples += 1
            if seen_examples > examples or (line.startswith("·") and seen_examples == 0):
                continue
        kept.append(line)
    text = " ".join(strip_revisions(line) for line in kept)
    return re.sub(r"^[①-⑳]\s*", "", one_line(text))


def annex_excerpt(doc_key: str, annex_no: str, ho: str, mok: str | None = None) -> str:
    """별표 발췌. 예) annex_excerpt('시행규칙', '5', '2', '가') → 별표 5 제2호 가목 본문."""
    annex = law_annex(doc_key, annex_no)
    if not annex:
        return ""
    lines = annex["text"].splitlines()
    block = _block(lines, f"{ho}.", re.compile(r"^\d+\."))
    if mok:
        block = _block(block[1:], f"{mok}.", _SUB_MARK)
    text = one_line(" ".join(block))
    return re.sub(r"^(?:\d+|[가-하])\.\s*", "", text)


# ── 표시·광고 관리 지침 (data/01_raw/guide) ───────────────────────────
_PAGE = re.compile(r"<!-- page (\d+) -->")
_PAGE_NO_LINE = re.compile(r"^\s*-\s*\d+\s*-\s*$")
_GUIDE_TABLE_HEAD = frozenset({"구 분", "금 지 표 현", "비 고", "구분", "금지표현", "비고"})
_GUIDE_NOTE = re.compile(r"^(?:단,|\*|<예시>|․|※|- )")
_GUIDE_ITEM = re.compile(r"^(.*?)·\s+(\S.*)$")
# [별표 1] '구 분' 칸 이름(줄바꿈이 섞여 나와 공백을 지운 형태로 대조한다). 같은 줄에 '피부 관련 표현· …' 처럼
# 붙어 나오는 구분은 줄에서 바로 읽고, 따로 떨어져 나오는 구분만 여기서 알아본다.
_GUIDE_CATEGORIES = frozenset({
    "질병을진단·치료·경감·처치또는예방,의학적효능·효과관련", "생리활성관련", "기타", "기능성관련표현",
    "천연·유기농화장품관련", "특정인또는기관의지정,공인관련", "화장품의범위를벗어나는광고",
    "인체유래성분관련표현", "저속하거나혐오감을줄수있는표현", "사실과다르거나소비자가사실로오인할수있는표현",
    "그밖의기타표현",
})


def _guide_path() -> Path:
    files = sorted((raw_dir() / "guide").glob("*.txt"))
    return files[0]


@lru_cache(maxsize=1)
def _guide_raw_pages() -> list[tuple[int, list[str]]]:
    """[(쪽 번호, 원문 줄(오른쪽 공백 보존))]."""
    parts = _PAGE.split(_guide_path().read_text(encoding="utf-8"))
    pages = []
    for i in range(1, len(parts), 2):
        lines = [line for line in parts[i + 1].split("\n") if line.strip() and not _PAGE_NO_LINE.match(line)]
        pages.append((int(parts[i]), lines))
    return pages


def _join_pdf(prev_raw: str, nxt: str) -> str:
    """PDF 에서 뽑은 줄 잇기: 앞 줄 끝에 공백이 있었으면 띄우고, 한글 사이에서 끊겼으면 붙인다."""
    prev = prev_raw.rstrip()
    if prev_raw.endswith(" "):
        return f"{prev} {nxt.strip()}"
    if prev.endswith(("(", "‘", "“", "「", "·", "‧")) or (re.search(r"[가-힣]$", prev) and re.match(r"[가-힣]", nxt)):
        return prev + nxt.strip()
    return f"{prev} {nxt.strip()}"


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _annex_ranges(pages: list[tuple[int, list[str]]]) -> list[dict]:
    """지침 [별표 N] 의 시작 쪽·제목·쪽 범위·절(□ …관련)."""
    starts = []
    for no, lines in pages:
        for i, line in enumerate(lines):
            m = re.fullmatch(r"\s*\[별표\s*(\d+)\]\s*", line)
            if m:
                starts.append({"no": m.group(1), "start": no, "title": one_line(lines[i + 1]) if i + 1 < len(lines) else ""})
    colophon = next((no for no, lines in pages if any("편집위원" in line for line in lines)), pages[-1][0] + 1)
    out = []
    for i, s in enumerate(starts):
        end = starts[i + 1]["start"] - 1 if i + 1 < len(starts) else colophon - 1
        sections = []
        for no, lines in pages:
            if s["start"] <= no <= end:
                for line in lines:
                    if line.strip().startswith("□"):
                        sections.append({"title": one_line(line.strip().lstrip("□")), "pages": [no]})
                    elif sections and no not in sections[-1]["pages"]:
                        sections[-1]["pages"].append(no)
        out.append({"no": s["no"], "title": s["title"], "pages": list(range(s["start"], end + 1)), "sections": sections})
    return out


def _cat_pdf(acc: str, raw: str) -> str:
    """누적한 글자에 PDF 줄 하나를 잇는다. 줄 끝 공백(다음 줄과 띄어 쓴다는 표시)은 남겨 둔다."""
    if not acc:
        return raw.strip() + (" " if raw.endswith(" ") else "")
    return _join_pdf(acc, raw) + (" " if raw.endswith(" ") else "")


def _item_done(text: str) -> bool:
    """금지 표현 칸이 끝났는지: 문장('…한다.')이나 '…표현'으로 끝나면 끝난 것으로 본다."""
    tail = text.rstrip()
    return tail.endswith(".") or tail.endswith("표현")


@lru_cache(maxsize=1)
def guide_rows() -> list[dict]:
    """관리지침 [별표 1] 금지 표현 표의 행. [{section, category, text, note, page}] — 원문 줄을 다시 이어 만든다.

    PDF 에서 뽑은 표는 '구분 · 금지 표현 · 비고' 세 칸이 한 줄씩 섞여 나온다.
    - '· ' 로 시작하는 줄이 새 금지 표현 행이다('피부 관련 표현· …' 처럼 구분이 앞에 붙기도 한다).
    - 따로 떨어져 나온 구분 이름은 새 행 직전의 미결 줄 끝부분으로 알아본다(앞 행의 비고 줄과 섞여 나와도).
    - 금지 표현이 문장이나 '…표현'으로 끝난 뒤의 줄은 비고로 본다. 단, 표현이 덜 끝난 채 쪽이 넘어가면
      새 쪽 첫 줄은 금지 표현에 잇는다.
    """
    pages = _guide_raw_pages()
    annex1 = next((a for a in _annex_ranges(pages) if a["no"] == "1"), None)
    if annex1 is None:
        return []
    rows: list[dict] = []
    state: dict[str, Any] = {"section": None, "category": None, "cur": None, "mode": None}
    pending: list[tuple[str, bool]] = []      # (원문 줄, 쪽 첫 줄 여부)

    def attach(raw: str, page_first: bool) -> None:
        cur = state["cur"]
        if cur is None:
            return
        if state["mode"] == "note" and page_first and not _item_done(cur["text"]):
            cur["text"] = _cat_pdf(cur["text"], raw)       # 쪽을 넘어 이어진 금지 표현
        elif state["mode"] == "item" and _item_done(cur["text"]):
            state["mode"] = "note"
            cur["notes"].append(_cat_pdf("", raw))
        elif state["mode"] == "note" and cur["notes"]:
            cur["notes"][-1] = _cat_pdf(cur["notes"][-1], raw)
        else:
            cur["text"] = _cat_pdf(cur["text"], raw)

    def resolve(is_item_start: bool) -> None:
        if not pending:
            return
        split = len(pending)
        if is_item_start:      # 미결 줄의 끝부분이 구분 이름이면 떼어 낸다
            split = next((i for i in range(len(pending))
                          if _norm("".join(raw for raw, _ in pending[i:])) in _GUIDE_CATEGORIES), len(pending))
        for raw, page_first in pending[:split]:
            attach(raw, page_first)
        if split < len(pending):
            joined = ""       # 구분 칸은 낱말 경계에서 줄이 바뀐다('진단·'처럼 가운뎃점으로 끝난 줄만 붙인다)
            for raw, _ in pending[split:]:
                glue = "" if not joined or joined.endswith(("·", "(")) else " "
                joined = joined + glue + raw.strip()
            state["category"] = joined
        pending.clear()

    for page_no, lines in pages:
        if page_no not in annex1["pages"]:
            continue
        page_first = True
        for raw in lines:
            line = raw.strip()
            if line in _GUIDE_TABLE_HEAD or line.startswith("[별표") or line == annex1["title"]:
                continue
            if line.startswith("□"):
                resolve(False)
                state.update(section=one_line(line.lstrip("□")), category=None, cur=None, mode=None)
                page_first = False
                continue
            if _GUIDE_NOTE.match(line):
                resolve(False)
                if state["cur"] is not None:
                    state["cur"]["notes"].append(_cat_pdf("", raw))
                    state["mode"] = "note"
                page_first = False
                continue
            m = _GUIDE_ITEM.match(line)
            if m:
                resolve(True)
                if m.group(1).strip():
                    state["category"] = m.group(1).strip()
                text = m.group(2) + (" " if raw.endswith(" ") else "")
                state["cur"] = {"section": state["section"], "category": state["category"], "text": text,
                                "notes": [], "page": page_no}
                rows.append(state["cur"])
                state["mode"] = "item"
                page_first = False
                continue
            pending.append((raw, page_first))
            page_first = False
    resolve(False)
    for row in rows:
        row["text"] = one_line(row["text"])
        row["note"] = one_line(" ".join(row.pop("notes"))) or None
        row["category"] = one_line(row["category"] or "")
    return rows


def find_guide_row(key: str) -> dict | None:
    """금지 표현 행을 원문 글자 일부(공백 무시)로 찾는다."""
    target = _norm(key)
    return next((r for r in guide_rows() if target in _norm(r["text"])), None)


def guide_lines(page_from: int, page_to: int) -> list[str]:
    """지침 원문 줄(정리된 한 줄씩). 실증 대상 표([별표 2]) 발췌에 쓴다."""
    return [one_line(line) for no, lines in _guide_raw_pages() if page_from <= no <= page_to for line in lines]


@lru_cache(maxsize=1)
def guide_document() -> dict:
    """관리지침 전체: 쪽 단위 본문 + 별표 범위 + 금지 표현 표 행."""
    path = _guide_path()
    pages = _guide_raw_pages()
    history = " ".join(line for no, lines in pages if no == 4 for line in lines)
    edition = (re.findall(r"안내서-\d{4}-\d{2}", history) or [None])[-1]
    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    annexes = _annex_ranges(pages)
    annex1 = next((a for a in annexes if a["no"] == "1"), {"pages": [], "title": ""})
    row = _readme_rows().get(f"guide/{path.name}", [])
    return {
        "key": "관리지침",
        "title": "화장품 표시·광고 관리 지침",
        "kind": "지침",
        "authority": 3,
        "version": f"{date_m.group(1) if date_m else ''} 개정" + (f" ({edition})" if edition else ""),
        "effective_date": date_m.group(1) if date_m else None,
        "file": rel(path),
        "source": row[2] if len(row) > 2 else "식약처 민원인안내서",
        "pages": [{"no": no, "text": "\n".join(line.rstrip() for line in lines)} for no, lines in pages],
        "annexes": annexes,
        "banned_table": {"annex": "1", "title": annex1["title"], "pages": annex1["pages"], "rows": guide_rows()},
    }


# ── 식약처 적발 사례 (data/01_raw/cases) ──────────────────────────────
_CASE_NAME = re.compile(r"^case_(\d{4}-\d{2}-\d{2})_(.+)\.txt$")
_CASE_JUNK = re.compile(r"//\s*0\)\{|이 자료는 텍스트에 한하여")


def _short_title(full: str) -> str:
    """보도자료 제목을 짧게: 기관명·출처 괄호·건수·'적발'을 뺀다."""
    t = re.sub(r"\s*\((?:식약처|정책브리핑)[^)]*\)\s*$", "", full)
    t = re.sub(r"\s*\(\d[\d,]*건\)\s*$", "", t)
    t = re.sub(r"^식약처,\s*", "", t)
    if "…" in t:
        t = t.split("…")[-1]
    t = re.sub(r"\s*(?:총\s*)?\d[\d,]*건\s*적발(?:\s*조치)?\s*$", "", t.strip())
    return re.sub(r"\s*적발(?:\s*조치)?\s*$", "", t).strip()


def _breakdown_label(phrase: str) -> str:
    if "기능성" in phrase:
        return "기능성 오인" if re.search(r"잘못\s*인식|오인", phrase) else "기능성 효능 상이"
    if "의약품" in phrase:
        return "의약품 오인"
    if "범위" in phrase:
        return "범위 이탈"
    if "소비자" in phrase:
        return "소비자 오인"
    return one_line(phrase)[:12]


def _breakdown(section: str) -> list[dict] | None:
    """'▲… 광고(53건, 64%)' · '▲… 142건(80%)' 형태의 유형 비율. 본문에 % 가 없으면 None."""
    items = []
    for chunk in section.split("▲")[1:]:
        m = re.search(r"(\d[\d,]*)건\s*[,(]\s*(\d+(?:\.\d+)?)\s*%", chunk)
        if m:
            items.append({"label": _breakdown_label(chunk[:m.start()]),
                          "pct": float(m.group(2)), "count": int(m.group(1).replace(",", ""))})
    return items or None


@lru_cache(maxsize=1)
def case_documents() -> list[dict]:
    """적발 사례 보도자료. 날짜 내림차순(최신이 앞). 숫자는 파일 이름·본문에서 읽고, 없으면 None."""
    readme = _readme_rows()
    out = []
    for path in sorted((raw_dir() / "cases").glob("case_*.txt")):
        m = _CASE_NAME.match(path.name)
        if not m:
            continue
        raw = path.read_text(encoding="utf-8")
        header = [line[2:].strip() for line in raw.splitlines() if line.startswith("# ")]
        body = "\n".join(line for line in raw.splitlines() if not line.startswith("# "))
        junk = _CASE_JUNK.search(body)
        body = "\n".join(l.rstrip() for l in body[: junk.start() if junk else None].splitlines()
                         if l.strip() and not _PAGE_NO_LINE.match(l))
        source_url = next((h.split(":", 1)[1].strip() for h in header if h.startswith("출처:")), None)
        heading = next((h for h in header if not re.match(r"^(?:출처|이용 조건):", h)), None)
        readme_row = readme.get(f"cases/{path.name}", [])
        full_title = re.sub(r"\s+-\s+[^-]*\|.*$", "", heading) if heading else (readme_row[0] if readme_row else None)
        flat = one_line(body)
        count_m = re.search(r"_(\d[\d,]*)건", m.group(2)) or re.search(r"총\s*(\d[\d,]*)건", flat) \
            or re.search(r"(\d[\d,]*)건을\s*(?:적발|확인)", flat)
        count = int(count_m.group(1).replace(",", "")) if count_m else None
        cos_m = re.search(r"화장품\s*(?:부당광고\s*)?(\d[\d,]*)건", f"{full_title or ''} {flat}")
        cosmetics_count = int(cos_m.group(1).replace(",", "")) if cos_m else None
        mentions_cosmetics = "화장품" in f"{full_title or ''} {flat}"
        if cosmetics_count is not None and count is not None and cosmetics_count < count:
            scope = "혼합"
            section_start = flat.find(cos_m.group(0))
            nxt = re.search(r"◆|(?:의약외품|의료기기|식품)\s*(?:등\s*)?부당광고\s*\d", flat[section_start + 1:])
            section = flat[section_start: section_start + 1 + nxt.start() if nxt else None]
        elif mentions_cosmetics:
            scope, cosmetics_count, section = "화장품", count, flat
        else:
            scope, cosmetics_count, section = "화장품 외", None, ""
        out.append({
            "key": f"CASE_{m.group(1)}",
            "date": m.group(1),
            "title": _short_title(full_title) if full_title else m.group(2),
            "full_title": full_title,
            "count": count,
            "cosmetics_count": cosmetics_count,
            "scope": scope,                         # 화장품 · 혼합(다른 품목과 함께 발표) · 화장품 외
            "breakdown": _breakdown(section) if section else None,
            "source_url": source_url,
            "file": rel(path),
            "text": body,
        })
    return sorted(out, key=lambda c: c["date"], reverse=True)


def enforcement_trends() -> list[dict]:
    """대시보드 적발 동향: 사례 문서에서 본문을 뺀 요약. 날짜 내림차순."""
    keys = ("date", "title", "full_title", "count", "cosmetics_count", "scope", "breakdown", "source_url", "file")
    return [{k: c[k] for k in keys} for c in case_documents()]


def case_document(key: str) -> dict | None:
    """'CASE_2025-08-06' 또는 '2025-08-06' 으로 사례 하나."""
    date = re.search(r"\d{4}-\d{2}-\d{2}", key or "")
    return next((c for c in case_documents() if date and c["date"] == date.group(0)), None)


def clip(text: str, limit: int = 300) -> str:
    """limit 글자 안으로 자른다. 문장·항목 경계에서 끊고, 잘랐으면 '…' 을 붙인다."""
    text = one_line(text)
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    cut = max(head.rfind(mark) for mark in (". ", "다.", " · ", " / ", ", "))
    if cut >= limit // 2:
        head = head[: cut + (2 if head[cut: cut + 2] in ("다.",) else 1)].rstrip(" ·/,")
    return head.rstrip() + "…"


def case_title(case: dict) -> str:
    """보도자료 제목(끝의 '(식약처 보도참고자료, …)' 같은 출처 괄호는 뺀다)."""
    title = case.get("full_title") or case.get("title") or ""
    return re.sub(r"\s*\((?:식약처|정책브리핑)[^)]*\)\s*$", "", title).strip()


_CASE_LABEL_MAX = 16


def _case_is_label(line: str) -> bool:
    """표의 '위반 유형' 칸처럼 짧은 머리 줄인지."""
    return len(line) <= _CASE_LABEL_MAX and not re.search(r"[,.:;!?\d]", line)


def _case_phrase(case: dict, keywords: tuple[str, ...]) -> str | None:
    """사례 본문에서 낱말이 든 '광고 문구(발췌)' 줄. 표 줄이면 앞 칸 이름을 붙이고, 긴 문단이면 그 문장만."""
    lines = [line.strip() for line in case["text"].splitlines() if line.strip()]
    title_norm = _norm(case.get("full_title") or "")
    keys = [_norm(k) for k in keywords if k]
    best, best_score = None, 0
    for i, line in enumerate(lines):
        flat = _norm(line)
        if len(line) < 6 or not any(k in flat for k in keys):
            continue
        score = 1
        score += 3 if line.count(",") >= 2 else 0
        score += 1 if re.search(r"오인|우려|위반", line) else 0
        score += 1 if line.startswith(("√", "▲")) else 0
        score -= 3 if flat and flat in title_norm else 0
        if score > best_score:
            best, best_score = i, score
    if best is None:
        return None
    line = lines[best]
    if len(line) > 150:     # 문단 한 줄(웹 기사형 본문): 낱말이 든 문장만
        sentences = re.split(r"(?<=다\.)\s+", line)
        return next((s for s in sentences if any(k in _norm(s) for k in keys)), sentences[0])
    item_mark = re.compile(r"^[√▲*◆○·<\-]")
    finished = re.compile(r"(?:등|\.|다|광고)$")
    start = end = best
    # 앞줄: 쉼표로 끝난 목록 줄이거나, 끝맺지 않은 채 이 줄로 이어지는 표 칸 줄(한 줄까지)
    while start > 0 and best - start < 3 and not _case_is_label(lines[start - 1]) and (
            lines[start - 1].endswith(",")
            or (start == best and not finished.search(lines[start - 1]) and not item_mark.match(lines[start]))):
        start -= 1
    # 뒷줄: 쉼표로 끝났으면 목록이 이어진다. 끝맺지 않았으면 다음 항목 표시 전까지 잇는다.
    while end + 1 < len(lines) and end - start < 3 and (
            lines[end].endswith(",")
            or (not finished.search(lines[end]) and not _case_is_label(lines[end + 1])
                and not item_mark.match(lines[end + 1]))):
        end += 1
    phrase = " ".join(lines[start: end + 1])
    phrase = re.sub(r"^[√▲*]\s*", "", phrase)
    label = lines[start - 1].strip("<> ") if start > 0 and _case_is_label(lines[start - 1]) else None
    return f"{label}: {phrase}" if label else phrase


def case_excerpt(key: str, keywords: tuple[str, ...] = (), limit: int = 300) -> str:
    """적발 사례 발췌: 보도자료 제목 · 위반 유형 비율 · 낱말이 든 광고 문구 줄. limit 글자 이내."""
    case = case_document(key)
    if case is None:
        return ""
    parts = [case_title(case)]
    if case["breakdown"]:
        parts.append("유형: " + " · ".join(f"{b['label']} {b['count']}건({b['pct']:g}%)" for b in case["breakdown"]))
    elif case["scope"] == "혼합" and case["cosmetics_count"]:
        parts.append(f"이 중 화장품 {case['cosmetics_count']}건")
    phrase = _case_phrase(case, tuple(keywords)) if keywords else None
    if phrase:
        parts.append(phrase)
    return clip(". ".join(p.rstrip(".") for p in parts), limit)


# ── 지식베이스 통계 ───────────────────────────────────────────────────
def _law_kind_of(path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        head = f.read(400)
    return "법령" if "<법령" in head else "고시"


@lru_cache(maxsize=1)
def kb_stats() -> dict:
    """지식베이스 줄: 법령·고시 XML 수, 지침 수, 적발 사례 수, 원료 성분 수(파일 머리에서 읽음)."""
    laws = sorted((raw_dir() / "law").glob("*.xml"))
    kinds: dict[str, int] = {}
    for path in laws:
        kind = _law_kind_of(path)
        kinds[kind] = kinds.get(kind, 0) + 1
    ingredients, fetched_at = None, None
    ing_path = raw_dir() / "api" / "cosmetic_ingredients.json"
    if ing_path.exists():
        with open(ing_path, encoding="utf-8") as f:
            head = f.read(2000)
        total = re.search(r'"total_count"\s*:\s*(\d+)', head)
        fetched = re.search(r'"fetched_at"\s*:\s*"([^"]+)"', head)
        fetched_at = fetched.group(1) if fetched else None
        if total:
            ingredients = int(total.group(1))
        else:
            with open(ing_path, encoding="utf-8") as f:
                ingredients = len(json.load(f).get("items", []))
    return {
        "laws": len(laws),
        "law_kinds": kinds,
        "guidelines": len(list((raw_dir() / "guide").glob("*.txt"))),
        "cases": len(list((raw_dir() / "cases").glob("case_*.txt"))),
        "ingredients": ingredients,
        "fetched_at": fetched_at,
    }


# ── 검색 말뭉치 (Mock 검색용) ─────────────────────────────────────────
_CHUNK_CHARS = 800


def _split_long(text: str, limit: int = _CHUNK_CHARS) -> list[str]:
    """줄 경계에서 limit 글자 안팎으로 나눈다."""
    parts, buf = [], ""
    for line in text.splitlines():
        if buf and len(buf) + len(line) + 1 > limit:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n{line}" if buf else line
    if buf:
        parts.append(buf)
    return parts or [text]


def _annex_chunks(doc: dict, annex: dict) -> list[dict]:
    """별표 한 개 → 청크. 호·목 구조가 있으면 목 단위(…_별표5-2가), 아니면 글자 수로 나눈다."""
    base = f"{doc['prefix']}_{doc['short']}_별표{annex['no']}"
    label = f"[별표 {annex['no']}]" if annex["no"] else "[별표]"
    lines = annex["text"].splitlines()
    chunks, ho = [], None
    if any(_SUB_MARK.match(line) for line in lines) and not any(_BOX.search(line) for line in lines):
        for line in lines:
            if re.match(r"^(\d+)\.", line):
                ho = re.match(r"^(\d+)\.", line).group(1)
            elif _SUB_MARK.match(line) and ho:
                mok = line[0]
                chunks.append((f"{base}-{ho}{mok}", f"{label} 제{ho}호 {mok}목", line))
    if not chunks:
        parts = _split_long(annex["text"])
        chunks = [(base if len(parts) == 1 else f"{base}-p{i + 1}", label, part) for i, part in enumerate(parts)]
    return [{"id": cid, "article": f"{article} {annex['title']}".strip(), "content": content}
            for cid, article, content in chunks]


@lru_cache(maxsize=1)
def search_chunks() -> list[dict]:
    """법령·고시 조문·별표, 지침 쪽·금지 표현 행, 사례 문단을 검색 청크로 만든다."""
    chunks: list[dict] = []

    def add(cid: str, source: str, doc_type: str, authority: int, article: str, content: str,
            scope: str = "공통", effective: str | None = None) -> None:
        chunks.append({"id": cid, "source": source, "doc_type": doc_type, "authority": authority,
                       "article": article, "product_scope": scope, "effective_date": effective,
                       "content": content, "_norm": _norm(content).lower()})

    for doc in law_documents():
        scope = "기능성" if "기능성" in doc["title"] else "공통"
        for art in doc["articles"]:
            if art["deleted"]:
                continue
            parts = _split_long(art["text"])
            for i, part in enumerate(parts):
                cid = f"{doc['prefix']}_{doc['short']}_{art['no']}" + (f"-{i + 1}" if len(parts) > 1 else "")
                article = f"{art['no']}({art['title']})" if art["title"] else art["no"]
                add(cid, doc["title"], doc["kind"], doc["authority"], article, part, scope, doc["effective_date"])
        for annex in doc["annexes"]:
            if annex["deleted"]:
                continue
            for c in _annex_chunks(doc, annex):
                add(c["id"], doc["title"], doc["kind"], doc["authority"], c["article"], c["content"], scope,
                    doc["effective_date"])
    guide = guide_document()
    for i, row in enumerate(guide["banned_table"]["rows"], 1):
        content = f"{row['category']} — 금지 표현: {row['text']}" + (f" (비고: {row['note']})" if row["note"] else "")
        add(f"GUIDE_관리지침_별표1-{i}", guide["title"], "지침", 3, f"[별표 1] {row['category']} ({row['page']}쪽)",
            content, effective=guide["effective_date"])
    table_pages = set(guide["banned_table"]["pages"])
    for page in guide["pages"]:
        if page["no"] < 6 or page["no"] in table_pages or not page["text"].strip():
            continue
        add(f"GUIDE_관리지침_p{page['no']}", guide["title"], "지침", 3, f"{page['no']}쪽", one_line(page["text"]),
            effective=guide["effective_date"])
    for case in case_documents():
        for i, part in enumerate(_split_long(case["text"], 600), 1):
            add(f"{case['key']}-{i}", "식약처 보도자료", "사례", 4, f"{case['date']} {case['full_title'] or case['title']}",
                one_line(part), effective=case["date"])
    return chunks
