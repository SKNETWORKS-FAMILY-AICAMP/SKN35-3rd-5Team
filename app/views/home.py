"""
[app/views/home.py]
홈 — 서비스 소개 페이지. 「시작하기」를 누르면 검토 대화로 넘어간다.
사이드바는 그리지 않는다(진입 파일이 홈일 때 render_sidebar 를 건너뛴다). 섹션 HTML 과 움직임 스크립트는 components/landing.py.
"""
from __future__ import annotations

import streamlit as st

from app.components import landing
from app.components.layout import html, mode_badge
from app.components.theme import inject_css
from app.services import backend, data_sources

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]
stats = backend.kb_stats()
product = backend.list_products()[0]   # 예시 검토 기준: 첫 제품 + 보유 실증 전부 (검토 화면의 기본값과 같다)

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

exs = landing.examples(product)
# 히어로 — 왼쪽: 제목 · 시작하기 · 실제 교정 줄 / 오른쪽: 스튜디오 화보(화면 높이에 맞춤) 위에 흘러내리는 세럼 · 빛
with st.container(key="home_hero"):
    html(landing.hero_scene())
    html(landing.hero_text())
    with st.container(key="home_hero_cta", horizontal=True, gap="small"):
        _start("home_start_hero")
        html('<a class="bw-h-ghost" href="#bw-demo">실제 검토 보기</a>', inline=True)
    html(landing.hero_meta(stats))
    html(landing.hero_proof(exs))

html(landing.correction_band(data_sources.banned_terms()))
html(landing.demo_section(exs, product["name"], len(product.get("owned_evidence") or [])))
html(landing.problem(backend.enforcement_trends()))
html(landing.how())
html(landing.features(exs[0], landing.ladder_pair(product), landing.detail_rows(product)))
html(landing.sources(stats, backend.all_reference_documents()))

with st.container(key="home_cta", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
    html(landing.cta_text(), inline=True)
    _start("home_start_end", "검토 시작하기")

html(landing.footer(mode_badge(health)) + landing.MOTION_SCRIPT, js=True)
