"""
[app/components/panels.py]
오른쪽 근거 패널의 카드들. 모두 데이터 → HTML 문자열 순수 함수다.

순서: 검토 요약 → 근거(검색된 조항, 번호는 가운데 답변의 [n] 과 같다) → 참조 문서 → 검토 과정.
결과가 없을 때는 검색 대상 자료와 검토 방식을 보여 RAG 구조를 드러낸다.
"""
from __future__ import annotations

from app.components.cards import status_tag, tag
from app.components.icons import icon
from app.components.layout import esc, seconds
from app.components.theme import AUTHORITY, VIOLATION_LABEL
from app.services.contract import verdict_of

_DOC_ICON = {"법령": ("gavel", "k-law"), "고시": ("description", "k-law"), "지침": ("menu_book", ""), "사례": ("newspaper", "k-case")}


def _card(title: str, icon_name: str, body: str, *, right: str = "") -> str:
    return (f'<div class="bw-card"><div class="bw-card-h"><h3>{icon(icon_name, 18)}{esc(title)}</h3>{right}</div>'
            f'{body}</div>')


def _ladder(ladder: dict | None) -> str:
    """표현 단계 축약: Lv0 · Lv1 · Lv2 · 불가 네 칸에 제안·원문 위치를 표시한다."""
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
        mk = "".join(marks) or '<span class="mk"></span>'
        name = "불가" if is_x else f"Lv{lv}"
        cells.append(f'<div class="bw-rung {cls}" title="{esc(r.get("text", ""))} — {esc(r.get("needs", ""))}">'
                     f'<span class="bar"></span><span class="lv">{name}</span>{mk}</div>')
    reach = ladder.get("reachable")
    note = (f'보유 실증으로 Lv{reach}까지 쓸 수 있습니다.' if reach is not None else "")
    return f'<div class="bw-ladder">{"".join(cells)}</div><div class="bw-ladder-note">{esc(note)}</div>'


def summary_card(resp: dict, context: dict) -> str:
    """검토 요약: 전반적 판단 · 주요 이슈 · 제안 방향 · 표현 단계 · 검토 기준."""
    result, ui = resp["result"], resp.get("ui", {})
    verdict = verdict_of(result)
    summary = ui.get("summary") or result.get("review_notes") or "-"

    labels = []
    ordered = sorted(ui.get("highlights", []), key=lambda h: (not h.get("decisive"), -(h.get("level") or 0), h.get("start", 0)))
    for h in ordered:
        if h.get("kind") == "verified":
            continue
        label = h.get("label") or VIOLATION_LABEL.get(h.get("violation_type") or "", "")
        if label and label not in [x[0] for x in labels]:
            labels.append((label, "risk" if h.get("level") == 2 else "caution"))
    if not labels and result.get("violation_type") not in (None, "없음"):
        labels.append((VIOLATION_LABEL.get(result["violation_type"], result["violation_type"]),
                       "risk" if result.get("level") == 2 else "caution"))
    issues = "".join(tag(l, t) for l, t in labels) or '<span class="bw-muted">없음</span>'

    if verdict == "판단보류":
        direction = "관련 근거를 보강하거나 RA 담당자의 검토를 받은 뒤 다시 판단합니다."
    elif verdict == "가능":
        direction = "현재 표현을 그대로 쓸 수 있습니다."
    else:
        source = ui.get("suggestion_source", "")
        direction = ui.get("direction") or (f"보유 실증 {source} 범위 안에서 수치와 출처를 밝혀 표현합니다." if source
                                            else "근거가 있는 범위 안에서 효능을 낮춰 표현합니다.")

    rows = [("전반적 판단", esc(summary)), ("주요 이슈", f'<div class="bw-tags">{issues}</div>'), ("제안 방향", esc(direction))]
    ladder = _ladder(ui.get("ladder"))
    if ladder:
        rows.append((f'표현 단계<small>{esc(ui["ladder"].get("claim", ""))}</small>', ladder))
    ev = context.get("evidence_on", 0)
    rows.append(("검토 기준", f'{esc(context.get("product_name", ""))}<br><span class="bw-muted">'
                             f'{esc(context.get("category_label", ""))} · 실증 {ev}건 반영</span>'))
    kv = "".join(f'<div class="k">{k}</div><div class="v">{v}</div>' for k, v in rows)
    return _card("검토 요약", "fact_check", f'<div class="bw-kv">{kv}</div>', right=status_tag(verdict))


