"""
[app/components/landing.py]
홈(소개) 화면의 섹션 HTML — 데이터 dict → HTML 문자열 순수 함수 + 움직임 스크립트 하나(MOTION_SCRIPT).
버튼(시작하기)은 views/home.py 가 Streamlit 위젯으로 넣는다. CSS 는 styles/home.css.

- 글자: 홈 전체를 영문 Inter + 한글 Noto Sans KR 로(제목 800 · 줄간격 1.1 · 자간 -0.02em), 날짜·조항 번호는 IBM Plex Mono.
- 캐릭터: 히어로 예시 카드 뒤에서 고개를 내밀고 단계마다 말풍선으로 지금 하는 일을 말한다 · 카드 머리 아바타 · 마지막 안내.
- 움직임은 '교정 동작'만 쓴다 — 밑줄이 그어지고, 판정이 붙고, 근거가 달리고, 제안 문구로 바뀐다.
  적발 발표 띠는 흐르고, 섹션은 화면에 들어올 때 한 번 올라오며, 숫자는 센다. '동작 줄이기'면 모두 멈춘 최종 상태.
- 예시를 지어내지 않는다: 히어로·기능 카드의 판정·제안은 Mock 판정 엔진(services/mock.py)이 그 문구에 실제로 낸 결과,
  숫자는 data/ 실측(kb_stats · enforcement_trends)이다. 화면에는 "데모 데이터"로 표시한다.
"""
from __future__ import annotations

import base64
import json
import re
from functools import lru_cache
from pathlib import Path

from app.components.brand import avatar_img, lockup_img
from app.components.cards import highlighted, tag
from app.components.icons import icon
from app.components.layout import esc
from app.components.theme import status_of
from app.services import mock
from app.services.contract import verdict_of
from app.services.data_sources import case_title

_LANDING_DIR = Path(__file__).resolve().parents[1] / "static" / "landing"

SECTIONS = [("bw-demo", "검토 장면"), ("bw-problem", "문제"), ("bw-how", "검토 방식"), ("bw-features", "기능"),
            ("bw-forecast", "예상 매출"), ("bw-sources", "근거 자료")]

# 히어로 예시 — views/review.py 의 시작 문구와 같다. 판정은 그때그때 Mock 엔진 결과를 쓴다
DEMO_COPIES = [
    "단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!",
    "바르는 순간부터 24시간 촉촉함이 지속되는 수분 크림",
    "PDRN 성분이 피부 속 깊이 전달되는 신개념 앰플",
]
# 히어로 캐릭터 말풍선 — 예시 카드의 단계(s1 밑줄 · s2 판정 · s3 근거 · s4 제안)마다. 없는 단계는 말하지 않는다
SAY = {
    "start": "문구를 읽고 있어요",
    "marks": "위험 표현에 밑줄을 그었어요",
    "nomarks": "근거 조항을 찾고 있어요",
    "verdict": "규정 기준으로 판정했어요",
    "hold": "판단하기 어려운 문구예요",
    "cites": "근거 조항을 달았어요",
    "fix": "이렇게 고쳐 보면 어때요?",
    "nofix": "담당자 확인이 필요해요",
}
# 기능 카드 「상세페이지 검토」 — views/bulk.py 예시 상세페이지의 문장들
DETAIL_LINES = [
    "건조한 피부에 촉촉함을 채워 주는 데일리 수분 크림입니다.",
    "바르는 순간부터 24시간 촉촉함이 지속됩니다.",
    "손상된 피부를 완벽하게 재생시켜 줍니다!",
    "타사 수분 크림 대비 2배 촉촉합니다.",
]


@lru_cache(maxsize=4)
def _image_uri(filename: str) -> str:
    """st.html 은 페이지마다 상대 경로가 달라지므로 data URI 로 넣는다 (brand.py 와 같은 이유)."""
    path = _LANDING_DIR / filename
    return f"data:image/webp;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _rabbit(height: int) -> str:
    """팀 캐릭터 전신 — 원본(app/assets/rabbit-lab-scientist-v1.png, 1254px)에서 홈용으로 잘라 둔 600px 판."""
    return f'<img src="{_image_uri("rabbit-hero.webp")}" style="height:{height}px;width:auto" alt="">'


def _cite_label(c: dict) -> str:
    return " ".join(x for x in (c.get("source", ""), c.get("article", "")) if x)


def examples(product: dict) -> list[dict]:
    """히어로 예시 3개 — Mock 엔진이 각 문구에 낸 판정 · 근거 · 제안."""
    out = []
    for text in DEMO_COPIES:
        resp = mock.review(text, product)
        res, ui = resp.get("result", {}), resp.get("ui", {})
        label, tone = status_of(verdict_of(res))
        chosen = next((v for v in ui.get("variants") or [] if v.get("chosen")), None)
        out.append({
            "text": text,
            "quote": highlighted(text, ui.get("highlights") or []),
            "label": label,
            "tone": tone,
            "summary": ui.get("summary") or "",
            "cites": [_cite_label(c) for c in (res.get("citations") or [])[:3]],
            "fix": (chosen or {}).get("text") or res.get("suggestion") or "",
            "verified": bool(chosen and chosen.get("verified")),
        })
    return out


def ladder_pair(product: dict) -> dict:
    """기능 카드 「프로젝트」 — 같은 문구를 실증 있음 / 실증 해제로 검토했을 때 제안 단계와 문구."""
    text = DEMO_COPIES[0]
    on = mock.review(text, product)
    off = mock.review(text, dict(product, owned_evidence=[]))
    ev = (product.get("owned_evidence") or [{}])[0]
    return {
        "evidence": " · ".join(x for x in (ev.get("test_type"), ev.get("item")) if x),
        "on": {"lv": on["ui"]["ladder"]["proposal"], "text": on["result"].get("suggestion") or ""},
        "off": {"lv": off["ui"]["ladder"]["proposal"], "text": off["result"].get("suggestion") or ""},
    }


def detail_rows(product: dict) -> list[dict]:
    rows = []
    for line in DETAIL_LINES:
        label, tone = status_of(verdict_of(mock.review(line, product)["result"]))
        rows.append({"text": line, "label": label, "tone": tone})
    return rows


def _display(text_html: str, tag_name: str = "h2") -> str:
    """큰 제목 — <br> 로 나눈 줄마다 감싸 두어 줄 단위로 올라오게 한다(.ln, 섹션은 화면에 들어올 때 · 히어로는 처음에)."""
    lines = "".join(f'<span class="ln"><span>{line}</span></span>' for line in text_html.split("<br>"))
    return f'<{tag_name} class="bw-h-display">{lines}</{tag_name}>'


def _photo(name: str) -> str:
    """생성 화보(app/static/landing/editorial-*.webp, AI 생성) — 정적 서빙 주소. HTML 에 base64 로 넣지 않는다."""
    return f"/app/static/landing/editorial-{name}.webp"


