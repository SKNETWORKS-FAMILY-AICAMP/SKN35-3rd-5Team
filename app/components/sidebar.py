"""
[app/components/sidebar.py]
Streamlit 사이드바: 가상 제품 선택 및 보유 근거 체크리스트 컴포넌트.
"""
from typing import Any
import streamlit as st


def render_product_sidebar(mock_products: list[dict[str, Any]]) -> dict[str, Any]:
    st.sidebar.header("1. 제품 카드 선택")
    product_names = [p["name"] for p in mock_products]
    selected_name = st.sidebar.selectbox("검토 대상 제품", product_names)

    selected_product = next(p for p in mock_products if p["name"] == selected_name)

    st.sidebar.markdown(f"**구분:** {selected_product['category']}")
    if selected_product.get("functional_type"):
        st.sidebar.markdown(f"**기능성:** {selected_product['functional_type']}")

    st.sidebar.markdown("---")
    st.sidebar.header("2. 보유 실증 자료")
    evidences = selected_product.get("owned_evidence", [])
    if not evidences:
        st.sidebar.info("등록된 보유 실증 자료가 없습니다.")
    else:
        for idx, ev in enumerate(evidences):
            st.sidebar.checkbox(
                f"{ev['test_type']}: {ev['item']} ({ev['value']})",
                value=True,
                key=f"ev_{idx}",
            )

    return selected_product
