"""
[app/components/panels.py]
오른쪽 「근거 · RAG」 패널. 모두 데이터 → HTML 문자열 순수 함수다.

구성 (답변이 있을 때):
  rag_header()     — 무엇을 검색해 몇 건을 근거로 썼는가 (검색어 · 권위별 건수)
  ladder_block()   — 보유 실증으로 쓸 수 있는 표현 단계 (데모 핵심: 실증 해제 → Lv2→Lv1)
  evidence_list()  — 번호 붙은 근거 조항. 번호는 가운데 답변의 [n] 과 같다. 스니펫 안의 관련 표현을 표시한다
  documents_list() — 근거가 나온 원문 문서
  process_list()   — 검토 파이프라인 단계와 시간
답변이 없을 때: rag_empty() — 검색 대상 자료와 동작 방식.
"""
from __future__ import annotations

import re

from app.components.icons import icon
from app.components.layout import esc, seconds
from app.components.theme import AUTHORITY

_DOC_ICON = {"법령": ("gavel", "k-law"), "고시": ("description", "k-law"), "지침": ("menu_book", ""), "사례": ("newspaper", "k-case")}


def _mark_terms(snippet: str, terms: list[str]) -> str:
    """스니펫을 이스케이프하고, 답변의 문제 표현이 그대로 나오면 표시한다."""
    out = esc(snippet)
    for t in sorted({t for t in terms if t and len(t) >= 2}, key=len, reverse=True):
        out = re.sub(re.escape(esc(t)), lambda m: f"<mark>{m.group(0)}</mark>", out)
    return out


def rag_header(resp: dict) -> str:
    """패널 머리: 근거 n건 · 권위별 건수 · 검색에 쓴 표현."""
    cites = resp["result"].get("citations", [])
    counts: dict[str, int] = {}
    for c in cites:
        name = AUTHORITY.get(int(c.get("authority", 4)), "사례")
        counts[name] = counts.get(name, 0) + 1
    by_kind = " · ".join(f"{k} {counts[k]}" for k in ("법령", "고시", "지침", "사례") if counts.get(k))
    terms: dict[str, list[int]] = {}
    for h in resp.get("ui", {}).get("highlights", []):
        if h.get("kind") != "verified" and h.get("text"):
            terms.setdefault(h["text"], [])
            terms[h["text"]] += [int(n) for n in h.get("cites", []) if int(n) not in terms[h["text"]]]
    codes = "".join(f'<code data-cites="{",".join(map(str, ns))}">{esc(t)}</code>' if ns else f"<code>{esc(t)}</code>"
                    for t, ns in terms.items())
    query = f'<div class="bw-rag-q"><span class="k">검색한 표현</span>{codes}</div>' if terms else ""
    return (f'<div class="bw-pane-h"><h3>{icon("menu_book", 20)}근거</h3><span class="bw-pane-meta">RAG</span></div>'
            f'<p class="bw-pane-sub">이번 답변이 참고한 규정 문서입니다. 번호는 답변의 [n] 과 같습니다.</p>'
            f'<div class="bw-rag-stat"><b>{len(cites)}</b><span>건 검색{(" · " + by_kind) if by_kind else ""}</span></div>{query}')


def ladder_block(resp: dict, *, fresh: bool = False) -> str:
    """표현 단계: Lv0 · Lv1 · Lv2 · 불가 네 칸에 제안·원문 위치를 표시한다. fresh 면 막대가 차오른다(처음 한 번)."""
    ladder = resp.get("ui", {}).get("ladder")
    if not ladder or not ladder.get("rungs"):
        return ""
    cells = []
    for r in ladder["rungs"]:
        lv = r["lv"]
        is_x = lv == "X"
        cls = "x" if is_x else ("reach" if lv == ladder.get("proposal") else ("owned" if r.get("owned") else ""))
        marks = []
        if lv == ladder.get("proposal"):
            marks.append('<span class="mk is-prop">제안</span>')
        if lv == ladder.get("original"):
            marks.append('<span class="mk is-orig">원문</span>')
        cells.append(f'<div class="bw-rung {cls}" title="{esc(r.get("text", ""))} — {esc(r.get("needs", ""))}">'
                     f'<span class="bar"></span><span class="lv">{"불가" if is_x else f"Lv{lv}"}</span>'
                     f'{"".join(marks) or "<span class=mk></span>"}</div>')
    reach = ladder.get("reachable")
    note = f"보유 실증으로 Lv{reach}까지 쓸 수 있습니다." if reach is not None else ""
    return (f'<div class="bw-block"><div class="bw-block-h"><span>표현 단계 · {esc(ladder.get("claim", ""))}</span>'
            f'<span class="bw-pane-meta">실증 기준</span></div>'
            f'<div class="bw-ladder{" is-arrive" if fresh else ""}">{"".join(cells)}</div><p class="bw-ladder-note">{esc(note)}</p></div>')