def _head(no: str, eyebrow: str, title_html: str, desc: str = "") -> str:
    """섹션 머리 — no 가 비면 번호 없이 선만(번호 섹션 사이에 끼는 장)."""
    p = f"<p>{esc(desc)}</p>" if desc else ""
    mark = f'<span class="no">{no}</span>' if no else '<span class="no is-blank" aria-hidden="true"></span>'
    return (f'<div class="bw-h-sh rv"><div class="ey">{mark}{esc(eyebrow)}</div>'
            f'{_display(title_html)}{p}</div>')


# ── 상단 바 ─────────────────────────────────────────────────────────
def top_brand() -> str:
    return f'<div class="bw-h-logo">{lockup_img(30)}</div>'


def top_links() -> str:
    links = "".join(f'<a href="#{sid}">{esc(label)}</a>' for sid, label in SECTIONS)
    return f'<nav class="bw-h-nav" aria-label="홈 섹션">{links}</nav>'


# ── 히어로 ──────────────────────────────────────────────────────────
def hero_text() -> str:
    return ('<div class="bw-h bw-h-hero">'
            '<span class="bw-h-pill"><i class="ping"></i>규정 문서 기반 광고 문구 검토 AI</span>'
            + _display("광고 문구,<br>올리기 전에<br><em>규정으로</em> 확인하세요", "h1") +
            '<p>화장품법 · 식약처 고시 · 관리지침 · 적발 사례에서 근거 조항을 찾아 판정하고, '
            '보유한 실증 자료 범위 안에서 쓸 수 있는 문구로 고쳐 드립니다.</p></div>')


def hero_meta(stats: dict) -> str:
    ing = stats.get("ingredients")
    items = [(stats.get("laws", 0), "종", "법령 · 고시"), (stats.get("cases", 0), "건", "적발 사례"),
             (f"{ing:,}" if isinstance(ing, int) else "-", "개", "원료 성분")]
    lis = "".join(f"<li><b>{n}</b>{u} {esc(label)}</li>" for n, u, label in items)
    return f'<ul class="bw-h bw-h-meta">{lis}</ul>'


def hero_scene() -> str:
    """히어로 오른쪽 화보 장면 — 사진은 화면 높이에 맞춰 오른쪽에 붙어(넓은 화면에서도 사물이 잘리지 않고 글자와 비율이 맞는다)
    흘러내리는 세럼과 떨어지는 방울 · 유리의 빛 · 벽의 빛 무늬 · 빛 알갱이는 사진 좌표(%)에 얹는다.
    (토끼는 2026-10-14 CEO "첫 화면에 토끼는 빼자, 난잡하다"로 뺐다.) 장식이라 화면 읽기에서는 뺀다."""
    motes = "".join(f'<i class="mote m{i}"></i>' for i in range(1, 6))
    return ('<div class="bw-h-scene" aria-hidden="true"><div class="ph">'
            '<img class="photo" src="/app/static/landing/editorial-studio.webp?v=2" alt="">'
            '<span class="stream"></span><i class="drop"></i><i class="drop d2"></i>'   # 흘러내리는 세럼 · 떨어지는 방울 · 바닥 물결
            f'<span class="glint"></span><span class="caustic"></span>{motes}'
            '</div></div>')


def hero_proof(exs: list[dict]) -> str:
    """히어로 아래쪽 교정 줄 — 사진 위에서 실제 문구에 밑줄이 그어지고(s1) 위험 표현이 지워지고 판정이 붙은 뒤(s2)
    근거가 달리고(s3) 엔진 제안 문구가 써진다(s4) · 역검증(s5). 판정 · 근거 · 제안은 Mock 엔진 실제 결과(examples)."""
    panels = []
    for i, ex in enumerate(exs):
        fix = (f'<p class="fixed"><span class="arw">{icon("arrow_forward", 16)}</span><span class="t">{esc(ex["fix"])}</span></p>'
               if ex["fix"] else '<p class="fixed is-hold"><span class="t">근거가 부족해 담당자 검토로 넘깁니다</span></p>')
        cite = esc(ex["cites"][0]) if ex["cites"] else ""
        state = " on s1 s2 s3 s4 s5" if i == 0 else ""   # 스크립트가 없으면 첫 예시의 최종 상태
        panels.append(f'<div class="ex is-{ex["tone"]}{state}"><p class="quote">{ex["quote"]}</p>{fix}'
                      f'<div class="meta">{tag(ex["label"], ex["tone"], small=True)}'
                      f'{f"<span class=cite>{cite}</span>" if cite else ""}'
                      f'{"<span class=ok>" + icon("check", 13) + "역검증 통과</span>" if ex["verified"] else ""}</div></div>')
    dots = "".join(f'<i{" class=on" if i == 0 else ""}></i>' for i in range(len(exs)))
    return (f'<div class="bw-h bw-h-proof" data-demo aria-label="교정 장면 — 실제 검토 결과">'
            f'<div class="bar"><span class="k"><i class="ping"></i>교정 중</span><span class="dots" aria-hidden="true">{dots}</span></div>'
            f'<div class="stage">{"".join(panels)}</div></div>')


def correction_band(terms: list[dict]) -> str:
    """금지 표현 → 바꿔 쓸 표현 — 금지 표현 사전(banned_terms.json)의 term · fix_hint 그대로, 큰 글자로 흐른다."""
    rows = []
    for t in terms:
        term = re.sub(r"\s*\([^)]*\)", "", t.get("term", "")).strip()
        fix = (t.get("fix_hint") or "").strip()
        if not term or not fix or "삭제" in fix or len(fix) > 18:
            continue
        rows.append(f'<li><s>{esc(term)}</s><i aria-hidden="true">{icon("arrow_forward", 22)}</i><b>{esc(fix)}</b></li>')
    items = "".join(rows[:16])
    return ('<div class="bw-h bw-h-band-type" aria-label="금지 표현 사전 — 금지 표현과 바꿔 쓸 표현">'
            f'<div class="track"><ul>{items}</ul><ul aria-hidden="true">{items}</ul></div>'
            '<p class="src">식약처 화장품 표시 · 광고 관리지침 금지 표현과 바꿔 쓸 표현 — 이 서비스의 금지 표현 사전</p></div>')


def photo_band(name: str, alt: str, caption: str) -> str:
    """잡지 펼침면 같은 전폭 사진 띠 — 화면에 들어오면 커튼처럼 열리고, 스크롤에 따라 사진이 천천히 움직인다."""
    return (f'<figure class="bw-h bw-h-photo rv" data-par><div class="img" role="img" aria-label="{esc(alt)}" '
            f'style="background-image:url({_photo(name)})"></div><figcaption>{esc(caption)}</figcaption></figure>')


# 피부에 바르는 실사 컷(AI 생성) → 그 장면에 따라붙는 표현(금지 표현 사전 id). 왼쪽 세로 한 장 · 오른쪽 가로 두 장
_SKIN = [
    ("neck", "목선에 흰 크림을 손끝으로 펴 바르는 모습", "B061"),
    ("cheek", "눈을 감고 볼에 흰 크림을 펴 바르는 모습", "B030"),
    ("hand", "손등 위로 유리 스포이드에서 세럼 한 방울이 떨어지는 모습", "B032"),
]


