"""
[app/views/library.py]
규정 라이브러리 — 검토 근거로 쓰는 법령·고시·관리지침·적발 사례를 찾아본다.
조항 검색은 백엔드 GET /search (하이브리드 검색) 와 같은 모양의 결과를 쓴다.
"""
from __future__ import annotations

import re

import streamlit as st

from app.components.icons import icon
from app.components.layout import esc, html, page_header
from app.components.panels import corpus_card
from app.components.theme import AUTHORITY, inject_css
from app.services import backend

QUICK = ["피부 재생", "실증자료 요건", "탈모 표현", "최고 1위 표현", "기능성화장품 오인"]

health = st.session_state["bw_health"]
inject_css("pages")


def _set_query(q: str) -> None:
    st.session_state["bw_lib_q"] = q


def _mark(text: str, terms: list[str]) -> str:
    """검색어가 나온 자리를 표시한다 (이스케이프 후)."""
    out = esc(text)
    for t in sorted({t for t in terms if t and len(t) >= 2}, key=len, reverse=True):
        out = re.sub(re.escape(esc(t)), lambda m: f'<span class="bw-hl">{m.group(0)}</span>', out)
    return out


def _clean(text: str) -> str:
    return re.sub(r"\s*<(?:개정|신설|전문개정|본조신설|제목개정)[^>]*>", "", text or "")


def _search_tab() -> None:
    with st.container(horizontal=True, key="libsearch", vertical_alignment="center"):
        q = st.text_input("규정 검색", key="bw_lib_q", placeholder="찾고 싶은 표현이나 조항을 입력하세요 (예: 피부 재생, 실증자료)",
                          label_visibility="collapsed", icon=":material/search:")
        scope = st.segmented_control("적용 범위", ["공통", "일반", "기능성"], default="공통", key="bw_lib_scope",
                                     label_visibility="collapsed")
    with st.container(horizontal=True, key="libex"):
        for i, s in enumerate(QUICK):
            st.button(s, key=f"libq_{i}", on_click=_set_query, args=(s,))

    q = (q or "").strip()
    if not q:
        html('<div class="bw-results" style="margin-top:12px"><div class="bw-sents-empty">'
             '검색어를 입력하면 법령·고시·관리지침·적발 사례에서 관련 조항을 찾아 근거로 보여 줍니다.</div></div>')
        return
    try:
        hits = backend.search_rules(q, scope=scope or "공통", limit=10)
    except backend.BackendError as err:
        html(f'<div class="bw-error" style="margin-top:12px">{icon("error", 18)}<div><b>검색하지 못했습니다.</b> {esc(err.message)}</div></div>')
        return
    html(f'<div class="bw-block-h" style="margin-top:16px"><h3>‘{esc(q)}’ 검색 결과</h3>'
         f'<span>{len(hits)}건 · 권위 높은 순 가중</span></div>')
    if not hits:
        html('<div class="bw-results"><div class="bw-sents-empty">일치하는 조항이 없습니다. 다른 표현으로 찾아보세요.</div></div>')
        return
    terms = q.split()
    rows = []
    for h in hits:
        md = h.get("metadata", {})
        auth = int(md.get("authority", 4) or 4)
        matched = md.get("matched_terms") or terms
        rows.append(
            f'<div class="bw-result"><div class="bw-result-h"><b>{esc(md.get("source", ""))}</b>'
            f'<span class="art">{esc(md.get("article", ""))}</span>'
            f'<span class="bw-auth{" a1" if auth == 1 else ""}">{AUTHORITY.get(auth, md.get("doc_type", ""))}</span>'
            f'<span class="date">{esc(md.get("effective_date") or "")}</span></div>'
            f'<p>{_mark(_clean(h.get("content", "")), matched)}</p>'
            f'<div class="bw-result-id">{esc(md.get("id", ""))}</div></div>'
        )
    html(f'<div class="bw-results">{"".join(rows)}</div>')


def _banned_tab() -> None:
    f = st.text_input("금지 표현 거르기", key="bw_lib_ban", placeholder="표현으로 거르기 (예: 재생, 탈모, 여드름)",
                      label_visibility="collapsed", icon=":material/filter_list:")
    rows = backend.guide_rows()
    f = (f or "").strip()
    if f:
        rows = [r for r in rows if f in (r.get("text") or "") or f in (r.get("category") or "") or f in (r.get("note") or "")]
    if not rows:
        html('<div class="bw-results"><div class="bw-sents-empty">해당하는 금지 표현이 없습니다.</div></div>')
        return
    body, prev = [], None
    for r in rows:
        cat = r.get("category") or ""
        first = cat != prev
        body.append(f'<tr class="{"grp" if first and prev is not None else ""}"><td class="cat">{esc(cat) if first else ""}</td>'
                    f'<td class="expr">{esc(r.get("text", ""))}</td><td>{esc(r.get("note") or "")}</td>'
                    f'<td class="pg">{r.get("page") or ""}쪽</td></tr>')
        prev = cat
    html(f'<div class="bw-block-h" style="margin-top:10px"><h3>화장품 표시·광고 관리 지침 [별표 1] 금지 표현</h3>'
         f'<span>{len(rows)}개 · 식약처 2025-01-21</span></div>'
         f'<table class="bw-table"><thead><tr><th>구분</th><th>금지 표현</th><th>비고</th><th></th></tr></thead>'
         f'<tbody>{"".join(body)}</tbody></table>')


def _cases_tab() -> None:
    cases = backend.enforcement_trends()
    top = max((c.get("cosmetics_count") or c.get("count") or 0) for c in cases) or 1
    rows = []
    for c in cases:
        n = c.get("cosmetics_count") or c.get("count") or 0
        scope = "" if c.get("cosmetics_count") in (None, c.get("count")) else f'전체 {c["count"]}건 중 화장품'
        bd = "".join(f'<span>{esc(b["label"])} <b>{b["pct"]:.0f}%</b></span>' for b in (c.get("breakdown") or []))
        link = c.get("source_url")
        title = (f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(c.get("full_title") or c.get("title"))}</a>'
                 if link else esc(c.get("full_title") or c.get("title")))
        rows.append(f'<div class="bw-case"><span class="d">{esc(c.get("date", ""))}</span>'
                    f'<div><div class="t">{title}</div><div class="s">{esc(c.get("file", ""))}</div>'
                    f'{"<div class=bd>" + bd + "</div>" if bd else ""}</div>'
                    f'<div class="cnt"><b>{n}건</b><small>{esc(scope) or "화장품"}</small>'
                    f'<span class="bar"><i style="width:{n / top * 100:.0f}%"></i></span></div></div>')
    html(f'<div class="bw-block-h" style="margin-top:10px"><h3>식약처 부당광고 적발 사례</h3>'
         f'<span>{len(cases)}건 · 보도자료 원문 기준</span></div><div class="bw-cases">{"".join(rows)}</div>')


center, right = st.columns([1.72, 1], gap="large")

with center, st.container(key="center"):
    page_header("규정 · 가이드라인", "검토 근거로 쓰는 법령·고시·관리지침·적발 사례를 찾아봅니다. 답변의 근거 번호도 여기 있는 원문에서 나옵니다.",
                health=health)
    with st.container(key="pagebody"):
        tab_search, tab_banned, tab_cases = st.tabs(["조항 검색", "금지 표현 사전", "적발 사례"], key="bw_lib_tab")
        with tab_search:
            _search_tab()
        with tab_banned:
            _banned_tab()
        with tab_cases:
            _cases_tab()

with right:
    with st.container(key="aside"):
        html(corpus_card(backend.kb_stats(), backend.all_reference_documents()))
