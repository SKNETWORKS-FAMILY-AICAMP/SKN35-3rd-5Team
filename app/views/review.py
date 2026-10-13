"""
[app/views/review.py]
문구 검토 — RAG 챗봇 화면.
가운데: 검토 기준 · 대화(질문 → AI 검토 답변) · 입력 / 오른쪽: 검토 요약 · 근거 · 참조 문서 · 검토 과정.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import streamlit as st

from app.components import threads
from app.components.cards import assistant_message, error_message, thinking, user_message, welcome
from app.components.context import render_context_bar
from app.components.icons import icon
from app.components.layout import esc, html, page_header
from app.components.panels import (
    corpus_card, evidence_card, howto_card, process_card, references_card, summary_card,
)
from app.services import backend
from app.services.contract import PIPELINE_STEPS, verdict_of

EXAMPLES = [
    "단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!",
    "바르는 순간부터 24시간 촉촉함이 지속되는 수분 크림",
    "피부 보습 유지에 도움을 주는 데일리 수분 크림",
    "엑소좀이 피부 속 깊이 전달되는 신개념 앰플",
]

# Mock 응답의 단계 연출 속도 (0 이면 기다리지 않는다 — 점검·시연 리허설용)
MOCK_DELAY = float(os.getenv("UI_MOCK_DELAY", "1"))

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]


def _ctx_label(ctx: dict) -> str:
    return f'{ctx["product_name"]} · 실증 {ctx["evidence_on"]}건'


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


center, right = st.columns([1.72, 1], gap="large")

with center, st.container(key="center"):
    page_header("화장품 광고 문구 검토", "법령·고시·관리지침·적발 사례를 근거로, 보유한 실증 범위 안에서 더 안전한 문구를 제안합니다.",
                health=health, beta=True)
    product, ctx = render_context_bar()

    thread = threads.active()
    pending = threads.pending_for(thread)

    with st.container(key="thread"):
        if not thread:
            html(welcome(ctx["product_name"]))
            with st.container(horizontal=True, key="examples", horizontal_alignment="center", gap="small"):
                for i, example in enumerate(EXAMPLES):
                    if st.button(example, key=f"example_{i}"):
                        threads.ask(example, ctx, product)
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
                 "if(!el){return;}var q=el.querySelectorAll('.bw-msg.is-user');var last=q[q.length-1];"
                 "if(!last){return;}el.scrollTop+=last.getBoundingClientRect().top-el.getBoundingClientRect().top-12;},80);</script>",
                 js=True)

    last = threads.last_assistant(thread)
    changed = bool(last) and last["ctx"]["signature"] != ctx["signature"]
    if last and not pending:
        last_user = next(m for m in reversed(thread["messages"]) if m["role"] == "user")
        if changed:
            with st.container(horizontal=True, key="ctxnote", vertical_alignment="center"):
                html(f'<span class="bw-ctxnote">{icon("info", 15)}검토 기준이 바뀌었습니다 — '
                     f'{esc(_ctx_label(ctx))}</span>', inline=True)
                if st.button("이 기준으로 다시 검토", key="rerun_ctx", icon=":material/refresh:"):
                    threads.ask(last_user["text"], ctx, product)
                    st.rerun()
    prompt = st.chat_input("검토할 광고 문구를 입력하거나 붙여 넣으세요", key="bw_chat", max_chars=5000)
    if prompt and prompt.strip():
        threads.ask(prompt.strip(), ctx, product)
        st.rerun()

    # 후속 질문 칩은 입력창 아래 (대화 내용을 가리지 않게). 기준이 바뀌었으면 "이 기준으로 다시 검토" 하나만 남긴다
    if last and not pending and not changed:
        result = last["resp"]["result"]
        with st.container(horizontal=True, key="followups", gap="small"):
            if result.get("suggestion") and verdict_of(result) in ("불가", "조건부"):
                if st.button("제안 문구로 다시 검토", key="fu_suggest", icon=":material/refresh:"):
                    threads.ask(result["suggestion"], ctx, product)
                    st.rerun()
            st.page_link(pages["library"], label="근거 원문 찾아보기", icon=":material/menu_book:")

with right:
    with st.container(key="aside"):
        if last:
            resp = last["resp"]
            docs = backend.reference_documents(resp["result"].get("citations", []))
            html(summary_card(resp, last["ctx"]) + evidence_card(resp) + references_card(docs) + process_card(resp))
        else:
            html(corpus_card(backend.kb_stats(), backend.all_reference_documents()) + howto_card())
