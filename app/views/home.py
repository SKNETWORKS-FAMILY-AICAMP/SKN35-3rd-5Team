"""
[app/views/home.py]
홈 — 서비스 소개 페이지. 「시작하기」를 누르면 검토 대화로 넘어간다.
사이드바는 그리지 않는다(진입 파일이 홈일 때 render_sidebar 를 건너뛴다). 섹션 HTML 은 components/landing.py.
"""
from __future__ import annotations

import streamlit as st

from app.components import landing
from app.components.layout import html, mode_badge
from app.components.theme import inject_css
from app.services import backend

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]

inject_css("home")


def _start(key: str, label: str = "시작하기") -> None:
    if st.button(label, key=key, type="primary", icon=":material/arrow_forward:", icon_position="right"):
        st.switch_page(pages["review"])


with st.container(key="home_top", horizontal=True, vertical_alignment="center", gap="medium"):
    html(landing.top_brand(), inline=True)
    html(landing.top_links(), inline=True)
    with st.container(key="home_top_r", horizontal=True, vertical_alignment="center", width="content", gap="small"):
        html(mode_badge(health), inline=True)
        _start("home_start_top")

with st.container(key="home_hero"):
    html(landing.hero())
    with st.container(key="home_hero_cta", horizontal=True, horizontal_alignment="center", gap="small"):
        _start("home_start_hero")
        html('<a class="bw-home-ghost" href="#bw-features">기능 살펴보기</a>', inline=True)
    html(landing.hero_checks())
    html(landing.preview())

html(landing.problem(backend.enforcement_trends()))
html(landing.how())
html(landing.features())
html(landing.sources(backend.kb_stats(), backend.all_reference_documents()))

with st.container(key="home_cta", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
    html(landing.cta_text(), inline=True)
    _start("home_start_end", "검토 시작하기")

html(landing.footer(mode_badge(health)))
