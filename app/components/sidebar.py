"""
[app/components/sidebar.py]
왼쪽 사이드바: 브랜드 · 새 검토 · 화면 이동 · 최근 검토 · 데이터 상태.
"""
from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.brand import BRAND_NAME, TAGLINE, lockup_img, scene_img
from app.components.icons import icon
from app.components.layout import ago, esc, html

MAX_RECENT = 8


def render_sidebar(pages: dict[str, st.Page], health: dict) -> None:
    """pages: {"review": Page, "bulk": Page, "library": Page}."""
    with st.sidebar:
        tagline = esc(TAGLINE).replace("\n", "<br>")
        html(f'<div class="bw-brand">{lockup_img(42)}<p>{tagline}</p></div>')

        if st.button("새 검토", icon=":material/add:", icon_position="right", key="new_review", width="stretch"):
            threads.start_new()
            st.switch_page(pages["review"])

        with st.container(key="nav", gap=None):
            for page in pages.values():
                st.page_link(page, width="stretch")

        html('<div class="bw-side-h" style="margin-top:12px;border-top:1px solid var(--bw-line);padding-top:18px">'
             f'<span>최근 검토</span>{icon("history", 17)}</div>')
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
            cls, title, body = "", "데모 데이터로 동작 중", "판정과 제안은 Mock 응답이며 실제 AI 결과가 아닙니다."
        elif health.get("ok"):
            cls, title, body = "is-live", "API 연결됨", health.get("detail", "")
        else:
            cls, title, body = "is-down", "API 연결 실패", health.get("detail", "")
        html(f'<div class="bw-promo" style="margin-top:20px"><p>근거 있는 문구로<br>더 안전한<br>뷰티 마케팅을<br>'
             f'<b>{BRAND_NAME}</b>가<br>함께합니다.</p><span class="bw-promo-art">{scene_img(136)}</span></div>'
             f'<div class="bw-side-status {cls}"><span><b>{esc(title)}</b> — {esc(body)}</span></div>')
