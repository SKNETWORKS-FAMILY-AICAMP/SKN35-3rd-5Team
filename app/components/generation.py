"""챗봇과 생성 화면이 공유하는 광고 후보·검토 결과 표시."""
import streamlit as st


def render_generation(response: dict, on_select=None, select_label: str = "이 문구를 매출 시나리오에 사용") -> None:
    """on_select(index) 를 주면 검토를 통과한 후보마다 선택 버튼을 단다 (광고문 생성 → 예상 매출 연결)."""
    if response.get("mock"):
        st.info("디자인 확인용 데모 결과입니다. 실제 AI 생성·검토 결과가 아닙니다.")
    for warning in response.get("warnings", []):
        st.caption(warning)
    for index, candidate in enumerate(response.get("candidates", []), 1):
        status = candidate.get("status") or ("검토통과" if candidate.get("verified") else "확인필요")
        st.markdown(f"**후보 {index} · {status}**")
        if candidate.get("headline"):
            st.markdown(f"### {candidate['headline']}")
            if candidate.get("supporting_copy"):
                st.write(candidate["supporting_copy"])
        if candidate.get("evidence_note"):
            st.caption("함께 표시할 등록 시험 정보 · 최종 광고 사용 전 원자료 확인")
            st.write(candidate["evidence_note"])
        if status == "검토통과":
            st.code(candidate["text"] + ("\n\n" + candidate["evidence_note"] if candidate.get("evidence_note") else ""), language=None)
            if on_select and st.button(f"후보 {index} · {select_label}", key=f"select_generated_{index - 1}",
                                       type="primary", icon=":material/trending_up:"):
                on_select(index - 1)
        else:
            with st.expander("확인이 필요한 초안"):
                st.write(candidate["text"])
        if candidate.get("rationale"):
            st.caption(candidate["rationale"])
        if candidate.get("creative_application"):
            st.caption("창작 구성: " + candidate["creative_application"])
        if candidate.get("market_application"):
            st.caption("시장 표현 반영: " + candidate["market_application"])
        if candidate.get("ingredient_application"):
            st.caption("성분 역할 반영: " + candidate["ingredient_application"])
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
    references = response.get("market_references") or []
    if references:
        with st.expander(f"비교한 시장 문구 {len(references)}건 · 표현 참고용"):
            for ref in references:
                st.markdown(f"**{ref['reference_id']} · {ref['brand']} · {ref['product_name']}**")
                st.write(ref["copy_text"])
                st.caption("공통 성분: " + ", ".join(ref["shared_ingredients"]) + " · " + ref["ingredient_basis"])
                if ref.get("source_url"):
                    st.link_button("시장 문구 원문", ref["source_url"], key=f"market_ref_{ref['reference_id']}")
    if response.get("citations"):
        with st.expander("생성에 참고한 규정"):
            for citation in response["citations"]:
                st.write(f"{citation['source']} · {citation['article']}")
                st.caption(citation.get("content_snippet") or "")
    if not response.get("candidates"):
        st.info("검토를 통과한 후보가 없습니다. 위 사유를 확인하고 작성 방향을 바꿔 다시 시도해주세요.")
    st.caption(response.get("disclaimer", "자동 검토는 법률 준수를 보장하지 않습니다."))
