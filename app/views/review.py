"""
[app/views/review.py]
문구 검토 — 규정 문서 기반 RAG 챗봇 화면.
가운데: 대화(질문 → AI 답변) · 검토 기준 줄 · 입력 / 오른쪽: 근거(RAG) · 원문 문서 · 검토 과정.
검토 기준(제품·실증 자료)은 왼쪽 사이드바 「프로젝트」가 정한다 — 여기서는 읽기만 한다.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import streamlit as st

from app.components import threads
from app.components.cards import assistant_message, error_message, thinking, user_message, welcome
from app.components.context import current
from app.components.icons import icon
from app.components.layout import esc, html, page_header
from app.components.panels import documents_list, evidence_list, ladder_block, process_list, rag_empty, rag_header
from app.services import backend
from app.services.contract import PIPELINE_STEPS, verdict_of

# 첫 화면 시작 문구 — 판정 셋(수정 필요 · 실증 필요 · 전문가 검토)이 하나씩 나오게 골랐다
STARTERS = [
    "단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!",
    "바르는 순간부터 24시간 촉촉함이 지속되는 수분 크림",
    "PDRN 성분이 피부 속 깊이 전달되는 신개념 앰플",
]

# Mock 응답의 단계 연출 속도 (0 이면 기다리지 않는다 — 점검·시연 리허설용)
MOCK_DELAY = float(os.getenv("UI_MOCK_DELAY", "1"))

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]


def _ctx_line(ctx: dict) -> str:
    return f'{ctx["product_name"]} · {ctx["category_label"]} · 실증 {ctx["evidence_on"]}/{ctx["evidence_total"]}'


def _bubble_label(ctx: dict) -> str:
    """말풍선 아래 한 마디 — 같은 문구를 다른 실증 기준으로 다시 물은 것이 보이게."""
    return f'실증 {ctx["evidence_on"]}건 기준'


def _run(thread: dict, message: dict, slot) -> None:
    """대기 중인 질문에 답한다. Mock 이면 결과의 단계를 따라 진행을 보여 준다."""
    total = len(PIPELINE_STEPS)
    try:
        if backend.data_mode() == "mock":
            resp = backend.review_copy(message["text"], message["product"])
            steps = resp.get("ui", {}).get("steps") or [{"name": n, "status": "done"} for _, n in PIPELINE_STEPS]
            for i, s in enumerate(steps, start=1):
                slot.html(f'<div class="bw">{thinking(i, total, s["name"] + " 중")}</div>')
                time.sleep(0.17 * MOCK_DELAY)
        else:
            slot.html(f'<div class="bw">{thinking(1, total, "근거를 찾고 판정하는 중")}</div>')
            resp = backend.review_copy(message["text"], message["product"])
        threads.answer(thread, {"role": "assistant", "resp": resp, "at": datetime.now(), "ctx": message["ctx"]})
    except backend.BackendError as err:
        threads.answer(thread, {"role": "error", "message": err.message, "at": datetime.now()})


product, ctx = current()
thread = threads.active()
pending = threads.pending_for(thread)
last = threads.last_assistant(thread)
changed = bool(last) and last["ctx"]["signature"] != ctx["signature"]

center, right = st.columns([1.85, 1], gap="large")

with center, st.container(key="center"):
    page_header(thread["title"] if thread else "새 대화", "규정 문서를 근거로 답하는 광고 문구 검토 챗봇", health=health)

    with st.container(key="thread"):
        if not thread:
            html(welcome(ctx["product_name"]))
            with st.container(key="starters", gap=None):
                html('<div class="bw-starters-h">이런 문구로 시작해 보세요</div>')
                for i, text in enumerate(STARTERS):
                    if st.button(text, key=f"example_{i}", icon=":material/north_east:", width="stretch"):
                        threads.ask(text, ctx, product)
                        st.rerun()
        else:
            for m in thread["messages"]:
                if m["role"] == "user":
                    html(user_message(m["text"], m["at"], _bubble_label(m["ctx"])))
                elif m["role"] == "assistant":
                    html(assistant_message(m["resp"], m["at"]), js=True)
                else:
                    html(error_message(m["message"], m["at"]))
            if pending:
                _run(thread, pending, st.empty())
                st.rerun()
            # 마지막 질문이 대화 영역 맨 위에 오게 스크롤한다 (답변을 처음부터 읽게)
            html("<script>setTimeout(function(){var el=document.querySelector('.st-key-thread');"
                 "if(!el){return;}var q=el.querySelectorAll('.bw-user');var last=q[q.length-1];"
                 "if(!last){return;}el.scrollTop+=last.getBoundingClientRect().top-el.getBoundingClientRect().top-12;},80);</script>",
                 js=True)

    if last and not pending and changed:
        last_user = next(m for m in reversed(thread["messages"]) if m["role"] == "user")
        with st.container(horizontal=True, key="ctxnote", vertical_alignment="center"):
            html(f'<span class="bw-ctxnote">{icon("info", 16)}검토 기준이 바뀌었습니다 — {esc(_ctx_line(ctx))}</span>',
                 inline=True)
            if st.button("이 기준으로 다시 검토", key="rerun_ctx", icon=":material/refresh:"):
                threads.ask(last_user["text"], ctx, product)
                st.rerun()

    with st.container(key="composer", gap=None):
        html(f'<div class="bw-composer-ctx">{icon("science", 15)}<span>검토 기준</span><b>{esc(_ctx_line(ctx))}</b>'
             '<span class="hint">왼쪽 「프로젝트」에서 바꿉니다</span></div>')
        prompt = st.chat_input("검토할 광고 문구를 입력하거나 붙여 넣으세요", key="bw_chat", max_chars=5000)
        if prompt and prompt.strip():
            threads.ask(prompt.strip(), ctx, product)
            st.rerun()

    # 후속 동작은 입력창 아래 한 줄 (기준이 바뀌었으면 위의 "이 기준으로 다시 검토" 하나만)
    if last and not pending and not changed:
        result = last["resp"]["result"]
        with st.container(horizontal=True, key="followups", gap="small"):
            if result.get("suggestion") and verdict_of(result) in ("불가", "조건부"):
                if st.button("제안 문구로 다시 검토", key="fu_suggest", icon=":material/refresh:", type="tertiary"):
                    threads.ask(result["suggestion"], ctx, product)
                    st.rerun()
            st.page_link(pages["library"], label="근거 원문 찾아보기", icon=":material/menu_book:")

with right, st.container(key="aside"):
    if last:
        resp = last["resp"]
        docs = backend.reference_documents(resp["result"].get("citations", []))
        n = len(resp["result"].get("citations", []))
        html(rag_header(resp) + ladder_block(resp))
        tab_ev, tab_docs, tab_proc = st.tabs([f"근거 {n}", f"원문 문서 {len(docs)}", "검토 과정"], key="asidetabs")
        with tab_ev:
            html(evidence_list(resp))
        with tab_docs:
            html(documents_list(docs))
        with tab_proc:
            html(process_list(resp))
    else:
        html(rag_empty(backend.kb_stats(), backend.all_reference_documents()))
