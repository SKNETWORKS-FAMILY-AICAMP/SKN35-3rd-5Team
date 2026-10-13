"""
[app/views/review.py]
문구 검토 — 규정 문서 기반 RAG 챗봇 화면.
가운데: 대화(질문 → AI 답변) · 검토 기준 줄 · 입력 / 오른쪽: 근거(RAG) · 원문 문서 · 검토 과정.
검토 기준(제품·실증 자료)은 왼쪽 사이드바 「프로젝트」가 정한다 — 여기서는 읽기만 한다.

- 진행 표시는 backend.review_events() 가 실제로 낸 이벤트만 그린다 (components/progress.py).
- 최신 답변: 수정 제안 후보 고르기(components/suggest.py) · 위험 표현 ↔ 근거 연동(components/interact.py) ·
  확장 블록(components/blocks.py — 응답에 ui.blocks 가 있을 때만).
"""
from __future__ import annotations

import os
import queue
import threading
import time
from datetime import datetime

import streamlit as st

from app.components import blocks, progress, suggest, threads
from app.components.cards import assistant_live, assistant_message, error_message, user_message, welcome
from app.components.context import current
from app.components.icons import icon
from app.components.interact import LINK_SCRIPT
from app.components.layout import esc, html, page_header
from app.components.panels import documents_list, evidence_list, ladder_block, process_list, rag_empty, rag_header
from app.services import backend

# 첫 화면 시작 문구 — 판정 셋(수정 필요 · 실증 필요 · 전문가 검토)이 하나씩 나오게 골랐다
STARTERS = [
    "단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!",
    "바르는 순간부터 24시간 촉촉함이 지속되는 수분 크림",
    "PDRN 성분이 피부 속 깊이 전달되는 신개념 앰플",
]

# Mock 진행 단계를 보여 주는 속도 (0 이면 기다리지 않는다 — 점검·시연 리허설용). 실제 API 에는 쓰지 않는다
MOCK_DELAY = float(os.getenv("UI_MOCK_DELAY", "1"))
_SEEN = "bw_seen"   # 한 번 그린 답변 (처음 도착한 답변에만 캐릭터 동작·스크롤)

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]


def _ctx_line(ctx: dict) -> str:
    return f'{ctx["product_name"]} · {ctx["category_label"]} · 실증 {ctx["evidence_on"]}/{ctx["evidence_total"]}'


def _bubble_label(ctx: dict) -> str:
    """말풍선 아래 한 마디 — 같은 문구를 다른 실증 기준으로 다시 물은 것이 보이게."""
    return f'실증 {ctx["evidence_on"]}건 기준'


def _run(thread: dict, message: dict, slot) -> None:
    """대기 중인 질문에 답한다. 검토는 별도 스레드에서 돌리고, 받은 이벤트만 진행 카드에 그린다."""
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            for event in backend.review_events(message["text"], message["product"]):
                events.put(event)
        except backend.BackendError as err:
            events.put({"type": "error", "message": err.message})
        except Exception as err:  # noqa: BLE001 — 화면에 그대로 알린다
            events.put({"type": "error", "message": f"검토 중 오류가 났습니다: {err}"})

    threading.Thread(target=work, daemon=True).start()
    demo = backend.data_mode() == "mock"
    pace = 0.08 * MOCK_DELAY if demo else 0.0
    state, t0 = progress.Progress(), time.perf_counter()
    while True:
        try:
            event = events.get(timeout=0.15)
        except queue.Empty:
            event = None
        if event and event["type"] == "result":
            threads.answer(thread, {"role": "assistant", "resp": event["resp"], "at": datetime.now(), "ctx": message["ctx"]})
            return
        if event and event["type"] == "error":
            threads.answer(thread, {"role": "error", "message": event["message"], "at": datetime.now()})
            return
        if event:
            state.apply(event)
        slot.html(f'<div class="bw">{progress.card(state, elapsed=None if demo else time.perf_counter() - t0, demo=pace > 0)}</div>')
        if event and pace and event["type"] == "stage":
            time.sleep(pace)


def _answer_question(block: dict, answer: str) -> None:
    """확장 블록(question)에서 답을 고르면 그 답을 붙여 다시 묻는다."""
    text = (block.get("follow_up") or "{answer}").replace("{answer}", answer)
    threads.ask(text, ctx, product)
    st.rerun()


product, ctx = current()
thread = threads.active()
pending = threads.pending_for(thread)
last = threads.last_assistant(thread)
changed = bool(last) and last["ctx"]["signature"] != ctx["signature"]
seen: set = st.session_state.setdefault(_SEEN, set())
arrived = False   # 이번에 처음 그린 답변이 있는가 (스크롤용)

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
            msgs = thread["messages"]
            for idx, m in enumerate(msgs):
                mk = f'{thread["id"]}_{idx}'
                fresh = mk not in seen
                seen.add(mk)
                if m["role"] == "user":
                    html(user_message(m["text"], m["at"], _bubble_label(m["ctx"])))
                elif m["role"] == "error":
                    html(error_message(m["message"], m["at"], fresh=fresh))
                elif m is last and not pending:
                    arrived = arrived or fresh
                    parts = assistant_live(m["resp"], m["at"], fresh=fresh)
                    with st.container(key=f"live_{mk}", gap=None):
                        if parts:
                            top, bottom, has_tail = parts
                            html(top, js=True)
                            suggest.render(m["resp"], mk, ctx, product, last=not has_tail)
                            html(bottom)
                        else:
                            html(assistant_message(m["resp"], m["at"], live=True, fresh=fresh), js=True)
                    blocks.render(m["resp"].get("ui", {}).get("blocks"), mk, _answer_question)
                else:
                    html(assistant_message(m["resp"], m["at"]), js=True)
            if pending:
                _run(thread, pending, st.empty())
                st.rerun()
            if arrived:
                # 새 답변이 왔을 때만: 마지막 질문이 대화 영역 맨 위에 오게 (답변을 처음부터 읽게)
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

    if last and not pending and not changed:
        with st.container(horizontal=True, key="followups", gap="small"):
            st.page_link(pages["library"], label="근거 원문 찾아보기", icon=":material/menu_book:")

    html(LINK_SCRIPT, js=True)   # 위험 표현 ↔ 오른쪽 근거 연동 (한 번만 붙는다)

with right, st.container(key="aside"):
    if last:
        resp = last["resp"]
        docs = backend.reference_documents(resp["result"].get("citations", []))
        n = len(resp["result"].get("citations", []))
        html(rag_header(resp) + ladder_block(resp, fresh=arrived))
        tab_ev, tab_docs, tab_proc = st.tabs([f"근거 {n}", f"원문 문서 {len(docs)}", "검토 과정"], key="asidetabs")
        with tab_ev:
            html(evidence_list(resp, fresh=arrived))
        with tab_docs:
            html(documents_list(docs))
        with tab_proc:
            html(process_list(resp))
    else:
        html(rag_empty(backend.kb_stats(), backend.all_reference_documents()))
