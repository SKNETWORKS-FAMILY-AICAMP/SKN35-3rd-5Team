"""성분 입력 → AI 광고 초안 → 후보별 규정 검토."""
import re

import streamlit as st

from app.components.context import current
from app.services import backend

product, ctx = current()
st.title("성분으로 문구 만들기")
st.caption("성분 함유 사실에서 시작해 광고 초안을 만들고, 후보마다 규정과 보유 근거를 검토합니다.")
use_project = st.checkbox("왼쪽 프로젝트의 제품·실증 자료 사용", value=False)
if use_project:
    st.info(f"대상 제품: {ctx['product_name']} · {ctx['category_label']} · 실증 {ctx['evidence_on']}건. 왼쪽 프로젝트에서 변경할 수 있습니다.")
    st.warning("예시 제품의 실증은 내 제품의 근거가 아닙니다. 실제 동일 제품의 자료만 사용하세요.")
else:
    name = st.text_input("제품명", value="나의 화장품", max_chars=100)
    category = st.selectbox("제품 구분", ["일반", "기능성"])
    functional_type = st.text_input("실제 심사·보고받은 기능성 유형", max_chars=100) if category == "기능성" else None
    product = {"product_id": "ingredient_draft", "name": name, "category": category,
               "functional_type": functional_type, "owned_evidence": []}
st.caption("성분만으로 완제품 효능이나 기능성을 확정할 수 없습니다. 실증이 없는 제품은 함유 사실 중심으로 작성합니다.")

with st.form("generate_form"):
    raw = st.text_area("실제 제품에 들어 있는 성분", placeholder="예: 글리세린, 히알루론산, 판테놀\n쉼표 또는 줄바꿈으로 구분하세요.", max_chars=10000)
    left, right = st.columns(2)
    channel = left.selectbox("게시할 곳", ["SNS", "상세페이지", "배너"])
    tone = right.selectbox("문구 분위기", ["담백한", "감성적인", "발랄한", "눈길 끄는"])
    if tone == "눈길 끄는":
        st.caption("강한 도입·질문·감성적 비유를 사용합니다. 효능과 수치는 보유 근거 범위를 유지합니다.")
    submitted = st.form_submit_button("광고·홍보 문구 만들기", type="primary")

payload = {"ingredients": list(dict.fromkeys(v.strip() for v in re.split(r"[,，\n;]+", raw) if v.strip())),
           "product": product, "channel": channel, "tone": tone}
if submitted:
    st.session_state.pop("bw_generation", None)
    if not payload["ingredients"]:
        st.error("성분을 하나 이상 입력하세요.")
    else:
        try:
            with st.spinner("성분 기반 초안을 만들고 후보별로 검토하고 있습니다…"):
                response = backend.generate_copy(payload)
            st.session_state["bw_generation"] = {"payload": payload, "response": response}
        except backend.BackendError as error:
            st.error(error.message)

saved = st.session_state.get("bw_generation")
if saved and saved["payload"] == payload:
    response = saved["response"]
    for warning in response.get("warnings", []):
        st.warning(warning)
    for index, candidate in enumerate(response.get("candidates", []), 1):
        with st.container(border=True):
            st.subheader(f"후보 {index} · {candidate['status']}")
            if candidate["status"] == "검토통과":
                st.code(candidate["text"], language=None)
            else:
                with st.expander("검토가 필요한 초안 보기"):
                    st.write(candidate["text"])
            for note in candidate.get("notes", []):
                st.write(note)
            review = candidate.get("review")
            if review:
                with st.expander("검토 근거"):
                    citations = review["result"].get("citations", [])
                    if not citations:
                        st.caption("반환된 근거 조항이 없습니다.")
                    for citation in citations:
                        st.write(f"{citation['source']} · {citation['article']}")
                        st.caption(citation.get("content_snippet") or "")
    st.caption(response["disclaimer"])
elif saved:
    st.info("입력 또는 검토 기준이 바뀌었습니다. 다시 생성하면 현재 기준으로 검토합니다.")
