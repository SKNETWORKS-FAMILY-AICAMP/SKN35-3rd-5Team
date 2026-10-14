"""현재 검토 기준을 사용한 신규 광고 문구 생성 화면."""

from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.context import current
from app.components.layout import esc, html, page_header
from app.components.theme import AUTHORITY, inject_css
from app.services import backend

health = st.session_state["bw_health"]
pages = st.session_state["bw_pages"]
inject_css("pages")

product, ctx = current()
result_key = "bw_generation_result"
signature_key = "bw_generation_signature"

page_header(
    "광고문 생성",
    "왼쪽 검토 기준의 제품 정보와 선택된 실증자료 안에서 검증된 광고 문구를 만듭니다.",
    health=health,
)

html(
    f'<div class="bw-hint"><span class="material-symbols-rounded">science</span><div>'
    f'<b>{esc(ctx["product_name"])}</b> · {esc(ctx["category_label"])} · '
    f'사용 실증 {ctx["evidence_on"]}/{ctx["evidence_total"]}<br>'
    f'<span>왼쪽 「프로젝트 · 검토 기준」에서 제품과 사용할 실증자료를 바꿀 수 있습니다.</span>'
    f'</div></div>'
)

with st.container(key="pagebody"):
    with st.form("generate_form"):
        instruction = st.text_area(
            "어떤 광고문을 만들까요?",
            value=f"{ctx['product_name']}의 특징을 설득력 있게 소개하는 광고문을 만들어줘",
            max_chars=2000,
            height=100,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            channel = st.selectbox("광고 채널", ["상세페이지", "SNS", "배너", "검색광고", "라이브커머스"])
        with col2:
            tone = st.selectbox("문구 분위기", ["고급스러운", "전문적인", "감성적인", "간결한", "친근한"])
        with col3:
            length = st.selectbox("문구 길이", ["한 줄", "짧은 문단", "상세 설명"])
        keyword_text = st.text_input("포함할 키워드", placeholder="쉼표로 구분해 입력하세요")
        submitted = st.form_submit_button("검증된 광고문 생성", type="primary", icon=":material/auto_awesome:")

    if submitted:
        keywords = [word.strip() for word in keyword_text.split(",") if word.strip()][:10]
        try:
            with st.spinner("관련 규정을 검색하고 광고 문구를 검증하고 있습니다..."):
                st.session_state[result_key] = backend.generate_project_copy(
                    instruction.strip(),
                    product,
                    channel=channel,
                    tone=tone,
                    length=length,
                    keywords=keywords,
                )
                st.session_state[signature_key] = ctx["signature"]
        except backend.BackendError as error:
            st.error(error.message)
        except Exception as error:  # noqa: BLE001 - 사용자 화면에 안전하게 표시
            st.error(f"광고문 생성 중 오류가 발생했습니다: {error}")

    response = st.session_state.get(result_key)
    if response:
        if st.session_state.get(signature_key) != ctx["signature"]:
            st.warning("검토 기준이 바뀌었습니다. 새 기준으로 다시 생성해 주세요.")
        elif response.get("status") == "생성보류":
            st.warning(" ".join(response.get("warnings") or ["안전한 광고 문구를 생성하지 못했습니다."]))
        else:
            labels = {"strong": "근거 최대", "balanced": "균형", "safe": "가장 안전"}
            st.subheader("생성 결과")
            for index, candidate in enumerate(response.get("candidates", [])):
                tier = candidate.get("tier", "safe")
                with st.container(border=True):
                    st.caption(f"{labels.get(tier, tier)} · {candidate.get('verify_note', '검증 통과')}")
                    st.markdown(f"### {candidate['text']}")
                    if candidate.get("rationale"):
                        st.write(candidate["rationale"])
                    if candidate.get("used_evidence"):
                        st.caption("사용한 근거: " + ", ".join(candidate["used_evidence"]))
                    st.code(candidate["text"], language=None)
                    if st.button("이 문구 다시 검토", key=f"review_generated_{index}", icon=":material/fact_check:"):
                        threads.ask(candidate["text"], ctx, product)
                        st.switch_page(pages["review"])

            citations = response.get("citations") or []
            if citations:
                with st.expander(f"생성에 참고한 규정 {len(citations)}건"):
                    for number, citation in enumerate(citations, start=1):
                        authority = AUTHORITY.get(int(citation.get("authority", 4)), "자료")
                        st.markdown(
                            f"**{number}. [{authority}] {citation.get('source', '')} "
                            f"{citation.get('article', '')}**\n\n{citation.get('content_snippet', '') or ''}"
                        )
