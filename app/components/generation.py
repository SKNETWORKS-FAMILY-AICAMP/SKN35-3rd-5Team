"""챗봇과 생성 화면이 공유하는 광고 후보·검토 결과 표시."""
import streamlit as st


def render_generation(response: dict) -> None:
    if response.get("mock"):
        st.info("디자인 확인용 데모 결과입니다. 실제 AI 생성·검토 결과가 아닙니다.")
    for warning in response.get("warnings", []):
        st.caption(warning)
    for index, candidate in enumerate(response.get("candidates", []), 1):
        status = candidate.get("status") or ("검토통과" if candidate.get("verified") else "확인필요")
        st.markdown(f"**후보 {index} · {status}**")
        if status == "검토통과":
            if candidate.get("headline"):
                st.markdown(f"### {candidate['headline']}")
                st.write(candidate.get("supporting_copy", ""))
            if candidate.get("evidence_note"):
                with st.container(border=True):
                    st.caption("등록 시험 정보 · 광고 사용 전 원자료 확인")
                    st.write(candidate["evidence_note"])
            st.code(candidate["text"] + ("\n\n" + candidate["evidence_note"] if candidate.get("evidence_note") else ""), language=None)
            for field, label in (("creative_application", "창작 구성"), ("market_application", "시장 표현 참고"), ("ingredient_application", "성분 역할 참고")):
                if candidate.get(field):
                    st.caption(label + ": " + candidate[field])
        else:
            with st.expander("확인이 필요한 초안"):
                st.write(candidate["text"])
        if candidate.get("rationale"):
            st.caption(candidate["rationale"])
        for note in candidate.get("notes", []):
            st.write(note)
        review = candidate.get("review")
        if review:
            with st.expander(f"후보 {index} 검토 상세"):
                result = review["result"]
                if result.get("review_notes"):
                    st.write(result["review_notes"])
                if result.get("next_test"):
                    st.write(result["next_test"])
                for citation in result.get("citations", []):
                    st.write(f"{citation['source']} · {citation['article']}")
                    st.caption(citation.get("content_snippet") or "")
    if response.get("citations"):
        with st.expander("생성에 참고한 규정"):
            for citation in response["citations"]:
                st.write(f"{citation['source']} · {citation['article']}")
                st.caption(citation.get("content_snippet") or "")
    if not response.get("candidates"):
        st.info("검토를 통과한 후보가 없습니다. 위 사유를 확인하고 작성 방향을 바꿔 다시 시도해주세요.")
    st.caption(response.get("disclaimer", "자동 검토는 법률 준수를 보장하지 않습니다."))