def skin_spread(terms: list[dict]) -> str:
    """피부에 닿는 문구 — 바르는 장면 사진마다 금지 표현 → 바꿔 쓸 표현(금지 표현 사전 term · fix_hint 그대로)."""
    by_id = {t.get("id"): t for t in terms}
    figs = []
    for i, (name, alt, tid) in enumerate(_SKIN, 1):
        t = by_id.get(tid)
        chip = ""
        if t and t.get("fix_hint"):
            kind = (t.get("type") or "").replace("오인", " 오인")
            chip = (f'<figcaption class="chip"><s>{esc(t["term"])}</s>{icon("arrow_forward", 14)}<b>{esc(t["fix_hint"])}</b>'
                    f'<small>{esc(kind)} · 금지 표현 사전 {esc(tid)}</small></figcaption>')
        figs.append(f'<figure class="f{i} rv"><div class="bw-h-pic" role="img" aria-label="{esc(alt)}" '
                    f'style="background-image:url(/app/static/landing/skin-{name}.webp)"></div>{chip}</figure>')
    return ('<section class="bw-h bw-h-skin" aria-label="피부에 닿는 문구">'
            + _head("", "피부에 닿는 문구", "피부에 닿기 전에,<br><em>문구</em>부터 검토합니다",
                    "바르는 장면마다 따라붙는 표현이 있습니다. 사진마다 그 표현이 금지 표현 사전에서 어떻게 바뀌는지 붙였습니다.")
            + f'<div class="bw-h-skin-grid">{"".join(figs)}</div><p class="bw-h-credit">이미지 · AI 생성</p></section>')


def demo_section(exs: list[dict], product_name: str, n_evidence: int) -> str:
    """실제 검토 장면 — 히어로의 교정 줄을 판정 · 근거 · 제안까지 펼친 예시 카드(엔진 실제 결과)."""
    return ('<section id="bw-demo" class="bw-h bw-h-sec bw-h-demo-sec">'
            + _head("01", "실제 검토 장면", "문구 하나에<br>판정 · 근거 · <em>제안</em>까지",
                    "아래 카드는 Mock 판정 엔진이 시작 문구 세 개에 실제로 낸 결과를 그대로 보여 줍니다. 문구마다 위험 표현에 밑줄을 긋고, "
                    "규정 기준으로 판정하고, 근거 조항을 단 뒤 보유 실증 범위 안의 문구로 고칩니다.")
            + demo(exs, product_name, n_evidence) + '</section>')


def demo(exs: list[dict], product_name: str, n_evidence: int) -> str:
    panels = []
    for i, ex in enumerate(exs):
        cites = "".join(f"<li><b>{k}</b>{esc(c)}</li>" for k, c in enumerate(ex["cites"], 1))
        if ex["fix"]:
            ok = f'<span class="ok">{icon("check", 14)}역검증 통과</span>' if ex["verified"] else ""
            fix = (f'<div class="fix"><div class="lab">수정 제안{ok}</div>'
                   f'<p>{esc(ex["fix"])}</p></div>')
        else:
            fix = ('<div class="fix is-hold"><div class="lab">수정 제안</div>'
                   '<p>근거 조항을 충분히 찾지 못해 담당자 검토로 넘깁니다.</p></div>')
        state = " on s1 s2 s3 s4 s5" if i == 0 else ""   # 스크립트가 없으면 첫 예시의 최종 상태를 보인다
        panels.append(
            f'<div class="ex is-{ex["tone"]}{state}">'
            f'<div class="lab">검토한 문구</div><p class="quote">{ex["quote"]}</p>'
            f'<div class="verdict">{tag(ex["label"], ex["tone"])}<span>{esc(ex["summary"])}</span></div>'
            f'{f"<ol class=cites>{cites}</ol>" if cites else ""}{fix}</div>'
        )
    dots = "".join(f'<i{" class=on" if i == 0 else ""}></i>' for i in range(len(exs)))
    first = SAY["fix"] if exs and exs[0]["fix"] else SAY["nofix"]   # 스크립트가 없을 때 = 첫 예시의 마지막 말
    buddy = (f'<div class="buddy" aria-hidden="true"><span class="say">{esc(first)}</span>'
             f'<span class="pic">{_rabbit(228)}</span></div>')
    return ('<div class="bw-h bw-h-demo rv" data-demo aria-label="검토 예시">' + buddy + '<div class="card">'
            f'<div class="bar"><span class="live">{avatar_img(22)}뷰렛 AI · 검토 예시</span>'
            f'<span class="who">{esc(product_name)} · 실증 {n_evidence}건</span>'
            f'<span class="dots" aria-hidden="true">{dots}</span></div>'
            f'<div class="stage">{"".join(panels)}</div>'
            '<div class="foot">Mock 판정 엔진의 실제 결과 · 데모 데이터</div></div></div>')


# ── 적발 발표 띠 ────────────────────────────────────────────────────
def ticker(cases: list[dict]) -> str:
    def item(c: dict) -> str:
        n = f'<b>{c["count"]:,}건</b>' if c.get("count") else ""
        return f'<li><span class="d">{esc(c.get("date", ""))}</span><span class="t">{esc(c.get("title", ""))}</span>{n}</li>'
    items = "".join(item(c) for c in cases)
    return ('<div class="bw-h bw-h-ticker"><span class="lab">식약처 적발 발표</span>'
            f'<div class="track"><ul>{items}</ul><ul aria-hidden="true">{items}</ul></div></div>')


# ── 01 문제 ─────────────────────────────────────────────────────────
_PAINS = [
    ("흩어진 규정", "규정이 여러 문서에 흩어져 있습니다",
     "화장품법, 시행규칙 별표 5, 실증 규정, 관리지침, 적발 사례를 문구마다 따로 찾아봐야 합니다."),
    ("실증 범위", "실증에 따라 쓸 수 있는 말이 다릅니다",
     "인체적용시험이 있으면 쓸 수 있는 표현이 자료가 없으면 위반이 됩니다."),
    ("고친 뒤 재확인", "고친 문구도 다시 확인해야 합니다",
     "한 표현을 바꾸면서 다른 금지 표현이 들어갈 수 있습니다."),
]


