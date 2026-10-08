"""
[app/streamlit_app.py]
Streamlit 프론트엔드 메인 대시보드.
"""
from pathlib import Path
import json
import streamlit as st
import httpx
from cosmetic_agent.common.config import settings
from app.components.sidebar import render_product_sidebar
from app.components.cards import render_result_card

st.set_page_config(
    page_title="화장품 광고 문구 심사 에이전트",
    page_icon="💄",
    layout="wide",
)


@st.cache_data
def load_mock_products():
    path = settings.MOCK_PRODUCTS_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    st.title("💄 화장품 광고 문구 컴플라이언스 에이전트")
    st.caption("화장품법 및 식약처 광고 실증 가이드라인 기반 사전 심사 및 표현 사다리 교정")

    products = load_mock_products()
    selected_product = render_product_sidebar(products)

    tab1, tab2 = st.tabs(["단일 문구 검토", "상세페이지 일괄 검토"])

    with tab1:
        copy_input = st.text_area(
            "광고 문구 입력",
            value="단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!",
            height=100,
        )
        if st.button("문구 심사 시작", type="primary"):
            with st.spinner("법령 검색 및 에이전트 판정 중..."):
                try:
                    res = httpx.post(
                        f"{settings.API_BASE_URL}/review",
                        json={"copy_text": copy_input, "product": selected_product},
                        timeout=30.0,
                    )
                    if res.status_code == 200:
                        render_result_card(res.json())
                    else:
                        st.error(f"서버 오류: {res.text}")
                except Exception as e:
                    st.warning(f"FastAPI 연결 실패 ({e}). Mock 결과 표시:")
                    render_result_card({
                        "result": {
                            "status": "판정",
                            "level": 2,
                            "violation_type": "의약품오인",
                            "suggestion": "피부 보습 장벽을 탄탄하게 케어해 줍니다.",
                            "next_test": "피부 재생 표현은 불가하며, 장벽 강화 인체적용시험 필요",
                        }
                    })

    with tab2:
        st.text_area("상세페이지 전체 글 붙여넣기 (준비 중)", height=200)


if __name__ == "__main__":
    main()
