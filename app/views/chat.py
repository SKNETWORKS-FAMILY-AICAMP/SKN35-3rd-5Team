"""통합 챗봇 전체 화면. 팝업과 같은 대화를 사용한다."""
import streamlit as st

from app.components.chatbot import chat_header, render_chat, reset
from app.components.theme import inject_css


def remember_project() -> None:
    st.session_state["bw_chat_project"] = st.session_state["bw_chat_project_widget"]

inject_css("chat")
with st.container(key="chat_shell_full"):
    with st.container(key="chat_header_full"):
        left, right = st.columns([5, 1], vertical_alignment="center")
        with left:
            chat_header()
        with right:
            st.button("새 대화", icon=":material/edit_square:", on_click=reset, width="stretch", key="chat_reset", type="tertiary")
    with st.container(key="chat_settings_full"), st.expander("제품 및 검토 기준"):
        st.session_state["bw_chat_project_widget"] = st.session_state.get("bw_chat_project", False)
        st.checkbox("왼쪽 프로젝트의 제품·실증 자료 사용", key="bw_chat_project_widget", on_change=remember_project)
        if st.session_state.get("bw_chat_project"):
            st.caption("프로젝트 자료는 실제 동일 제품의 근거일 때만 사용하세요.")
        else:
            st.caption("기본은 실증 없는 일반 화장품입니다. 제품 성분을 대화로 알려주세요.")
    render_chat()
