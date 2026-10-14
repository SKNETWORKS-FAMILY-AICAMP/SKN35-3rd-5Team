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
from app.services.peer_market import appeal_summary, candidate_copies, find_peers, judge_candidates, price_benchmark
from app.services.revenue_scenario import DISPLAY_LABEL, build_scenario

pages = st.session_state["bw_pages"]
health = st.session_state["bw_health"]
stats = backend.kb_stats()
product = backend.list_products()[0]   # 예시 검토 기준: 첫 제품 + 보유 실증 전부 (검토 화면의 기본값과 같다)

inject_css("home")

# 「05 예상 매출 시나리오」 예시 — 팀원 화면(views/forecast.py)의 「예시로 해보기 · 비타민A 앰플」과 같은 제품 · 같은 기본값
# (그 화면은 페이지 스크립트라 import 하지 않고 값만 옮겨 둔다: 월 300 · 600 · 1,200개, 1차 위반, 광고 기준)
FORECAST_EXAMPLE = {
    "id": "EXAMPLE_FORECAST", "name": "비타민A 브라이트닝 앰플", "category": "기능성", "functional_type": "피부 미백, 주름 개선",
    "key_ingredients": ["레티놀", "나이아신아마이드", "아데노신"], "form": "세럼·앰플", "price_krw": 32000,
    "owned_evidence": [{"test_type": "인체적용시험", "item": "눈가 주름 개선",
                        "value": "8주 사용 후 눈가 주름 15% 개선", "institute": "예시 피부임상연구소"}],
    "example": True,
}
FORECAST_UNITS = {"low": 300, "mid": 600, "high": 1200}


@st.cache_data(show_spinner=False)
def _forecast_example() -> dict | None:
    """예상 매출 화면과 같은 서비스로 계산한 예시 결과. 팀원 서비스 · 자료가 바뀌어 계산이 깨지면 None → 섹션만 빠지고 홈은 그대로."""
    try:
        product = FORECAST_EXAMPLE
        peers = find_peers(product)
        judged = judge_candidates(product, candidate_copies(product), peers)
        best = next((j for j in judged if j["recommended"]), None)
        if not best:
            return None
        original = f"바르는 순간 주름이 사라지는 {product['name']}"   # 예상 매출 화면의 기본 원문과 같은 꼴
        common = dict(price_krw=product["price_krw"], monthly_units=FORECAST_UNITS, product=product, offense=1,
                      sanction_kind="광고", ad_dependent_share=None, copy_exposed_share=1.0)
        return {"product": product, "peers": peers, "bench": price_benchmark(peers) if peers else None,
                "summary": appeal_summary(peers) if peers else [], "best": best, "original": original,
                "before": build_scenario(copy_text=original, **common), "after": build_scenario(copy_text=best["copy"], **common),
                "units": FORECAST_UNITS, "label": DISPLAY_LABEL}
    except Exception:   # noqa: BLE001 — 소개 섹션 하나 때문에 홈 전체가 죽지 않게
        return None



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

terms = data_sources.banned_terms()
html(landing.correction_band(terms))
html(landing.demo_section(exs, product["name"], len(product.get("owned_evidence") or [])))
html(landing.skin_spread(terms))
html(landing.problem(backend.enforcement_trends()))
html(landing.how())
html(landing.features(exs[0], landing.ladder_pair(product), landing.detail_rows(product)))
fc = _forecast_example()
if fc and "forecast" in pages:
    html(landing.forecast(fc))
    with st.container(key="home_fc_go", horizontal=True):
        if st.button("예상 매출 시나리오 열기", key="home_fc_open", icon=":material/arrow_forward:", icon_position="right"):
            st.switch_page(pages["forecast"])
html(landing.sources(stats, backend.all_reference_documents()))
html(landing.closing())

with st.container(key="home_cta", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
    html(landing.cta_text(), inline=True)
    _start("home_start_end", "검토 시작하기")

html(landing.footer(mode_badge(health)) + landing.MOTION_SCRIPT + landing.DRIP_SCRIPT, js=True)
