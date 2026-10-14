"""
[app/components/sidebar.py]
왼쪽 사이드바 — 브랜드(누르면 홈) · 메뉴(사용 흐름 묶음) · 내 제품(제품·실증 자료) · 데이터 상태.
(최근 대화 목록은 화면을 단순하게 하려고 뺐다. 대화 기록 기능(threads)은 그대로 있다.)
"""
from __future__ import annotations

import streamlit as st

from app.components.brand import lockup_uri
from app.components.context import render_project
from app.components.layout import esc, html

# 메뉴 묶음 — 사용 흐름 순서. pages 의 key 로 고르고, 없는 key 는 건너뛴다. 묶음에 없는 새 화면은 맨 끝 「그 밖」에 붙는다.
GROUPS = [("검토", ("review", "bulk")), ("작성", ("chat", "generate")), ("근거 · 예측", ("library", "forecast"))]


def _section(title: str, right: str = "") -> None:
    html(f'<div class="bw-side-h"><span>{esc(title)}</span>{right}</div>')


def _nav(pages: dict[str, st.Page]) -> None:
    with st.container(key="nav", gap=None):
        groups = [(title, [k for k in keys if k in pages]) for title, keys in GROUPS]
        groups.append(("그 밖", [k for k in pages if all(k not in keys for _, keys in GROUPS)]))
        for title, keys in groups:
            if not keys:
                continue
            html(f'<div class="bw-nav-h">{esc(title)}</div>')
            for key in keys:
                st.page_link(pages[key], width="stretch")


def render_sidebar(pages: dict[str, st.Page], health: dict, *, home: st.Page) -> None:
    """pages: {"review": Page, "bulk": Page, "chat": Page, "generate": Page, "library": Page, "forecast": Page}. 로고를 누르면 home."""
    with st.sidebar:
        with st.container(key="brand_home"):
            st.page_link(home, label=f"![Beaurette]({lockup_uri()})", icon="", help="첫 화면으로 이동", width="content")

        _nav(pages)

        _section("내 제품", '<span class="bw-side-note">검토 기준</span>')
        render_project()

        if health.get("mode") == "mock":
            cls, title, body = "", "데모 데이터", "판정과 제안은 Mock 응답입니다. 실제 AI 결과가 아닙니다."
        elif health.get("ok"):
            cls, title, body = "is-live", "API 연결됨", health.get("detail", "")
        else:
            cls, title, body = "is-down", "API 연결 실패", health.get("detail", "")
        html(f'<div class="bw-side-status {cls}"><span><b>{esc(title)}</b> {esc(body)}</span></div>')
