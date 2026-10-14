"""
[app/streamlit_app.py]
Beaurette — 화장품 광고 문구 검토 AI 의 Streamlit 진입 파일.

실행 (저장소 루트에서): uv run streamlit run app/streamlit_app.py
데이터 모드: 환경변수 UI_DATA_MODE=api(기본) | mock  — 연결 지점은 app/services/backend.py
"""
import sys
from pathlib import Path

# `streamlit run app/streamlit_app.py` 는 app/ 만 sys.path 에 넣는다. 저장소 루트(app.*)와 src(cosmetic_agent,
# 패키지를 설치하지 않은 실행·Docker)를 넣는다 — 팀 dev 의 같은 수정(9b4f4e1)과 합침.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402

from app.components.sidebar import render_sidebar  # noqa: E402
from app.components.theme import inject_base_css  # noqa: E402
from app.services import backend  # noqa: E402

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Beaurette · 화장품 광고 문구 검토",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="auto",
)


@st.cache_data(ttl=20, show_spinner=False)
def _health() -> dict:
    return backend.health()


PAGES = {
    "review": st.Page(str(APP_DIR / "views" / "review.py"), title="검토 대화", icon=":material/forum:", default=True),
    "generate": st.Page(str(APP_DIR / "views" / "generate.py"), title="광고문 생성", icon=":material/edit_note:"),
    "bulk": st.Page(str(APP_DIR / "views" / "bulk.py"), title="상세페이지 검토", icon=":material/article:"),
    "library": st.Page(str(APP_DIR / "views" / "library.py"), title="규정 · 가이드라인", icon=":material/menu_book:"),
    "market": st.Page(str(APP_DIR / "views" / "market.py"), title="시장 근거 · 문구 비교", icon=":material/analytics:"),
}
st.session_state["bw_pages"] = PAGES
st.session_state["bw_health"] = _health()

page = st.navigation(list(PAGES.values()), position="hidden")
inject_base_css()
render_sidebar(PAGES, st.session_state["bw_health"])
page.run()