def evidence_list(resp: dict, *, fresh: bool = False) -> str:
    """번호 붙은 근거 조항 목록 (패널의 주인공). fresh 면 위에서부터 차례로 들어온다(처음 한 번)."""
    cites = resp["result"].get("citations", [])
    if not cites:
        return ('<div class="bw-pane-empty">이 판단에 인용한 조항이 없습니다. '
                '위반 소지가 없거나 근거가 부족한 경우입니다.</div>')
    hits_by_cite: dict[int, list[str]] = {}
    for h in resp.get("ui", {}).get("highlights", []):
        if h.get("kind") == "verified":
            continue
        for n in h.get("cites", []):
            hits_by_cite.setdefault(int(n), []).append(h.get("text", ""))
    items = []
    for i, c in enumerate(cites, start=1):
        auth = int(c.get("authority", 4))
        snippet = c.get("content_snippet") or ""
        hits = list(dict.fromkeys(hits_by_cite.get(i, [])))
        more = (f'<details><summary>전문 보기</summary><div class="bw-cite-full">{esc(snippet)}</div></details>'
                if len(snippet) > 120 else "")
        hit_html = (f'<div class="bw-hits">관련 표현 {" · ".join("‘" + esc(t) + "’" for t in hits)}</div>' if hits else "")
        items.append(
            f'<li class="bw-cite" data-n="{i}"><span class="bw-num">{i}</span><div>'
            f'<div class="bw-cite-t"><b>{esc(c.get("source", ""))}</b> <span class="art">{esc(c.get("article", ""))}</span>'
            f'<span class="bw-auth{" a1" if auth == 1 else ""}">{AUTHORITY.get(auth, "")}</span></div>'
            f'<p class="bw-cite-q">{_mark_terms(snippet, hits)}</p>{more}{hit_html}</div></li>'
        )
    return f'<ol class="bw-cites{" is-arrive" if fresh else ""}">{"".join(items)}</ol>'


def documents_list(docs: list[dict]) -> str:
    """근거가 나온 원문 문서 목록."""
    if not docs:
        return '<div class="bw-pane-empty">연결된 원문 문서가 없습니다.</div>'
    rows = []
    for d in docs:
        ic, cls = _DOC_ICON.get(d.get("kind", ""), ("description", ""))
        when = d.get("version") or d.get("date") or ""
        meta = " · ".join(x for x in (d.get("org", ""), when) if x)
        summary = f'<div class="bw-doc-s">{esc(d["summary"])}</div>' if d.get("summary") else ""
        rows.append(
            f'<li class="bw-docrow"><span class="bw-doc-ic {cls}">{icon(ic, 17)}</span>'
            f'<div><div class="bw-doc-t">{esc(d.get("title", ""))}</div><div class="bw-doc-m">{esc(meta)}</div>{summary}</div>'
            f'<span class="bw-auth">{esc(d.get("kind", ""))}</span></li>'
        )
    return f'<ul class="bw-docs">{"".join(rows)}</ul>'


