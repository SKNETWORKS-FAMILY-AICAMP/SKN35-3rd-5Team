"""
[app/components/sidebar.py]
왼쪽 사이드바: 브랜드 · 새 검토 · 화면 이동 · 최근 검토 · 데이터 상태.
"""
from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.brand import TAGLINE, lockup_img
from app.components.icons import icon
from app.components.layout import ago, esc, html

MAX_RECENT = 8


def render_sidebar(pages: dict[str, st.Page], health: dict) -> None:
    """pages: {"review": Page, "bulk": Page, "library": Page}."""
    with st.sidebar:
        tagline = esc(TAGLINE).replace("\n", "<br>")
        html(f'<div class="bw-brand">{lockup_img(34)}<p>{tagline}</p></div>')

        if st.button("새 검토", icon=":material/add:", icon_position="right", key="new_review", width="stretch"):
            threads.start_new()
            st.switch_page(pages["review"])

        for page in pages.values():
            st.page_link(page, width="stretch")

        html('<div class="bw-side-h" style="margin-top:14px;border-top:1px solid var(--bw-line);padding-top:16px">'
             f'<span>최근 검토</span>{icon("history", 15)}</div>')
        recent = threads.all_threads()[:MAX_RECENT]
        if not recent:
            html('<div class="bw-side-empty">아직 검토한 문구가 없습니다.</div>')
        current = threads.active()
        for t in recent:
            on = current is not None and current["id"] == t["id"]
            with st.container(horizontal=True, key=f'recent_{"on" if on else "off"}_{t["id"]}',
                              vertical_alignment="center", wrap=False):
                if st.button(t["title"], key=f'open_{t["id"]}', type="tertiary", width="stretch"):
                    threads.set_active(t["id"])
                    st.switch_page(pages["review"])
                html(f'<span class="bw-recent-time">{ago(t["created"])}</span>', inline=True)

        if health.get("mode") == "mock":
            title, body, name = "데모 데이터로 동작 중", "백엔드 연결 전입니다. 판정과 제안은 Mock 응답이며 실제 AI 결과가 아닙니다.", "database"
        elif health.get("ok"):
            title, body, name = "API 연결됨", health.get("detail", ""), "check_circle_outline"
        else:
            title, body, name = "API 연결 실패", health.get("detail", ""), "cloud_off"
        html(f'<div class="bw-side-foot" style="margin-top:18px">{icon(name, 16)}'
             f'<div><b>{esc(title)}</b>{esc(body)}</div></div>')
