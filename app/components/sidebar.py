"""
[app/components/sidebar.py]
왼쪽 사이드바 — 브랜드 · 새 대화 · 작업(화면 이동) · 프로젝트(제품·실증 자료) · 데이터 상태.
(최근 대화 목록은 화면을 단순하게 하려고 뺐다. 대화 기록 기능(threads)은 그대로 있다.)
"""
from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.brand import lockup_img
from app.components.context import render_project
from app.components.layout import esc, html

def _section(title: str, right: str = "") -> None:
    html(f'<div class="bw-side-h"><span>{esc(title)}</span>{right}</div>')


def render_sidebar(pages: dict[str, st.Page], health: dict) -> None:
    """pages: {"review": Page, "bulk": Page, "library": Page}."""
    with st.sidebar:
        html(f'<div class="bw-brand">{lockup_img(36)}</div>')

        if st.button("새 대화", icon=":material/edit_square:", key="new_review", width="stretch"):
            threads.start_new()
            st.switch_page(pages["review"])

        _section("작업")
        with st.container(key="nav", gap=None):
            for page in pages.values():
                st.page_link(page, width="stretch")

        _section("프로젝트", '<span class="bw-side-note">검토 기준</span>')
        render_project()

        if health.get("mode") == "mock":
            cls, title, body = "", "데모 데이터", "판정과 제안은 Mock 응답입니다. 실제 AI 결과가 아닙니다."
        elif health.get("ok"):
            cls, title, body = "is-live", "API 연결됨", health.get("detail", "")
        else:
            cls, title, body = "is-down", "API 연결 실패", health.get("detail", "")
        html(f'<div class="bw-side-status {cls}"><span><b>{esc(title)}</b> {esc(body)}</span></div>')
