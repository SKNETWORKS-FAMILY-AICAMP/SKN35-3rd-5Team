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
from functools import lru_cache
from pathlib import Path

from app.components.brand import avatar_img, character_img, lockup_img
from app.components.cards import highlighted, tag
from app.components.icons import icon
from app.components.layout import esc
from app.components.theme import status_of
from app.services import mock
from app.services.contract import verdict_of
from app.services.data_sources import case_title

_LANDING_DIR = Path(__file__).resolve().parents[1] / "static" / "landing"

SECTIONS = [("bw-problem", "문제"), ("bw-how", "검토 방식"), ("bw-features", "기능"), ("bw-sources", "근거 자료")]

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
    return f'<{tag_name} class="bw-h-display">{text_html}</{tag_name}>'


def _head(no: str, eyebrow: str, title_html: str, desc: str = "") -> str:
    p = f"<p>{esc(desc)}</p>" if desc else ""
    return (f'<div class="bw-h-sh rv"><div class="ey"><span class="no">{no}</span>{esc(eyebrow)}</div>'
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
             f'<span class="pic">{character_img(228)}</span></div>')
    return ('<div class="bw-h bw-h-demo" aria-label="검토 예시">' + buddy + '<div class="card">'
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
    return (f'<section id="bw-problem" class="bw-h bw-h-sec">'
            + _head("01", "문제", "광고 문구 한 줄이<br><em>행정처분</em>으로 이어집니다",
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
            + _head("02", "검토 방식", "근거를 먼저 찾고,<br>그 근거로 <em>판정</em>합니다",
                    "답변에는 근거 조항 번호가 붙습니다. 번호를 누르면 오른쪽에 그 조항이 열립니다.")
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
            + _head("03", "기능", "문구 하나부터<br><em>상세페이지</em> 전체까지")
            + f'<ul class="bw-h-features">{lis}</ul></section>')


# ── 04 근거 자료 ────────────────────────────────────────────────────
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
            + _head("04", "근거 자료", "답변의 근거는<br>이 <em>문서들</em>에서 찾습니다",
                    "법령은 국가법령정보센터, 고시 · 지침 · 사례는 식약처 공개 자료에서 받았습니다.")
            + f'<ul class="bw-h-stats rv">{cells}</ul><ul class="bw-h-docs rv">{doc_cells}</ul></section>')


# ── 마지막 안내 · 푸터 ──────────────────────────────────────────────
def cta_text() -> str:
    return (f'<div class="bw-h bw-h-cta"><span class="pic">{character_img(136, alt="")}</span>'
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
    var box = document.querySelector('.bw-h-demo:not([data-run])');
    if (!box) return;
    box.setAttribute('data-run', '1');
    if (reduce) return;
    var exs = box.querySelectorAll('.ex'), dots = box.querySelectorAll('.dots i');
    var say = box.querySelector('.say'), buddy = box.querySelector('.buddy');
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

  function run() { reveal(); demo(); }
  run();
  setTimeout(run, 250);
  setTimeout(run, 1200);
})();
</script>"""

MOTION_SCRIPT = _MOTION_JS.replace("__SAY__", json.dumps(SAY, ensure_ascii=False))