def problem(cases: list[dict]) -> str:
    cols = "".join(f'<li class="rv"><span class="k">{esc(k)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></li>'
                   for k, t, d in _PAINS)
    rows = []
    for c in cases:
        title = esc(case_title(c))
        if c.get("source_url"):
            title = f'<a href="{esc(c["source_url"])}" target="_blank" rel="noopener">{title}{icon("open_in_new", 14)}</a>'
        sub = ""
        if c.get("scope") == "혼합" and c.get("cosmetics_count"):
            sub = f'<small>화장품 {c["cosmetics_count"]:,}건</small>'
        elif c.get("scope") == "화장품 외":
            sub = "<small>화장품 외 품목</small>"
        n = f'<b>{c["count"]:,}건</b>' if c.get("count") else ""
        rows.append(f'<li class="rv"><span class="d">{esc(c.get("date", ""))}</span>'
                    f'<span class="t">{title}</span><span class="n">{n}{sub}</span></li>')
    return (f'<section id="bw-problem" class="bw-h bw-h-sec bw-h-ink">' + ticker(cases)
            + photo_band("amber", "짙은 어둠 속 빛나는 호박색 구체 앞, 황동 선반 위에 놓인 호박색 유리 세럼 병과 크림 단지, 크림빛 난초 한 송이",
                         "병이 아무리 고급스러워도 — 행정처분은 문구 한 줄에서 시작됩니다")
            + _head("02", "문제", "광고 문구 한 줄이<br><em>행정처분</em>으로 이어집니다",
                    f"식약처는 온라인 부당광고를 점검해 적발 결과를 발표합니다. 아래는 이 서비스가 근거로 쓰는 발표 {len(cases)}건입니다.")
            + f'<ul class="bw-h-cols">{cols}</ul>'
            f'<div class="bw-h-cases"><div class="h rv"><span>식약처 적발 발표</span><span>날짜 · 건수</span></div>'
            f'<ul>{"".join(rows)}</ul></div></section>')


# ── 02 검토 방식 ────────────────────────────────────────────────────
def how() -> str:
    verdicts = "".join(tag(t, tone, small=True) for t, tone in
                       [("사용 가능", "pass"), ("실증 필요", "caution"), ("수정 필요", "risk"), ("전문가 검토", "hold")])
    steps = [
        ("근거 검색", "문구에서 위험 표현을 뽑고, 법령 · 고시 · 지침 · 적발 사례 조항을 하이브리드 검색(BM25 + 벡터)으로 찾습니다.", ""),
        ("판정", "금지 표현 규칙과 AI 판정을 함께 써서 네 가지 중 하나로 나눕니다.", f'<div class="tags">{verdicts}</div>'),
        ("교정 · 역검증", "보유 실증 범위 안에서 대체 문구 후보를 만들고, 후보마다 다시 검사해 통과한 것만 제안합니다.", ""),
    ]
    lis = "".join(f'<li><span class="node">{i}</span><h3>{esc(t)}</h3><p>{esc(d)}</p>{extra}</li>'
                  for i, (t, d, extra) in enumerate(steps, 1))
    return (f'<section id="bw-how" class="bw-h bw-h-sec">'
            + _head("03", "검토 방식", "근거를 먼저 찾고,<br>그 근거로 <em>판정</em>합니다",
                    "답변에는 근거 조항 번호가 붙습니다. 번호를 누르면 오른쪽에 그 조항이 열립니다.")
            + photo_band("serum", "아이보리 받침대 위에 맺힌 투명한 세럼 방울 접사", "문구 한 줄도 원료 하나처럼 — 성분을 보듯 표현을 봅니다")
            + f'<div class="bw-h-steps rv"><div class="line"><i></i></div><ol>{lis}</ol></div>'
            '<figure class="bw-h-shot rv"><div class="frame"><div class="bar"><i></i><i></i><i></i>'
            '<span class="url">Beaurette · 검토 대화</span></div>'
            f'<img src="{_image_uri("review-preview.webp")}" width="1440" height="900" '
            'alt="검토 대화 화면: 문구의 판정, 문제 표현 두 개, 오른쪽 근거 조항 목록"></div>'
            '<figcaption>실제 검토 화면 · 데모 데이터</figcaption></figure></section>')


# ── 03 기능 ─────────────────────────────────────────────────────────
def features(ex: dict, pair: dict, rows: list[dict]) -> str:
    fix = f'<div class="fix"><span>수정 제안</span>{esc(ex["fix"])}</div>' if ex["fix"] else ""
    vis_review = (f'<div class="vis vis-review"><p class="quote">{ex["quote"]}</p>'
                  f'<div class="verdict">{tag(ex["label"], ex["tone"], small=True)}<span>{esc(ex["summary"])}</span></div>{fix}</div>')
    rungs = "".join(f"<span>{x}</span>" for x in ("Lv0", "Lv1", "Lv2", "불가"))
    vis_project = (f'<div class="vis vis-project">'
                   f'<div class="ev"><span class="box">{icon("check", 13)}</span>{esc(pair["evidence"])}</div>'
                   f'<div class="ladder"><div class="bar"><i></i></div><div class="rungs">{rungs}</div></div>'
                   f'<div class="out"><p class="a"><span>실증 있음 · Lv{pair["on"]["lv"]}</span>{esc(pair["on"]["text"])}</p>'
                   f'<p class="b"><span>실증 해제 · Lv{pair["off"]["lv"]}</span>{esc(pair["off"]["text"])}</p></div></div>')
    lis = "".join(f'<li><i class="dot is-{r["tone"]}"></i><span>{esc(r["text"])}</span>{tag(r["label"], r["tone"], small=True)}</li>'
                  for r in rows)
    vis_detail = f'<div class="vis vis-detail"><ol>{lis}</ol></div>'
    res = "".join(f"<li><b>{k}</b>{esc(c)}</li>" for k, c in enumerate(ex["cites"], 1))
    vis_library = (f'<div class="vis vis-library"><div class="q">{icon("search", 16)}<span class="typed">피부 재생</span>'
                   f'<i class="caret"></i></div><ol>{res}</ol></div>')
    cards = [
        ("검토 대화", "문구를 붙여 넣으면 판정, 문제 표현, 수정 제안, 출처를 한 답변으로 보여 줍니다.", vis_review),
        ("프로젝트 · 보유 실증", "가지고 있는 실증 자료를 고르면, 그 자료로 쓸 수 있는 표현 단계까지만 제안합니다.", vis_project),
        ("상세페이지 검토", "긴 상세페이지를 문장 단위로 나눠 한 번에 검토하고, 교정본을 복사하거나 내려받습니다.", vis_detail),
        ("규정 · 가이드라인", "조항 검색, 관리지침의 금지 표현, 식약처 적발 사례를 한곳에서 찾아봅니다.", vis_library),
    ]
    lis = "".join(f'<li class="rv"><div class="txt"><h3>{esc(t)}</h3><p>{esc(d)}</p></div>{vis}</li>'
                  for t, d, vis in cards)
    return (f'<section id="bw-features" class="bw-h bw-h-sec">'
            + _head("04", "기능", "문구 하나부터<br><em>상세페이지</em> 전체까지")
            + f'<ul class="bw-h-features">{lis}</ul></section>')


