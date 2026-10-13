"""
[app/components/threads.py]
검토 대화 기록(세션 안에서만 유지). 사이드바의 '최근 검토'와 가운데 대화 영역이 같이 쓴다.

대화 = {"id", "title", "created", "messages": [메시지...]}
메시지 = {"role": "user", "text", "at", "ctx"} | {"role": "assistant", "resp", "at", "ctx"} | {"role": "error", "message", "at"}
"""
from __future__ import annotations

from datetime import datetime
from itertools import count

import streamlit as st

_THREADS = "bw_threads"
_ACTIVE = "bw_active"
_PENDING = "bw_pending"
_SEQ = count(1)


def all_threads() -> list[dict]:
    """최근 것이 위로 오도록 정렬된 대화 목록."""
    return st.session_state.setdefault(_THREADS, [])


def active() -> dict | None:
    tid = st.session_state.get(_ACTIVE)
    return next((t for t in all_threads() if t["id"] == tid), None)


def set_active(tid: str | None) -> None:
    st.session_state[_ACTIVE] = tid


def start_new() -> None:
    """'새 검토' — 빈 대화 화면으로 간다(기록은 첫 질문 때 만든다)."""
    set_active(None)
    st.session_state.pop(_PENDING, None)


def delete(tid: str) -> bool:
    """대화를 지운다. 보고 있던 대화면 빈 화면(새 대화)으로 돌아간다. 지웠으면 True."""
    threads = all_threads()
    for i, t in enumerate(threads):
        if t["id"] == tid:
            del threads[i]
            if st.session_state.get(_ACTIVE) == tid:
                set_active(None)
            if st.session_state.get(_PENDING) == tid:
                st.session_state.pop(_PENDING, None)
            return True
    return False


def _title(text: str) -> str:
    one = " ".join(text.split())
    return one if len(one) <= 20 else one[:20].rstrip() + "…"


def ask(text: str, ctx: dict, product: dict) -> None:
    """사용자 문구를 대화에 넣고 답변 대기 상태로 둔다. 답변은 화면이 다음 실행에서 만든다.
    product 는 요청 시점의 제품(체크한 실증만 담은 것) — 나중에 기준을 바꿔도 이 질문의 기준은 그대로다."""
    thread = active()
    if thread is None:
        thread = {"id": f"t{next(_SEQ)}-{int(datetime.now().timestamp())}", "title": _title(text),
                  "created": datetime.now(), "messages": []}
        all_threads().insert(0, thread)
        set_active(thread["id"])
    thread["messages"].append({"role": "user", "text": text, "at": datetime.now(), "ctx": ctx, "product": product})
    st.session_state[_PENDING] = thread["id"]


def pending_for(thread: dict | None) -> dict | None:
    """이 대화에서 답을 기다리는 사용자 메시지."""
    if thread and st.session_state.get(_PENDING) == thread["id"] and thread["messages"] \
            and thread["messages"][-1]["role"] == "user":
        return thread["messages"][-1]
    return None


def answer(thread: dict, message: dict) -> None:
    """답변(또는 오류)을 붙이고 대기 상태를 푼다."""
    thread["messages"].append(message)
    st.session_state.pop(_PENDING, None)


def last_assistant(thread: dict | None) -> dict | None:
    if not thread:
        return None
    return next((m for m in reversed(thread["messages"]) if m["role"] == "assistant"), None)


def history() -> list[dict]:
    """모든 대화의 AI 답변 (상세페이지 화면 등에서 통계용)."""
    return [m for t in all_threads() for m in t["messages"] if m["role"] == "assistant"]