def evidence_card(resp: dict) -> str:
    """근거: 검색·정리된 조항 목록. 번호는 가운데 답변의 위첨자 번호와 같다."""
    cites = resp["result"].get("citations", [])
    if not cites:
        body = '<p class="bw-card-note">이 판단에 인용한 조항이 없습니다. 위반 소지가 없거나 근거가 부족한 경우입니다.</p>'
        return _card("근거", "menu_book", body)
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
        more = (f'<details><summary>전문 보기</summary><div class="bw-cite-full">{esc(snippet)}</div></details>'
                if len(snippet) > 110 else "")
        hits = hits_by_cite.get(i)
        hit_html = (f'<div class="bw-hits">관련 표현 {" · ".join("‘" + esc(t) + "’" for t in dict.fromkeys(hits))}</div>'
                    if hits else "")
        items.append(
            f'<div class="bw-cite"><span class="bw-num">{i}</span><div>'
            f'<div class="bw-cite-t">{esc(c.get("source", ""))} <span class="art">{esc(c.get("article", ""))}</span>'
            f'<span class="bw-auth{" a1" if auth == 1 else ""}">{AUTHORITY.get(auth, "")}</span></div>'
            f'<div class="bw-cite-q">“{esc(snippet)}”</div>{more}{hit_html}</div></div>'
        )
    right = f'<span class="bw-tag is-pass is-sm">{len(cites)}개 근거로 검토했어요</span>'
    return _card("근거", "menu_book", f'<div class="bw-cites">{"".join(items)}</div>', right=right)


def references_card(docs: list[dict], *, title: str = "참조 문서") -> str:
    """근거가 나온 원문 문서 목록."""
    if not docs:
        return ""
    rows = []
    for d in docs:
        ic, cls = _DOC_ICON.get(d.get("kind", ""), ("description", ""))
        when = d.get("version") or d.get("date") or ""
        meta = " · ".join(x for x in (d.get("org", ""), when) if x)
        summary = f'<div class="bw-doc-s">{esc(d["summary"])}</div>' if d.get("summary") else ""
        rows.append(
            f'<div class="bw-doc"><span class="bw-doc-ic {cls}">{icon(ic, 17)}</span>'
            f'<div><div class="bw-doc-t">{esc(d.get("title", ""))}</div><div class="bw-doc-m">{esc(meta)}</div>{summary}</div>'
            f'<span class="bw-auth">{esc(d.get("kind", ""))}</span></div>'
        )
    return _card(title, "folder_open", f'<div class="bw-docs">{"".join(rows)}</div>',
                 right=f'<span class="bw-card-meta">{len(docs)}건</span>')


def process_card(resp: dict) -> str:
    """검토 과정: LangGraph 9단계와 단계별 시간 (접힌 상태로 시작)."""
    steps = resp.get("ui", {}).get("steps") or []
    t = resp.get("timing", {})
    if not steps:
        return ""
    items = []
    for s in steps:
        skip = s.get("status") in ("skip", "pending")
        ic = icon("remove", 14) if skip else icon("check", 14)
        ms = f'<span class="ms">{seconds(s.get("ms"))}</span>' if s.get("ms") else '<span class="ms"></span>'
        name = esc(s.get("name", "")) + (" (건너뜀)" if s.get("status") == "skip" else "")
        items.append(f'<li class="{"is-skip" if skip else ""}">{ic}<span>{name}</span>{ms}</li>')
    head = (f'<div class="bw-card-h"><h3>{icon("timer", 18)}검토 과정</h3>'
            f'<span class="bw-card-meta">{len(steps)}단계 · 총 {seconds(t.get("total_ms"))} {icon("chevron_right", 16, cls="bw-chev")}</span></div>')
    return (f'<div class="bw-card"><details><summary>{head}</summary>'
            f'<ul class="bw-steps">{"".join(items)}</ul>'
            f'<p class="bw-card-note" style="margin-top:8px">하이브리드 검색(BM25 + 벡터)으로 조항을 찾고, 규칙 검사와 AI 판정 뒤 제안 문구를 다시 검증합니다.</p>'
            f'</details></div>')


def corpus_card(stats: dict, docs: list[dict]) -> str:
    """결과가 없을 때: 검색 대상 자료(지식베이스) 수치와 문서 목록."""
    kb = (f'<div class="bw-kb">'
          f'<div><div class="n">{stats.get("laws", 0)}<small>종</small></div><div class="l">법령 · 고시</div></div>'
          f'<div><div class="n">{stats.get("guidelines", 0)}<small>종</small></div><div class="l">표시·광고 관리 지침</div></div>'
          f'<div><div class="n">{stats.get("cases", 0)}<small>건</small></div><div class="l">식약처 적발 사례</div></div>'
          f'<div><div class="n">{stats.get("ingredients", 0):,}<small>개</small></div><div class="l">원료 성분 사전</div></div>'
          f'</div><p class="bw-card-note" style="margin-top:10px">문구를 입력하면 이 자료에서 관련 조항을 찾아 근거와 함께 답합니다.</p>')
    out = _card("검색 대상 자료", "library_books", kb)
    if docs:
        out += references_card([d for d in docs if d.get("kind") != "사례"], title="수집 문서")
    return out


def howto_card() -> str:
    """검토 방식 3단계."""
    body = ('<ol class="bw-howto">'
            '<li><div><b>근거 검색</b> — 문구와 관련된 법령·고시·지침·적발 사례 조항을 하이브리드 검색으로 찾습니다.</div></li>'
            '<li><div><b>판정</b> — 금지 표현 규칙과 AI 판정을 함께 써서 사용 가능 · 실증 필요 · 수정 필요로 나눕니다.</div></li>'
            '<li><div><b>교정</b> — 선택한 제품이 가진 실증 자료 범위 안에서 가장 설득력 있는 문구를 제안하고 다시 검증합니다.</div></li>'
            '</ol>')
    return _card("이렇게 검토합니다", "tune", body)