# ── 05 예상 매출 시나리오 ───────────────────────────────────────────
# 팀원 화면(views/forecast.py · 사이드바 「근거 · 예측」)을 홈에서 소개한다 — 그 화면의 네 단계를 예시 제품의 실제 계산 결과로 펼친다.
# 계산은 home.py 가 같은 서비스(peer_market · revenue_scenario)로 하고, 여기는 결과 dict → HTML 만.
# 오르내림 표시는 그 화면의 규칙 그대로: 오르면 빨강 ▲ · 내리면 파랑 ▼ · 변화 없음 회색 ■.
_LEVEL = {0: ("쓸 수 있음", "pass"), 1: ("근거 필요", "caution"), 2: ("쓰면 안 됨", "risk")}


def _won(v: float) -> str:
    v = abs(v)
    return f"{v / 1e8:,.2f}억 원" if v >= 1e8 else f"{v / 1e4:,.0f}만 원" if v >= 1e4 else f"{v:,.0f}원"


def _fc_side(cls: str, title: str, copy: str, scen: dict) -> str:
    label, tone = _LEVEL.get(scen["inputs"]["level"], ("판단 보류", "hold"))
    risk = scen["revenue_at_risk_if_unchanged"]
    if risk["status"] == "no_violation":
        amt, note = '<i class="flat" aria-label="변화 없음">■</i><b>없음</b>', "규칙상 처분 대상 표현이 없습니다"
    elif risk["status"] == "needs_review":
        amt, note = '<i class="flat" aria-label="변화 없음">■</i><b>개별 검토</b>', risk.get("note") or "처분표와 연결되지 않은 조항"
    else:
        upper = not (risk.get("amount_krw") or risk.get("estimate_krw"))
        amount = risk.get("amount_krw") or risk.get("estimate_krw") or risk["upper_bound_krw"]
        amt = (f'<i class="dn" aria-label="하락">▼</i><b>{"최대 " if upper else ""}{_won(amount["mid"])}</b>')
        note = (f'{risk["condition"]} {risk["sanction"]} {risk["months"]}개월'
                + (" · 모든 매출이 광고에서 온다고 가정한 최대" if upper else ""))
    return (f'<div class="side {cls}"><span class="k">{esc(title)}</span><p class="q">{esc(copy)}</p>{tag(label, tone, small=True)}'
            f'<div class="amt"><span class="l">적발되면 잃을 수 있는 매출</span>{amt}</div><p class="m">{esc(note)}</p></div>')


def forecast(fc: dict) -> str:
    """05 예상 매출 시나리오 — 비슷한 시장 제품 → 경쟁 문구 → 최적 문구 → 예상 매출(처분 위험 · 문구 교체 폭)."""
    p, peers, bench, best = fc["product"], fc["peers"], fc["bench"], fc["best"]
    before, after = fc["before"], fc["after"]
    hard = next((r for r in sorted(fc["summary"], key=lambda r: -r["products"])
                 if r["products"] and r["caution"] + r["risky"] > r["safe"]), None)
    price_note = f" · 가격 {bench['min']:,}~{bench['max']:,}원" if bench else ""
    steps = [
        ("비슷한 시장 제품 찾기", f"{len(peers)}개", " · ".join(x["brand"] for x in peers[:5]) + price_note),
        ("경쟁 제품 문구 분석", f"{hard['peers']}개 중 {hard['products']}개 제품" if hard else f"{len(fc['summary'])}개 유형",
         f"「{hard['type']}」 문구를 쓰지만 수집 문구 대부분이 ‘근거 필요’ 판정" if hard else "문구 유형별 사용 현황과 규칙 판정"),
        ("우리 제품 최적 문구", _LEVEL[best["level"]][0] if best["level"] in _LEVEL else "판단 보류", f"“{best['copy']}”"),
        ("예상 매출", _won(before["monthly_revenue_krw"]["mid"]),
         f"판매가 {p['price_krw']:,}원 × 월 {fc['units']['mid']:,}개(평소 가정) · 원문과 추천 문구를 나란히"),
    ]
    lis = "".join(f'<li><span class="node">{i}</span><div><h3>{esc(t)}</h3><b class="v">{esc(v)}</b><p>{esc(d)}</p></div></li>'
                  for i, (t, v, d) in enumerate(steps, 1))
    band = before["copy_change_band"]
    pct, krw = band["change_magnitude_pct"], band["change_magnitude_krw"]
    span = max(pct["p75"], 1)
    bars = "".join(f'<i class="b{k}" style="--w:{pct[q] / span * 50:.1f}%"></i>' for k, q in ((3, "p75"), (2, "median"), (1, "p25")))
    card = (
        '<div class="bw-h-fc-card rv"><div class="bar"><span>예시 제품 · ' + esc(p["name"]) + '</span>'
        '<span class="mono">' + esc(fc["label"]) + '</span></div>'
        '<div class="cmp">' + _fc_side("is-before", "원문 그대로", fc["original"], before)
        + _fc_side("is-after", "추천 문구로 바꾸면", best["copy"], after) + '</div>'
        f'<div class="band"><div class="h"><span>문구를 바꾸면 매출이 움직일 수 있는 폭</span><span class="mono">보통 움직일 때</span></div>'
        f'<div class="scale" aria-hidden="true">{bars}<i class="mid"></i></div>'
        f'<div class="ends"><span class="dn">▼ −{pct["median"]}% · {_won(krw["median"])}</span>'
        f'<span class="up">▲ +{pct["median"]}% · {_won(krw["median"])}</span></div>'
        f'<p class="m">공개 A/B 실험 148건의 문구 효과 크기(조금 · 보통 · 많이 움직일 때 {pct["p25"]}% · {pct["median"]}% · {pct["p75"]}%)를 빌려 온 가정 범위입니다. '
        '방향은 정해지지 않았고, 추천 문구가 매출을 올린다고 보장하지 않습니다.</p></div>'
        f'<p class="note">판매량(월 {fc["units"]["low"]:,} · {fc["units"]["mid"]:,} · {fc["units"]["high"]:,}개) · 1차 위반 · 광고 기준은 예시 가정입니다. '
        '예상 매출 화면에서 「예시로 해보기 · 비타민A 앰플」을 누르면 같은 계산을 직접 바꿔 볼 수 있습니다.</p></div>')
    return ('<section id="bw-forecast" class="bw-h bw-h-sec">'
            + _head("05", "예상 매출 시나리오", "문구 하나가<br><em>매출</em>을 얼마나 움직일까",
                    "비슷한 시장 제품과 비교해 쓸 수 있는 가장 강한 문구를 고르고, 원문 그대로 적발되면 잃을 수 있는 매출과 "
                    "문구를 바꿨을 때 움직일 수 있는 폭을 계산합니다. 아래는 예시 제품의 실제 계산 결과입니다.")
            + f'<div class="bw-h-fc"><ol class="bw-h-fc-steps rv">{lis}</ol>{card}</div></section>')


