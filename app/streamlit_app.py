"""
[app/streamlit_app.py]
Beaurette — 화장품 광고 문구 검토 AI 의 Streamlit 진입 파일.

실행 (저장소 루트에서): uv run streamlit run app/streamlit_app.py
데이터 모드: UI_DATA_MODE=api | local | mock(미설정 시 기본) — 연결 지점은 app/services/backend.py
"""
import sys
from pathlib import Path

# `streamlit run app/streamlit_app.py` 는 app/ 만 sys.path 에 넣는다. 저장소 루트(app.*)와 src(cosmetic_agent,
# 패키지를 설치하지 않은 실행·Docker)를 넣는다 — 팀 dev 의 같은 수정(9b4f4e1)과 합침.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st

from app.components.chatbot import render_launcher
from app.components.sidebar import render_sidebar
from app.components.theme import inject_base_css
from app.services import backend

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Beaurette · 화장품 광고 문구 검토",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="auto",
)


@st.cache_data(ttl=20, show_spinner=False)
def _health(mode: str) -> dict:
    return backend.health()


# 홈(소개 페이지)이 첫 화면이고, 「시작하기」로 검토 대화에 들어간다. 홈에는 사이드바가 없다.
HOME = st.Page(str(APP_DIR / "views" / "home.py"), title="홈", icon=":material/home:", default=True)
PAGES = {
    "chat": st.Page(str(APP_DIR / "views" / "chat.py"), title="통합 챗봇", icon=":material/chat_bubble:"),
    "generate": st.Page(str(APP_DIR / "views" / "generate.py"), title="광고문 생성", icon=":material/auto_awesome:"),
    "review": st.Page(str(APP_DIR / "views" / "review.py"), title="검토 대화", icon=":material/forum:"),
    "bulk": st.Page(str(APP_DIR / "views" / "bulk.py"), title="상세페이지 검토", icon=":material/article:"),
    "library": st.Page(str(APP_DIR / "views" / "library.py"), title="규정 · 가이드라인", icon=":material/menu_book:"),
    "forecast": st.Page(str(APP_DIR / "views" / "forecast.py"), title="예상 매출 시나리오", icon=":material/calculate:"),
}
# 「시장 근거 · 문구 비교」는 예상 매출 시나리오의 참고 자료로 합쳤다. 주소(views/market.py)는 남기되 메뉴에는 보이지 않는다.
MARKET = st.Page(str(APP_DIR / "views" / "market.py"), title="시장 근거 · 문구 비교", icon=":material/analytics:")
st.session_state["bw_pages"] = PAGES
st.session_state["bw_health"] = _health(backend.data_mode())

page = st.navigation([HOME, *PAGES.values(), MARKET], position="hidden")
inject_base_css()
if page.url_path != HOME.url_path:
    render_sidebar(PAGES, st.session_state["bw_health"])
page.run()
render_launcher(PAGES)
