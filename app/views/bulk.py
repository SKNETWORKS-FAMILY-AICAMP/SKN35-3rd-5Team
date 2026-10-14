"""
[app/views/bulk.py]
상세페이지 검토 — 긴 글을 문장 단위로 나눠 검토하고, 고칠 문장과 교정본을 보여 준다.
문장 분할은 서버(api/text.py)와 같은 규칙을 쓴다.
"""
from __future__ import annotations

import os
import re
import time
from collections import Counter
from datetime import datetime

import streamlit as st

from app.components import live_check
from app.components.cards import COPY_SCRIPT, highlighted, status_tag, thinking
from app.components.context import current
from app.components.icons import icon
from app.components.layout import esc, html, page_header
from app.components.theme import AUTHORITY, inject_css, status_of
from app.services import backend
from app.services.contract import verdict_of

SAMPLE = """건조한 피부에 촉촉함을 채워 주는 데일리 수분 크림입니다.
4주 사용 후 피부 보습력 42% 개선 (인체적용시험, 한국피부과학연구원).
바르는 순간부터 24시간 촉촉함이 지속됩니다.
손상된 피부를 완벽하게 재생시켜 줍니다!
피부 고민 1위 국민 수분 크림.
타사 수분 크림 대비 2배 촉촉합니다.
엑소좀 성분이 피부 속 깊이 전달됩니다.
민감한 피부도 편안하게 사용할 수 있습니다."""

MOCK_DELAY = float(os.getenv("UI_MOCK_DELAY", "1"))
ORDER = ["불가", "조건부", "판단보류", "가능"]
FILTERS = {"전체": None, "수정 필요": "불가", "실증 필요": "조건부", "전문가 검토": "판단보류", "사용 가능": "가능"}

health = st.session_state["bw_health"]
inject_css("pages")


def _fill_sample() -> None:
    st.session_state["bw_bulk_text"] = SAMPLE


def _corrected(items: list[dict]) -> tuple[str, str]:
    """교정본 (평문, 바뀐 문장을 표시한 HTML). 같은 제안이 겹치면 다른 표현을 쓰고, 그래도 겹치면 그 문장은 뺀다."""
    def key(t: str) -> str:   # 괄호 속 출처·문장부호를 빼고 비교한다
        return "".join(ch for ch in re.sub(r"\([^)]*\)", "", t) if ch.isalnum())

    used = {key(r["input_text"]) for r in items if verdict_of(r["result"]) not in ("불가", "조건부")}
    plain, marked = [], []
    for r in items:
        res = r["result"]
        if verdict_of(res) in ("불가", "조건부"):
            options = [res.get("suggestion")] + list(r.get("ui", {}).get("alternatives", []))
            pick = next((o for o in options if o and key(o) not in used), None)
            if pick is None:
                marked.append(f'<del>{esc(r["input_text"])}</del>')
                continue
            used.add(key(pick))
            plain.append(pick)
            marked.append(f"<mark>{esc(pick)}</mark>")
        else:
            plain.append(r["input_text"])
            marked.append(esc(r["input_text"]))
    return "\n".join(plain), "\n".join(marked)


def _sentence_rows(items: list[dict], only: str | None) -> str:
    rows = []
    for no, r in enumerate(items, start=1):
        res, ui = r["result"], r.get("ui", {})
        verdict = verdict_of(res)
        if only and verdict != only:
            continue
        _, tone = status_of(verdict)
        why = ui.get("summary") or res.get("review_notes") or ""
        fix = ""
        if verdict in ("불가", "조건부") and res.get("suggestion"):
            fix = f'<div class="fix">{icon("arrow_downward", 15)}<span>{esc(res["suggestion"])}</span></div>'
        why_html = f'<div class="why">{esc(why)}</div>' if verdict != "가능" and why else ""
        rows.append(f'<div class="bw-sent is-{tone}"><span class="no">{no:02d}</span>{status_tag(verdict, small=True)}'
                    f'<div><div class="txt">{highlighted(r["input_text"], ui.get("highlights", []))}</div>{why_html}{fix}</div></div>')
    if not rows:
        return '<div class="bw-sents"><div class="bw-sents-empty">이 조건에 해당하는 문장이 없습니다.</div></div>'
    return f'<div class="bw-sents">{"".join(rows)}</div>'


