"""
[app/components/cards.py]
판정 결과 및 교정 문구 시각화 카드 컴포넌트.
"""
from typing import Any
import streamlit as st


def render_result_card(response_data: dict[str, Any]):
    result = response_data.get("result", {})
    status = result.get("status", "판정")
    level = result.get("level")

    # 배지 색상 결정
    if status == "판단보류":
        badge = "⚪ 판단 보류 (전문가 검토 필요)"
        color = "#6c757d"
    elif level == 0:
        badge = "🟢 사용 가능 (Pass)"
        color = "#198754"
    elif level == 1:
        badge = "🟡 조건부 사용 가능 (Conditional)"
        color = "#ffc107"
    else:
        badge = "🔴 사용 불가 (Violation)"
        color = "#dc3545"

    st.markdown(
        f"""
        <div style="border-left: 6px solid {color}; padding: 12px; background-color: #f8f9fa; border-radius: 6px; margin-bottom: 12px;">
            <h4 style="margin: 0; color: {color};">{badge}</h4>
            <p style="margin: 6px 0 0 0; font-size: 14px;"><strong>위반 유형:</strong> {result.get("violation_type", "없음")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.get("suggestion"):
        st.success(f"**추천 대체 문구:** {result['suggestion']}")

    if result.get("next_test"):
        st.warning(f"**더 센 표현을 위해 필요한 시험:** {result['next_test']}")