# ── 06 근거 자료 ────────────────────────────────────────────────────
def sources(stats: dict, docs: list[dict]) -> str:
    kinds = stats.get("law_kinds") or {}
    kind_note = " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda kv: kv[0] != "법령"))
    ing = stats.get("ingredients")
    fetched = (stats.get("fetched_at") or "")[:10]
    nums = [
        (stats.get("laws", 0), "종", "법령 · 고시", kind_note),
        (stats.get("guidelines", 0), "종", "표시 · 광고 관리지침", ""),
        (stats.get("cases", 0), "건", "식약처 적발 사례", ""),
        (ing if isinstance(ing, int) else 0, "개", "원료 성분 사전", f"{fetched} 기준" if fetched else ""),
    ]
    cells = "".join(f'<li><div class="n"><span data-count="{n}">{n:,}</span><small>{u}</small></div>'
                    f'<div class="l">{esc(label)}</div><div class="m">{esc(note)}</div></li>' for n, u, label, note in nums)
    laws = [d for d in docs if d.get("kind") != "사례"]
    doc_cells = "".join(
        f'<li><span class="kind">{esc(d.get("kind", ""))}</span><h3>{esc(d.get("title", ""))}</h3>'
        f'<p>{esc(" · ".join(x for x in (d.get("org", ""), d.get("version") or d.get("date") or "") if x))}</p></li>'
        for d in laws)
    return (f'<section id="bw-sources" class="bw-h bw-h-sec">'
            + _head("06", "근거 자료", "답변의 근거는<br>이 <em>문서들</em>에서 찾습니다",
                    "법령은 국가법령정보센터, 고시 · 지침 · 사례는 식약처 공개 자료에서 받았습니다.")
            + photo_band("documents", "숲색 · 테라코타 인덱스 탭이 붙은 서류 묶음과 만년필이 놓인 책상",
                         "법령 · 고시 · 지침 · 적발 사례 — 조항 단위로 나눠 색인했습니다")
            + f'<ul class="bw-h-stats rv">{cells}</ul><ul class="bw-h-docs rv">{doc_cells}</ul></section>')


# ── 마지막 안내 · 푸터 ──────────────────────────────────────────────
def closing() -> str:
    """마무리 띠 — 짙은 바탕(잉크 띠와 같은 색 규칙), 왼쪽 한 줄 · 오른쪽 난초 접사(AI 생성)."""
    return ('<section class="bw-h bw-h-ink bw-h-close" aria-label="마무리">'
            + '<div class="txt">' + _head("", "Beaurette", "화려한 말보다<br><em>근거 있는 말</em>로",
                                          "금지 표현은 걸러 내고, 가진 실증 자료로 쓸 수 있는 표현까지만 제안합니다.") + '</div>'
            + '<figure class="pic rv"><div class="bw-h-pic" role="img" aria-label="어둠 속에서 가운데가 빛나는 숲색 난초 접사" '
            f'style="background-image:url({_photo("orchid")})"></div><figcaption>이미지 · AI 생성</figcaption></figure></section>')


def cta_text() -> str:
    return (f'<div class="bw-h bw-h-cta"><span class="pic">{_rabbit(136)}</span>'
            '<div>' + _display("검토할 문구가 있나요?") +
            '<p>가입 없이 바로 써 볼 수 있습니다. 문구를 붙여 넣거나 시작 문구 하나를 눌러 보세요.</p></div></div>')


def footer(mode: str) -> str:
    return ('<footer class="bw-h bw-h-foot">'
            '<div><b>Beaurette</b><span>SKN35 3차 5팀 프로젝트</span></div>'
            '<p>AI 판정은 참고용입니다. 광고를 게재하기 전에는 담당자가 원문 규정을 확인해 주세요.</p>'
            f'{mode}</footer>')


# ── 움직임 ──────────────────────────────────────────────────────────
# 1) .rv 가 화면에 들어오면 is-in (한 번)  2) [data-count] 숫자 세기  3) 히어로 예시를 단계별로 보이고 다음 예시로,
#    단계마다 캐릭터가 말풍선으로 말하고 살짝 뛴다
# 스크립트가 돌지 않으면 html 에 bw-js 가 없어 숨김 규칙이 걸리지 않는다 — 내용은 그대로 보인다.
_MOTION_JS = """<script>
(function () {
  document.documentElement.classList.add('bw-js');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function count(scope) {
    scope.querySelectorAll('[data-count]:not([data-counted])').forEach(function (el) {
      el.setAttribute('data-counted', '1');
      var to = +el.getAttribute('data-count');
      if (reduce || !to) return;
      var t0 = performance.now(), dur = 1200;
      el.textContent = '0';
      (function step(t) {
        var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(to * e).toLocaleString('ko-KR');
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    });
  }

  function reveal() {
    var els = document.querySelectorAll('.bw-h .rv:not([data-rv])');
    if (!els.length) return;
    if (reduce || !('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.setAttribute('data-rv', '1'); el.classList.add('is-in'); count(el); });
      return;
    }
    if (!window.__bwRv) {
      window.__bwRv = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          en.target.classList.add('is-in');
          window.__bwRv.unobserve(en.target);
          count(en.target);
        });
      }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
    }
    els.forEach(function (el) { el.setAttribute('data-rv', '1'); window.__bwRv.observe(el); });
  }

  function demo() {
    document.querySelectorAll('[data-demo]:not([data-run])').forEach(play);
  }
  function play(box) {
    box.setAttribute('data-run', '1');
    if (reduce) return;
    var exs = box.querySelectorAll('.ex'), dots = box.querySelectorAll('.dots i');
    var ext = box.getAttribute('data-buddy') ? document.querySelector(box.getAttribute('data-buddy')) : null;   // 히어로: 사진 위 토끼
    var say = (ext || box).querySelector('.say'), buddy = ext || box.querySelector('.buddy');
    var SAY = __SAY__;
    var STEPS = [300, 1000, 1700, 2500, 3500], HOLD = 7600, timers = [];
    function talk(text) {
      if (!say || !text) return;
      say.textContent = text;
      say.classList.remove('pop'); void say.offsetWidth; say.classList.add('pop');
      if (buddy) { buddy.classList.remove('hop'); void buddy.offsetWidth; buddy.classList.add('hop'); }
    }
    function line(ex, step) {
      if (step === 1) return ex.querySelector('.bw-mark:not(.is-verified)') ? SAY.marks : SAY.nomarks;
      if (step === 2) return ex.classList.contains('is-hold') ? SAY.hold : SAY.verdict;
      if (step === 3) return ex.querySelector('.cites') ? SAY.cites : '';
      if (step === 4) return ex.querySelector('.fix.is-hold') ? SAY.nofix : SAY.fix;
      return '';
    }
    function show(n) {
      timers.forEach(clearTimeout); timers = [];
      if (!document.body.contains(box)) return;
      exs.forEach(function (e, k) { e.classList.remove('on', 's1', 's2', 's3', 's4', 's5'); if (k === n) e.classList.add('on'); });
      dots.forEach(function (d, k) { d.classList.toggle('on', k === n); });
      talk(SAY.start);
      STEPS.forEach(function (ms, k) {
        timers.push(setTimeout(function () { exs[n].classList.add('s' + (k + 1)); talk(line(exs[n], k + 1)); }, ms));
      });
      timers.push(setTimeout(function () { show((n + 1) % exs.length); }, HOLD));
    }
    show(0);
  }

  // 4) 히어로 사진 마우스 시차(--mx · --my) 5) 상단 스크롤 진행선(--p) 6) 사진 띠 스크롤 시차(--py) 7) 지금 섹션의 메뉴 표시(.on)
  //    리스너는 문서에 한 번만 — Streamlit 이 노드를 다시 그려도 매번 다시 찾는다
  function scene() {
    if (window.__bwScene) return;
    window.__bwScene = true;
    var queued = false;
    function frame() {
      queued = false;
      var main = document.querySelector('[data-testid="stMain"]'), top = document.querySelector('.st-key-home_top');
      if (!main || !top) return;
      var max = main.scrollHeight - main.clientHeight, vh = window.innerHeight;
      top.style.setProperty('--p', max > 0 ? (main.scrollTop / max).toFixed(4) : '0');
      var current = '';
      document.querySelectorAll('.bw-h-sec[id]').forEach(function (s) { if (s.getBoundingClientRect().top < vh * 0.4) current = s.id; });
      document.querySelectorAll('.bw-h-nav a').forEach(function (a) { a.classList.toggle('on', a.getAttribute('href') === '#' + current); });
      if (reduce) return;
      var hero = document.querySelector('.st-key-home_hero');
      if (hero) {   // 히어로를 지나갈수록 0 → 1 (떠 있는 사물이 흩어진다)
        var hr = hero.getBoundingClientRect();
        hero.style.setProperty('--hs', Math.min(1, Math.max(0, -hr.top / Math.max(1, hr.height))).toFixed(3));
      }
      document.querySelectorAll('.bw-h-photo[data-par]').forEach(function (f) {
        var r = f.getBoundingClientRect();
        if (r.bottom < 0 || r.top > vh) return;
        f.style.setProperty('--py', (((r.top + r.height / 2) - vh / 2) / vh).toFixed(4));
      });
    }
    function ask() { if (!queued) { queued = true; requestAnimationFrame(frame); } }
    document.addEventListener('scroll', ask, { capture: true, passive: true });
    window.addEventListener('resize', ask);
    document.addEventListener('mousemove', function (e) {
      if (reduce) return;
      var hero = document.querySelector('.st-key-home_hero');
      if (!hero) return;
      var r = hero.getBoundingClientRect();
      if (e.clientY > r.bottom) return;
      hero.style.setProperty('--mx', ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
      hero.style.setProperty('--my', ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
    }, { passive: true });
    ask();
  }

  function run() { reveal(); demo(); scene(); }
  run();
  setTimeout(run, 250);
  setTimeout(run, 1200);
})();
</script>"""

