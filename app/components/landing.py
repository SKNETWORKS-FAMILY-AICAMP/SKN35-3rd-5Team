"""
[app/components/landing.py]
홈(소개) 화면의 섹션 HTML — 데이터 dict → HTML 문자열 순수 함수. 버튼(시작하기)은 views/home.py 가 Streamlit 위젯으로 넣는다.

- 구조는 서비스 소개 페이지의 흔한 순서(상단 바 → 히어로 → 문제 → 방식 → 기능 → 근거 자료 → 마지막 안내)를 따르고,
  색·글자·선은 base.css 토큰을 그대로 쓴다. 홈 전용 크기·간격은 styles/home.css.
- 숫자는 전부 data/ 에서 읽은 값이다 (kb_stats · enforcement_trends). 지어낸 수치·후기는 넣지 않는다.
- 섹션 id(bw-problem 등)는 상단 바 앵커가 가리킨다.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from app.components.brand import character_img, lockup_img
from app.components.cards import tag
from app.components.icons import icon
from app.components.layout import esc
from app.components.panels import documents_list
from app.services.data_sources import case_title

_LANDING_DIR = Path(__file__).resolve().parents[1] / "static" / "landing"

SECTIONS = [("bw-problem", "문제"), ("bw-how", "검토 방식"), ("bw-features", "기능"), ("bw-sources", "근거 자료")]


@lru_cache(maxsize=4)
def _image_uri(filename: str) -> str:
    """st.html 은 페이지마다 상대 경로가 달라지므로 data URI 로 넣는다 (brand.py 와 같은 이유)."""
    path = _LANDING_DIR / filename
    return f"data:image/webp;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _section_head(eyebrow: str, title: str, desc: str = "") -> str:
    p = f"<p>{desc}</p>" if desc else ""
    return f'<div class="bw-home-sh"><span class="bw-home-eyebrow">{esc(eyebrow)}</span><h2>{title}</h2>{p}</div>'


# ── 상단 바 ─────────────────────────────────────────────────────────
def top_brand() -> str:
    return f'<div class="bw-home-logo">{lockup_img(30)}</div>'


def top_links() -> str:
    links = "".join(f'<a href="#{sid}">{esc(label)}</a>' for sid, label in SECTIONS)
    return f'<nav class="bw-home-nav" aria-label="홈 섹션">{links}</nav>'


# ── 히어로 ──────────────────────────────────────────────────────────
def hero() -> str:
    return ('<div class="bw-home-hero">'
            '<span class="bw-home-pill"><i></i>규정 문서 기반 광고 문구 검토 AI</span>'
            '<h1>광고 문구, 올리기 전에<br><em>규정으로</em> 확인하세요</h1>'
            '<p>화장품법 · 식약처 고시 · 관리지침 · 적발 사례에서 근거 조항을 찾아 판정하고, '
            '보유한 실증 자료 범위 안에서 쓸 수 있는 문구로 고쳐 드립니다.</p></div>')


def hero_checks() -> str:
    items = ["근거 조항 번호", "금지 표현 판정", "실증 범위 안 교정", "상세페이지 일괄 검토"]
    lis = "".join(f"<li>{icon('check', 16)}{esc(t)}</li>" for t in items)
    return f'<ul class="bw-home-checks">{lis}</ul>'


def preview() -> str:
    return ('<figure class="bw-home-preview">'
            '<div class="bw-home-frame"><div class="bar"><i></i><i></i><i></i>'
            '<span class="url">Beaurette · 검토 대화</span></div>'
            f'<img src="{_image_uri("review-preview.webp")}" width="1440" height="900" '
            'alt="검토 대화 화면: 문구의 판정, 문제 표현 두 개, 오른쪽 근거 조항 목록"></div>'
            '<figcaption>실제 검토 화면 · 데모 데이터</figcaption></figure>')


# ── 문제 ────────────────────────────────────────────────────────────
_PAINS = [
    ("library_books", "규정이 여러 문서에 흩어져 있습니다",
     "화장품법, 시행규칙 별표 5, 실증 규정, 관리지침, 적발 사례를 문구마다 따로 찾아봐야 합니다."),
    ("lab_profile", "같은 효능도 실증 자료에 따라 쓸 수 있는 말이 다릅니다",
     "인체적용시험이 있으면 쓸 수 있는 표현이 자료가 없으면 위반이 됩니다."),
    ("rule", "고친 문구도 다시 확인해야 합니다",
     "한 표현을 바꾸면서 다른 금지 표현이 들어갈 수 있습니다."),
]


def _case_count(case: dict) -> str:
    total = case.get("count")
    if not total:
        return ""
    if case.get("scope") == "혼합" and case.get("cosmetics_count"):
        return f'<b>{total:,}건</b><small>화장품 {case["cosmetics_count"]:,}건</small>'
    if case.get("scope") == "화장품 외":
        return f"<b>{total:,}건</b><small>화장품 외 품목</small>"
    return f"<b>{total:,}건</b>"


def problem(cases: list[dict]) -> str:
    pains = "".join(f'<li><span class="ic">{icon(ic, 20)}</span><div><h3>{esc(t)}</h3><p>{esc(d)}</p></div></li>'
                    for ic, t, d in _PAINS)
    rows = []
    for c in cases:
        title = esc(case_title(c))
        if c.get("source_url"):
            title = (f'<a href="{esc(c["source_url"])}" target="_blank" rel="noopener">{title}'
                     f'{icon("open_in_new", 14)}</a>')
        rows.append(f'<li><span class="d">{esc(c.get("date", ""))}</span>'
                    f'<span class="t">{title}</span><span class="n">{_case_count(c)}</span></li>')
    return (f'<section id="bw-problem" class="bw-home-sec">'
            + _section_head("문제", "광고 문구 한 줄이 행정처분으로 이어집니다",
                            f"식약처는 온라인 부당광고를 점검해 적발 결과를 발표합니다. 아래는 이 서비스가 근거로 쓰는 발표 {len(cases)}건입니다.")
            + f'<div class="bw-home-problem"><ul class="bw-home-pains">{pains}</ul>'
            f'<div class="bw-home-cases"><div class="h"><span>식약처 적발 발표</span><span>날짜 · 건수</span></div>'
            f'<ul>{"".join(rows)}</ul></div></div></section>')


# ── 검토 방식 ───────────────────────────────────────────────────────
def how() -> str:
    verdicts = "".join(tag(t, tone, small=True) for t, tone in
                       [("사용 가능", "pass"), ("실증 필요", "caution"), ("수정 필요", "risk"), ("전문가 검토", "hold")])
    steps = [
        ("01", "근거 검색", "문구에서 위험 표현을 뽑고, 법령 · 고시 · 지침 · 적발 사례 조항을 하이브리드 검색(BM25 + 벡터)으로 찾습니다.", ""),
        ("02", "판정", "금지 표현 규칙과 AI 판정을 함께 써서 네 가지 중 하나로 나눕니다.", f'<div class="tags">{verdicts}</div>'),
        ("03", "교정 · 역검증", "보유 실증 범위 안에서 대체 문구 후보를 만들고, 후보마다 다시 검사해 통과한 것만 제안합니다.", ""),
    ]
    lis = "".join(f'<li><span class="no">{no}</span><h3>{esc(t)}</h3><p>{esc(d)}</p>{extra}</li>' for no, t, d, extra in steps)
    return (f'<section id="bw-how" class="bw-home-sec">'
            + _section_head("검토 방식", "근거를 먼저 찾고, 그 근거로 판정합니다",
                            "답변에는 근거 조항 번호가 붙습니다. 번호를 누르면 오른쪽에 그 조항이 열립니다.")
            + f'<ol class="bw-home-steps">{lis}</ol></section>')


# ── 기능 ────────────────────────────────────────────────────────────
def features() -> str:
    eg_review = ('<div class="bw-home-eg">'
                 f'{tag("수정 필요", "risk", small=True)}'
                 '<span>단 4주 만에 보습력 42% <span class="bw-mark is-caution">폭발적 개선</span> 입증! '
                 '손상 피부 <span class="bw-mark is-risk">완벽 재생</span>!</span></div>')
    eg_project = ('<div class="bw-home-eg is-ladder">'
                  '<span>인체적용시험 있음</span><b>보습 표현 Lv2까지</b>'
                  '<span>실증 해제</span><b>Lv1까지</b></div>')
    cards = [
        ("chat_bubble", "검토 대화", "문구를 붙여 넣으면 판정, 문제 표현, 수정 제안, 출처를 한 답변으로 보여 줍니다. "
         "수정 제안은 강도별 후보 셋 중에서 골라 복사하거나 그 문구로 다시 검토합니다.", eg_review),
        ("lab_profile", "프로젝트 · 보유 실증", "제품과 가지고 있는 실증 자료를 고르면, 그 자료로 쓸 수 있는 표현 단계까지만 제안합니다.", eg_project),
        ("article", "상세페이지 검토", "긴 상세페이지를 문장 단위로 나눠 한 번에 검토합니다. 문장별 결과를 보고 교정본을 복사하거나 내려받습니다.", ""),
        ("menu_book", "규정 · 가이드라인", "조항 검색, 관리지침의 금지 표현, 식약처 적발 사례를 한곳에서 찾아봅니다.", ""),
    ]
    lis = "".join(f'<li><span class="ic">{icon(ic, 20)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p>{eg}</li>'
                  for ic, t, d, eg in cards)
    return (f'<section id="bw-features" class="bw-home-sec">'
            + _section_head("기능", "문구 하나부터 상세페이지 전체까지")
            + f'<ul class="bw-home-features">{lis}</ul></section>')


# ── 근거 자료 ───────────────────────────────────────────────────────
def sources(stats: dict, docs: list[dict]) -> str:
    kinds = stats.get("law_kinds") or {}
    kind_note = " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda kv: kv[0] != "법령"))
    ing = stats.get("ingredients")
    fetched = (stats.get("fetched_at") or "")[:10]
    nums = [
        (stats.get("laws", 0), "종", "법령 · 고시", kind_note),
        (stats.get("guidelines", 0), "종", "표시 · 광고 관리지침", ""),
        (stats.get("cases", 0), "건", "식약처 적발 사례", ""),
        (f"{ing:,}" if isinstance(ing, int) else "-", "개", "원료 성분 사전", f"{fetched} 기준" if fetched else ""),
    ]
    cells = "".join(f'<li><div class="n">{n}<small>{u}</small></div><div class="l">{esc(label)}</div>'
                    f'{f"<div class=m>{esc(note)}</div>" if note else ""}</li>' for n, u, label, note in nums)
    laws = [d for d in docs if d.get("kind") != "사례"]
    return (f'<section id="bw-sources" class="bw-home-sec">'
            + _section_head("근거 자료", "답변의 근거는 이 문서들에서 찾습니다",
                            "법령은 국가법령정보센터, 고시 · 지침 · 사례는 식약처 공개 자료에서 받았습니다.")
            + f'<div class="bw-home-sources"><ul class="bw-home-nums">{cells}</ul>'
            f'<div class="bw-home-docs"><div class="h">수집 문서 {len(laws)}건</div>{documents_list(laws)}</div></div></section>')


# ── 마지막 안내 · 푸터 ──────────────────────────────────────────────
def cta_text() -> str:
    return (f'<div class="bw-home-cta-in"><span class="pic">{character_img(132, alt="")}</span>'
            '<div><h2>검토할 문구가 있나요?</h2>'
            '<p>가입 없이 바로 써 볼 수 있습니다. 문구를 붙여 넣거나 시작 문구 하나를 눌러 보세요.</p></div></div>')


def footer(mode: str) -> str:
    return ('<footer class="bw-home-foot">'
            '<div><b>Beaurette</b><span>SKN35 3차 5팀 프로젝트</span></div>'
            '<p>AI 판정은 참고용입니다. 광고를 게재하기 전에는 담당자가 원문 규정을 확인해 주세요.</p>'
            f'{mode}</footer>')
