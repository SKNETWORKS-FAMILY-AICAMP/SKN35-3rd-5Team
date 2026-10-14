"""
[app/components/sidebar.py]
왼쪽 사이드바 — 브랜드 · 새 대화 · 메뉴(홈 + 사용 흐름 묶음) · 프로젝트(제품·실증 자료) · 데이터 상태.
(최근 대화 목록은 화면을 단순하게 하려고 뺐다. 대화 기록 기능(threads)은 그대로 있다.)
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.components import threads
from app.components.brand import lockup_img
from app.components.context import render_project
from app.components.layout import esc, html

HOME = str(Path(__file__).resolve().parents[1] / "views" / "home.py")   # 검토 화면에서 홈으로 가는 길
# 메뉴 묶음 — 사용 흐름 순서. pages 의 key 로 고르고, 없는 key 는 건너뛴다. 묶음에 없는 새 화면은 맨 끝 「그 밖」에 붙는다.
GROUPS = [("검토", ("review", "bulk")), ("작성", ("chat", "generate")), ("근거 · 예측", ("library", "forecast"))]


def _section(title: str, right: str = "") -> None:
    html(f'<div class="bw-side-h"><span>{esc(title)}</span>{right}</div>')


def _nav(pages: dict[str, st.Page]) -> None:
    with st.container(key="nav", gap=None):
        st.page_link(HOME, label="홈", icon=":material/home:", width="stretch")
        groups = [(title, [k for k in keys if k in pages]) for title, keys in GROUPS]
        groups.append(("그 밖", [k for k in pages if all(k not in keys for _, keys in GROUPS)]))
        for title, keys in groups:
            if not keys:
                continue
            html(f'<div class="bw-nav-h">{esc(title)}</div>')
            for key in keys:
                st.page_link(pages[key], width="stretch")


def render_sidebar(pages: dict[str, st.Page], health: dict) -> None:
    """pages: {"review": Page, "bulk": Page, "chat": Page, "generate": Page, "library": Page, "forecast": Page}."""
    with st.sidebar:
        html(f'<div class="bw-brand">{lockup_img(36)}</div>')

        if st.button("새 대화", icon=":material/edit_square:", key="new_review", width="stretch"):
            threads.start_new()
            st.switch_page(pages["review"])

        _nav(pages)

        _section("프로젝트", '<span class="bw-side-note">검토 기준</span>')
        render_project()

        if health.get("mode") == "mock":
            cls, title, body = "", "데모 데이터", "판정과 제안은 Mock 응답입니다. 실제 AI 결과가 아닙니다."
        elif health.get("ok"):
            cls, title, body = "is-live", "API 연결됨", health.get("detail", "")
        else:
            cls, title, body = "is-down", "API 연결 실패", health.get("detail", "")
        html(f'<div class="bw-side-status {cls}"><span><b>{esc(title)}</b> {esc(body)}</span></div>')