MOTION_SCRIPT = _MOTION_JS.replace("__SAY__", json.dumps(SAY, ensure_ascii=False))


# ── 스포이드 방울 · 물결 ─────────────────────────────────────────────
# 홈 커서(세럼 스포이드)의 끝에서 방울이 맺혀 떨어진다 — 누르면 한 방울, 사진 위에 멈춰 있으면 1.9초마다(한 번 멈출 때 4방울까지).
# 사진(히어로 화보 · 사진 띠 · 피부 펼침면 · 마무리 띠)에 떨어지면 그 자리에서 물결이 퍼지고, 사진 위로 마우스를 움직이면 지나간 자리가 잔물결로 일렁인다.
# 물결은 사진 위에 얹은 WebGL 캔버스가 그린다 — 물결이 있을 때만 그리고 보인다(평소엔 원래 사진 그대로).
# 종이 바탕에 떨어지면 동그란 물결 테만 번진다. 마우스가 있는 기기에서만, 동작 줄이기면 아무것도 하지 않는다.
# 정화기 때문에 스크립트 안에서 꺾쇠 바로 뒤에 글자를 붙이지 않는다(비교는 꼭 띄어 쓴다).
_DRIP_JS = r"""<script>
(function () {
  if (window.__bwDrip) return;
  window.__bwDrip = true;
  var mm = window.matchMedia;
  if (!mm || mm('(prefers-reduced-motion: reduce)').matches || !mm('(hover: hover) and (pointer: fine)').matches) return;

  var MAXW = 12, LIFE = 2.6;
  var VS = 'attribute vec2 a; varying vec2 v; void main() { v = vec2(a.x * 0.5 + 0.5, 0.5 - a.y * 0.5); gl_Position = vec4(a, 0.0, 1.0); }';
  var FS = [
    'precision mediump float;',
    'uniform sampler2D u_tex; uniform vec2 u_size; uniform vec4 u_map; uniform vec4 u_w[12]; uniform int u_n;',
    'varying vec2 v;',
    'void main() {',
    '  vec2 p = v * u_size; vec2 disp = vec2(0.0); float lit = 0.0;',
    '  for (int i = 0; i != 12; i++) {',
    '    if (i == u_n) break;',
    '    vec4 w = u_w[i]; vec2 d = p - w.xy; float r = length(d) + 0.0001;',
    '    float x = r - w.z * 230.0; float s = 14.0 + w.z * 36.0;',
    '    float env = exp(-x * x / (2.0 * s * s)) * exp(-w.z * 1.6) * min(1.0, w.z * 8.0);',
    '    float h = sin(x * 0.16) * env * w.w;',
    '    disp += d / r * h; lit += cos(x * 0.16) * env * w.w;',
    '  }',
    '  vec2 t = (p + disp) / u_size * u_map.xy + u_map.zw;',
    '  vec4 c = texture2D(u_tex, clamp(t, vec2(0.001), vec2(0.999)));',
    '  c.rgb += lit * 0.012;',
    '  gl_FragColor = vec4(c.rgb, 1.0);',
    '}'
  ].join(' ');

  var surfaces = [];
  function onHome() { return !!document.querySelector('.st-key-home_top'); }

  function shader(gl, type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  }
  function attach() {
    surfaces = surfaces.filter(function (s) {
      if (s.el.isConnected) return true;
      s.cv.remove();
      var x = s.gl.getExtension('WEBGL_lose_context'); if (x) x.loseContext();
      return false;
    });
    document.querySelectorAll('.bw-h-scene .photo, .bw-h-photo .img, .bw-h-pic').forEach(function (el) {
      if (el.hasAttribute('data-rip')) return;
      el.setAttribute('data-rip', '1');
      var band = el.tagName !== 'IMG';
      var src = band ? (el.style.backgroundImage.match(/url\(["']?([^"')]+)/) || [])[1] : (el.currentSrc || el.src);
      if (!src) return;
      var cv = document.createElement('canvas');
      cv.className = 'bw-rip';
      cv.setAttribute('aria-hidden', 'true');
      var gl = cv.getContext('webgl', { alpha: false, antialias: false });
      if (!gl) return;
      var vs = shader(gl, gl.VERTEX_SHADER, VS), fs = shader(gl, gl.FRAGMENT_SHADER, FS);
      if (!vs || !fs) return;
      var pr = gl.createProgram();
      gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return;
      gl.useProgram(pr);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      var la = gl.getAttribLocation(pr, 'a');
      gl.enableVertexAttribArray(la); gl.vertexAttribPointer(la, 2, gl.FLOAT, false, 0, 0);
      var s = { el: el, cv: cv, gl: gl, band: band, waves: [], on: false, ready: false,
                u: { size: gl.getUniformLocation(pr, 'u_size'), map: gl.getUniformLocation(pr, 'u_map'),
                     w: gl.getUniformLocation(pr, 'u_w'), n: gl.getUniformLocation(pr, 'u_n') } };
      var im = new Image();
      im.onload = function () {
        s.iw = im.naturalWidth; s.ih = im.naturalHeight;
        gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, im);
        s.ready = true;
      };
      im.src = src;
      cv.addEventListener('webglcontextlost', function () { s.ready = false; cv.remove(); });
      if (band) el.appendChild(cv); else el.insertAdjacentElement('afterend', cv);
      surfaces.push(s);
    });
  }

  // 화면 좌표 → 사진 상자 안 좌표. 히어로 사진은 천천히 커지는 중이라(scale · transform-origin, CSS 값을 그대로 읽는다) 그만큼 되돌린다
  function local(s, x, y) {
    var w = s.el.offsetWidth, h = s.el.offsetHeight, lx, ly;
    if (s.band) {
      var r = s.el.getBoundingClientRect(); lx = x - r.left; ly = y - r.top;
    } else {
      var cs = getComputedStyle(s.el), R = s.el.parentElement.getBoundingClientRect(), k = parseFloat(cs.scale) || 1;
      var o = cs.transformOrigin.split(' '), ox = parseFloat(o[0]) || 0, oy = parseFloat(o[1]) || 0;
      lx = (x - R.left - ox) / k + ox; ly = (y - R.top - oy) / k + oy;
    }
    var edge = s.band ? 0 : 0.22;   // 히어로 사진 왼쪽 22% 는 종이색으로 흐려지는 자리
    return { x: lx, y: ly, w: w, h: h, ok: w > 0 && lx >= w * edge && lx <= w && ly >= 0 && ly <= h };
  }
  function cover(s) {   // CSS cover 와 같은 자리 — 사진 띠는 스크롤 시차(--py)만큼 위아래로 밀려 있다
    var w = s.w, h = s.h, k = Math.max(w / s.iw, h / s.ih), dw = s.iw * k, dh = s.ih * k, py = 0.5;
    if (s.band) { var f = s.el.closest('[data-par]'); py = 0.5 + (parseFloat(f && f.style.getPropertyValue('--py')) || 0) * 0.4; }
    return [w / dw, h / dh, -(w - dw) * 0.5 / dw, -(h - dh) * py / dh];
  }
  function wave(s, x, y, amp) {
    if (!s.ready) return;
    s.waves.push({ x: x, y: y, t0: performance.now(), a: amp });
    if (s.waves.length > MAXW) s.waves.shift();
    if (!s.on) { s.on = true; requestAnimationFrame(function () { draw(s); }); }
  }
  var buf = new Float32Array(MAXW * 4);
  function draw(s) {
    var now = performance.now();
    s.waves = s.waves.filter(function (w) { return (now - w.t0) / 1000 < LIFE; });
    if (!s.waves.length || !s.el.isConnected || !s.ready) { s.on = false; s.cv.classList.remove('on'); return; }
    var gl = s.gl, cv = s.cv, dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    s.w = s.el.offsetWidth; s.h = s.el.offsetHeight;
    var W = Math.max(1, Math.round(s.w * dpr)), H = Math.max(1, Math.round(s.h * dpr));
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    gl.viewport(0, 0, W, H);
    gl.uniform2f(s.u.size, s.w, s.h);
    gl.uniform4fv(s.u.map, cover(s));
    buf.fill(0);
    s.waves.forEach(function (w, i) { buf[i * 4] = w.x; buf[i * 4 + 1] = w.y; buf[i * 4 + 2] = (now - w.t0) / 1000; buf[i * 4 + 3] = w.a; });
    gl.uniform4fv(s.u.w, buf); gl.uniform1i(s.u.n, s.waves.length);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    if (!s.band) cv.style.scale = getComputedStyle(s.el).scale;
    cv.classList.add('on');
    requestAnimationFrame(function () { draw(s); });
  }
  function hit(x, y) {
    for (var i = 0; i != surfaces.length; i++) { var L = local(surfaces[i], x, y); if (L.ok) return { s: surfaces[i], L: L }; }
    return null;
  }

  // 방울: 커서 끝(핫스팟)에서 맺혀 → 늘어나 떨어지고 → 14px 아래에 닿는다
  function drop(x, y) {
    var d = document.createElement('i');
    d.className = 'bw-dropl'; d.style.left = x + 'px'; d.style.top = y + 'px';
    document.body.appendChild(d);
    setTimeout(function () { land(x, y + 14); }, 640);
    setTimeout(function () { d.remove(); }, 950);
  }
  function land(x, y) {
    if (!onHome()) return;
    attach();
    var h = hit(x, y);
    if (h) { wave(h.s, h.L.x, h.L.y, 11); return; }
    var r = document.createElement('i');
    r.className = 'bw-ring'; r.style.left = x + 'px'; r.style.top = y + 'px';
    document.body.appendChild(r);
    setTimeout(function () { r.remove(); }, 1400);
  }

  var last = { x: -1, y: -1 }, wake = { x: -1e4, y: -1e4, t: 0 }, idle = 0, rests = 0;
  function rest() {
    if (!onHome() || document.hidden || rests >= 4) return;
    attach();
    if (!hit(last.x, last.y)) return;
    rests += 1;
    drop(last.x, last.y);
    idle = setTimeout(rest, 1900);
  }
  document.addEventListener('mousemove', function (e) {
    if (!onHome()) return;
    last.x = e.clientX; last.y = e.clientY;
    clearTimeout(idle); rests = 0; idle = setTimeout(rest, 750);
    var now = performance.now();
    if (now - wake.t < 45 || Math.abs(e.clientX - wake.x) + Math.abs(e.clientY - wake.y) < 30) return;
    wake.x = e.clientX; wake.y = e.clientY; wake.t = now;
    attach();
    var h = hit(e.clientX, e.clientY);
    if (h) wave(h.s, h.L.x, h.L.y, 2.4);
  }, { passive: true });
  document.addEventListener('mousedown', function (e) {
    if (e.button === 0 && onHome()) drop(e.clientX, e.clientY);
  }, { passive: true });
  document.addEventListener('mouseleave', function () { clearTimeout(idle); });
})();
</script>"""

DRIP_SCRIPT = _DRIP_JS
