"""
[app/streamlit_app.py]
Beaurette — 화장품 광고 문구 검토 AI 의 Streamlit 진입 파일.

실행 (저장소 루트에서): uv run streamlit run app/streamlit_app.py
데이터 모드: 환경변수 UI_DATA_MODE=mock(기본) | api  — 연결 지점은 app/services/backend.py
"""
import sys
from pathlib import Path

# `streamlit run app/streamlit_app.py` 는 app/ 만 sys.path 에 넣는다. 저장소 루트를 넣어 app.* 로 import 한다.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    "review": st.Page(str(APP_DIR / "views" / "review.py"), title="문구 검토", icon=":material/chat_bubble:", default=True),
    "bulk": st.Page(str(APP_DIR / "views" / "bulk.py"), title="상세페이지 검토", icon=":material/article:"),
    "library": st.Page(str(APP_DIR / "views" / "library.py"), title="규정 라이브러리", icon=":material/menu_book:"),
}
st.session_state["bw_pages"] = PAGES
st.session_state["bw_health"] = _health()

page = st.navigation(list(PAGES.values()), position="hidden")
inject_base_css()
render_sidebar(PAGES, st.session_state["bw_health"])
page.run()