def _summary(items: list[dict]) -> str:
    counts = Counter(verdict_of(r["result"]) for r in items)
    total = len(items)
    bar = "".join(f'<i class="{status_of(v)[1]}" style="width:{counts[v] / total * 100:.1f}%"></i>'
                  for v in ORDER if counts[v])
    lines = "".join(f'<div>{status_tag(v, small=True)}<b>{counts[v]}</b></div>' for v in ORDER)
    fix_n = counts["불가"] + counts["조건부"]
    return (f'<div class="bw-card"><div class="bw-card-h"><h3>{icon("fact_check", 18)}검토 요약</h3></div>'
            f'<div class="bw-total"><span class="n">{total}</span><span class="l">문장 중 {fix_n}문장을 고쳐야 합니다</span></div>'
            f'<div class="bw-dist">{bar}</div><div class="bw-counts">{lines}</div></div>')


def _top_citations(items: list[dict]) -> str:
    counter: Counter = Counter()
    auth: dict[str, int] = {}
    for r in items:
        for c in r["result"].get("citations", []):
            name = f'{c.get("source", "")} {c.get("article", "")}'.strip()
            counter[name] += 1
            auth[name] = int(c.get("authority", 4))
    if not counter:
        return ""
    rows = "".join(f'<div><span><b>{esc(name)}</b> <span class="bw-auth">{AUTHORITY.get(auth[name], "")}</span></span>'
                   f'<span class="c">{n}회</span></div>' for name, n in counter.most_common(5))
    return (f'<div class="bw-card"><div class="bw-card-h"><h3>{icon("menu_book", 18)}자주 인용된 근거</h3>'
            f'<span class="bw-card-meta">상위 {min(5, len(counter))}개</span></div><div class="bw-top">{rows}</div></div>')


center, right = st.columns([1.72, 1], gap="large")