def process_list(resp: dict) -> str:
    """검토 과정: LangGraph 단계와 단계별 시간 (ui 확장이 없으면 총 시간만)."""
    steps = resp.get("ui", {}).get("steps") or []
    t = resp.get("timing", {})
    if not steps:
        return (f'<div class="bw-pane-empty">이 응답에는 단계별 기록이 없습니다. '
                f'총 응답 시간 {seconds(t.get("total_ms"))}.</div>')
    items = []
    for s in steps:
        skip = s.get("status") in ("skip", "pending")
        ic = icon("remove", 14) if skip else icon("check", 14)
        ms = f'<span class="ms">{seconds(s.get("ms"))}</span>' if s.get("ms") else '<span class="ms"></span>'
        name = esc(s.get("name", "")) + (" (건너뜀)" if s.get("status") == "skip" else "")
        items.append(f'<li class="{"is-skip" if skip else ""}">{ic}<span>{name}</span>{ms}</li>')
    return (f'<ul class="bw-steps">{"".join(items)}</ul>'
            f'<p class="bw-pane-note">총 {seconds(t.get("total_ms"))} · 하이브리드 검색(BM25 + 벡터)으로 조항을 찾고, '
            '규칙 검사와 AI 판정 뒤 제안 문구를 다시 검증합니다.</p>')


def kb_grid(stats: dict) -> str:
    """검색 대상 자료(지식베이스) 수치."""
    def cell(n, unit, label):
        return f'<div><div class="n">{n}<small>{unit}</small></div><div class="l">{label}</div></div>'
    ing = stats.get("ingredients")
    return ('<div class="bw-kb">'
            + cell(stats.get("laws", 0), "종", "법령 · 고시")
            + cell(stats.get("guidelines", 0), "종", "표시·광고 관리 지침")
            + cell(stats.get("cases", 0), "건", "식약처 적발 사례")
            + cell(f"{ing:,}" if isinstance(ing, int) else "-", "개", "원료 성분 사전")
            + '</div>')


def rag_empty(stats: dict, docs: list[dict]) -> str:
    """답변이 없을 때 오른쪽: 무엇을 근거로 답하는지 미리 보여 준다."""
    laws = [d for d in docs if d.get("kind") != "사례"]
    steps = ('<ol class="bw-howto">'
             '<li><span><b>근거 검색</b> 문구와 관련된 법령·고시·지침·적발 사례 조항을 하이브리드 검색으로 찾습니다.</span></li>'
             '<li><span><b>판정</b> 금지 표현 규칙과 AI 판정을 함께 써서 사용 가능 · 실증 필요 · 수정 필요로 나눕니다.</span></li>'
             '<li><span><b>교정</b> 내 제품의 보유 실증 범위 안에서 쓸 수 있는 문구를 제안하고 다시 검증합니다.</span></li></ol>')
    docs_block = (f'<div class="bw-block"><div class="bw-block-h"><span>수집 문서</span>'
                  f'<span class="bw-pane-meta">{len(laws)}건</span></div>{documents_list(laws)}</div>' if laws else "")
    return (f'<div class="bw-pane-h"><h3>{icon("menu_book", 20)}근거</h3><span class="bw-pane-meta">RAG</span></div>'
            '<p class="bw-pane-sub">답변이 참고한 규정 문서가 여기에 번호와 함께 표시됩니다.</p>'
            f'<div class="bw-block"><div class="bw-block-h"><span>검색 대상 자료</span></div>{kb_grid(stats)}</div>'
            f'<div class="bw-block"><div class="bw-block-h"><span>이렇게 답합니다</span></div>{steps}</div>{docs_block}')


def corpus_card(stats: dict, docs: list[dict]) -> str:
    """규정 라이브러리 오른쪽: 검색 대상 자료 + 수집 문서."""
    laws = [d for d in docs if d.get("kind") != "사례"]
    return (f'<div class="bw-pane-h"><h3>{icon("library_books", 20)}검색 대상 자료</h3></div>'
            f'<div class="bw-block">{kb_grid(stats)}<p class="bw-pane-note">검토 답변은 이 자료에서 관련 조항을 찾아 근거로 씁니다.</p></div>'
            f'<div class="bw-block"><div class="bw-block-h"><span>수집 문서</span><span class="bw-pane-meta">{len(laws)}건</span></div>'
            f'{documents_list(laws)}</div>')
