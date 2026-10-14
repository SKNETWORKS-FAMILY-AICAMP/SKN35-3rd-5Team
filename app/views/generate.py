"""현재 검토 기준을 사용한 신규 광고 문구 생성 화면."""

from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.context import current
from app.components.ingredient_roles import render_ingredient_roles
from app.components.layout import esc, html, page_header
from app.components.theme import AUTHORITY, inject_css
from app.services import backend, generation_results

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
    render_ingredient_roles(product)
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
                st.session_state[result_key] = backend.generate_copy(
                    instruction.strip(),
                    product,
                    channel=channel,
                    tone=tone,
                    length=length,
                    keywords=keywords,
                )
                st.session_state[signature_key] = ctx["signature"]
                generation_results.save(product, st.session_state[result_key], {
                    "instruction": instruction.strip(), "channel": channel, "tone": tone,
                    "length": length, "keywords": keywords,
                })
        except backend.BackendError as error:
            st.error(error.message)
        except Exception as error:  # noqa: BLE001 - 사용자 화면에 안전하게 표시
            st.error(f"광고문 생성 중 오류가 발생했습니다: {error}")

    saved, stale = generation_results.record(product)
    response = saved["response"] if saved else None
    if response:
        if stale:
            st.warning("검토 기준이 바뀌었습니다. 새 기준으로 다시 생성해 주세요.")
        elif response.get("status") == "생성보류":
            st.warning(" ".join(response.get("warnings") or ["안전한 광고 문구를 생성하지 못했습니다."]))
        else:
            labels = {"strong": "근거 최대", "balanced": "균형", "safe": "가장 안전"}
            st.subheader("생성 결과")
            if response.get("mock"):
                st.caption("화면 확인용 Mock 결과입니다. 실제 시장 참고 AI 생성 결과가 아닙니다.")
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
                    if candidate.get("market_application"):
                        st.write("시장 표현 반영: " + candidate["market_application"])
                    if candidate.get("ingredient_application"):
                        st.write("성분 역할 반영: " + candidate["ingredient_application"])
                    refs = {r["reference_id"]: r for r in response.get("market_references", [])}
                    for ref_id in candidate.get("market_reference_ids", []):
                        ref = refs.get(ref_id)
                        if ref:
                            st.caption(f"{ref_id} · {ref['brand']} · {ref['copy_text']}")
                    if st.button("이 문구를 매출 시나리오에 사용", key=f"select_generated_{index}"):
                        generation_results.choose(product, index)
                        st.switch_page(pages["forecast"])
                    if st.button("이 문구 다시 검토", key=f"review_generated_{index}", icon=":material/fact_check:"):
                        threads.ask(candidate["text"], ctx, product)
                        st.switch_page(pages["review"])

            references = response.get("market_references", [])
            with st.expander(f"비교한 시장 문구 {len(references)}건 · 표현 참고용"):
                if not references:
                    st.caption("비교 조건에 맞는 시장 문구가 없어 우리 제품 정보와 규정만으로 생성했습니다.")
                for ref in references:
                    st.markdown(f"**{ref['reference_id']} · {ref['brand']} · {ref['product_name']}**")
                    st.write(ref["copy_text"])
                    st.caption("공통 성분: " + ", ".join(ref["shared_ingredients"]) + " · " + ref["ingredient_basis"])
                    st.caption(ref.get("conditions") or "시험 조건 미확인")
                    if ref.get("source_url"):
                        st.link_button("시장 문구 원문", ref["source_url"], key=f"market_ref_{ref['reference_id']}")
            citations = response.get("citations") or []
            if citations:
                with st.expander(f"생성에 참고한 규정 {len(citations)}건"):
                    for number, citation in enumerate(citations, start=1):
                        authority = AUTHORITY.get(int(citation.get("authority", 4)), "자료")
                        st.markdown(
                            f"**{number}. [{authority}] {citation.get('source', '')} "
                            f"{citation.get('article', '')}**\n\n{citation.get('content_snippet', '') or ''}"
                        )