with center, st.container(key="center"):
    page_header("상세페이지 검토", "상세페이지 글 전체를 문장 단위로 검토하고, 고쳐야 할 문장과 교정본을 정리합니다.", health=health)
    product, ctx = current()   # 검토 기준은 왼쪽 「내 제품」이 정한다

    with st.container(key="pagebody"):
        with st.container(key="bulkin"):
            st.text_area("상세페이지 글", key="bw_bulk_text", height=170, label_visibility="collapsed",
                         placeholder="상세페이지 글을 그대로 붙여 넣으세요. 줄바꿈과 문장부호로 나눠 최대 100문장까지 검토합니다.")
            # 입력하는 동안 바로 밑줄 — 글자 아래 밑줄 + 요약 한 줄 (브라우저에서 바로 검사)
            html(live_check.slot("bw_bulk_text") + live_check.script(product, ["bw_bulk_text"]), js=True)
        with st.container(horizontal=True, key="bulkbtn"):
            st.button("예시 상세페이지 넣기", type="tertiary", icon=":material/description:", on_click=_fill_sample)
            run = st.button("문장별 검토 시작", type="primary", icon=":material/fact_check:")

        if run:
            text = st.session_state.get("bw_bulk_text", "").strip()
            if not text:  # 입력 누락은 오류가 아니라 안내다
                st.session_state["bw_bulk_error"] = None
                st.session_state["bw_bulk_hint"] = "검토할 글을 먼저 붙여 넣으세요. 예시 상세페이지로 시작해도 됩니다."
            else:
                slot = st.empty()
                try:
                    items = []
                    for event in backend.review_page_events(text, product):   # 실제로 끝낸 문장만 센다
                        if event["type"] == "sentence":
                            slot.html(f'<div class="bw">{thinking(event["done"], event["total"], "문장별로 검토하는 중")}</div>')
                            time.sleep(0.05 * MOCK_DELAY)   # 데모 표시 속도 (Mock 만, 0 이면 없음)
                        elif event["type"] == "wait":
                            slot.html(f'<div class="bw">{thinking(0, event["total"], "서버가 문장을 검토하는 중")}</div>')
                        elif event["type"] == "result":
                            items = event["items"]
                    st.session_state["bw_bulk"] = {"items": items, "ctx": ctx, "at": datetime.now(), "n": len(items)}
                    st.session_state.pop("bw_bulk_error", None)
                    st.session_state.pop("bw_bulk_hint", None)
                except backend.BackendError as err:
                    st.session_state["bw_bulk_error"] = err.message
                    st.session_state.pop("bw_bulk_hint", None)
                slot.empty()

        if st.session_state.get("bw_bulk_hint"):
            html(f'<div class="bw-hint" style="margin-top:12px">{icon("info", 18)}<span>{esc(st.session_state["bw_bulk_hint"])}</span></div>')
        if st.session_state.get("bw_bulk_error"):
            html(f'<div class="bw-error" style="margin-top:12px">{icon("error", 18)}<div><b>검토하지 못했습니다.</b> '
                 f'{esc(st.session_state["bw_bulk_error"])}</div></div>')

        bulk = st.session_state.get("bw_bulk")
        if bulk:
            items = bulk["items"]
            counts = Counter(verdict_of(r["result"]) for r in items)
            html(f'<div class="bw-block-h" style="margin-top:22px"><h3>문장별 결과</h3>'
                 f'<span>{esc(bulk["ctx"]["product_name"])} · 실증 {bulk["ctx"]["evidence_on"]}건 기준</span></div>')
            labels = {k: (f"{k} {len(items)}" if v is None else f"{k} {counts[v]}") for k, v in FILTERS.items()}
            with st.container(key="bulkfilter"):
                choice = st.segmented_control("결과 거르기", list(FILTERS), default="전체", key="bw_bulk_filter",
                                              format_func=lambda k: labels[k], label_visibility="collapsed")
            html(_sentence_rows(items, FILTERS.get(choice or "전체")))

with right:
    with st.container(key="aside"):
        bulk = st.session_state.get("bw_bulk")
        if bulk:
            items = bulk["items"]
            plain, marked = _corrected(items)
            html(_summary(items)
                 + f'<div class="bw-card"><div class="bw-card-h"><h3>{icon("edit_note", 18)}교정본</h3>'
                   f'<span class="bw-card-meta">바뀐 문장 표시</span></div><div class="bw-fixed">{marked}</div>'
                   f'<div class="bw-fixed-actions"><button type="button" class="bw-copy" data-copy="{esc(plain)}">'
                   f'{icon("content_copy", 15)}<span class="lbl">복사</span></button></div></div>'
                 + _top_citations(items) + COPY_SCRIPT, js=True)
            with st.container(key="bulkdl"):
                st.download_button("교정본 내려받기 (.txt)", plain.encode("utf-8"), file_name="beaurette_교정본.txt",
                                   mime="text/plain", icon=":material/download:", width="stretch")
        else:
            html('<div class="bw-card"><div class="bw-card-h"><h3>' + icon("tune", 18) + '이렇게 검토합니다</h3></div>'
                 '<ol class="bw-howto">'
                 '<li><div><b>문장 나누기</b> — 서버와 같은 규칙으로 줄바꿈과 문장부호에서 나눕니다. 소수점(42.5%)은 나누지 않습니다.</div></li>'
                 '<li><div><b>문장별 판정</b> — 문장마다 근거 조항을 찾아 사용 가능 · 실증 필요 · 수정 필요로 나눕니다.</div></li>'
                 '<li><div><b>교정본</b> — 고쳐야 할 문장만 보유 실증 범위의 표현으로 바꿔 한 번에 복사하거나 내려받습니다.</div></li>'
                 '</ol></div>'
                 '<div class="bw-card"><p class="bw-card-note">검토 기준 제품과 실증 자료는 왼쪽 「내 제품」에서 바꿀 수 있습니다. '
                 '모든 문장에 같은 기준이 적용됩니다.</p></div>')
