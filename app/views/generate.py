"""제품 설명·작성 요청 중심의 통합 광고문 생성 화면."""
import re

import streamlit as st

from app.components.context import current, register_product
from app.components.generation import render_generation
from app.components.ingredient_roles import render_ingredient_roles
from app.services import backend, generation_results
from cosmetic_agent.generation.creative import creative_catalog
from cosmetic_agent.market_reference import form_of

st.title("광고문 생성")
st.caption("원하는 제품과 광고 방향을 말해주세요. 성분을 몰라도 초안부터 만들고, 규정과 확인된 제품 근거로 검토합니다.")
use_project = st.checkbox("왼쪽 프로젝트의 제품·실증 자료 사용", value=False)
if use_project:
    product, ctx = current()
    st.caption(f"{ctx['product_name']} · 실증 {ctx['evidence_on']}건. 실제 동일 제품의 자료일 때만 사용하세요.")
else:
    product = {"product_id": "generation_draft", "name": "나의 화장품", "category": "일반", "owned_evidence": []}

if use_project:
    render_ingredient_roles(product)
with st.expander("창작 레퍼런스 · 표현 구성 5종"):
    for style in creative_catalog()["styles"]:
        st.markdown(f"**{style['name']}** — {style['pattern']}")
    st.caption("표현 구조만 참고하며 다른 브랜드의 효능·수치를 옮기지 않습니다.")

with st.form("generate_form"):
    instruction = st.text_area("어떤 광고문을 만들까요?", placeholder="예: 자외선 차단 선크림 광고를 20대 대상으로 짧고 발랄하게 만들어줘.\n예: 판테놀이 들어간 크림의 SNS 문구를 감성적인 톤으로 써줘.", max_chars=5000, height=140)
    channel_col, tone_col, length_col = st.columns(3)
    channel = channel_col.selectbox("광고 채널", ["SNS", "상세페이지", "배너", "검색광고", "라이브커머스"])
    tone = tone_col.text_input("문구 분위기", value="요청에 맞게", max_chars=100, placeholder="예: 재치 있는, 전문적인, 감성적인")
    length = length_col.selectbox("문구 길이", ["짧은 문단", "한 줄", "상세 설명"])
    with st.expander("제품·성분 정보 추가 (선택)"):
        st.caption("추가 정보가 없어도 생성할 수 있습니다. 성분이나 요청한 효능만으로 심사·시험 사실을 추정하지 않습니다.")
        if not use_project:
            name = st.text_input("제품명 (선택)", max_chars=100)
            category = st.selectbox("제품 구분", ["일반", "기능성"])
            functional_type = st.text_input("실제 심사·보고받은 기능성 유형", max_chars=100) if category == "기능성" else None
            product = dict(product, name=name.strip() or "나의 화장품", category=category, functional_type=functional_type)
        raw = st.text_area("실제 함유 성분 (선택)", placeholder="판테놀, 히알루론산", max_chars=10000, height=80)
    submitted = st.form_submit_button("광고문 만들기", type="primary", icon=":material/auto_awesome:")

payload = {"instruction": instruction.strip(), "product": product, "channel": channel,
           "tone": tone.strip() or "요청에 맞게", "length": length,
           "ingredients": list(dict.fromkeys(v.strip() for v in re.split(r"[,，\n;]+", raw) if v.strip()))}
if submitted:
    st.session_state.pop("bw_generation", None)
    if not payload["instruction"]:
        st.error("어떤 광고문을 만들지 요청을 입력해주세요.")
    else:
        try:
            with st.spinner("요청에 맞는 광고 초안을 만들고 검토하고 있습니다…"):
                response = backend.generate_copy(payload)
            st.session_state["bw_generation"] = {"payload": payload, "response": response}
            if use_project:
                generation_results.save(product, response, payload)
        except backend.BackendError as error:
            st.error(error.message)
saved = st.session_state.get("bw_generation")


def use_in_forecast(index: int) -> None:
    """선택한 후보를 예상 매출 변화 폭 화면에 연결한다.
    프로젝트 제품이면 그 제품 기록에, 초안이면 입력한 제품 정보로 프로젝트 제품을 만들어 연결한다."""
    target = product
    if not use_project:
        drafts = st.session_state.setdefault("bw_generation_drafts", {})
        key = (product.get("name"), product.get("category"), product.get("functional_type"), tuple(payload["ingredients"]))
        existing = next((p for p in st.session_state.get("bw_custom_products", []) if p["product_id"] == drafts.get(key)), None)
        target = existing or register_product({
            "name": product.get("name") or "나의 화장품", "category": product.get("category", "일반"),
            "functional_type": product.get("functional_type"), "key_ingredients": payload["ingredients"],
            "form": form_of(product.get("name") or ""), "owned_evidence": [],
        })
        drafts[key] = target["product_id"]
        st.session_state["bw_pid"] = target["product_id"]
    try:
        generation_results.send_to_forecast(target, saved["response"], saved["payload"], index)
    except Exception as error:  # noqa: BLE001 - 연결 실패 사유를 화면에 보여준다
        st.error(f"매출 시나리오 연결에 실패했습니다: {error}")
        return
    st.switch_page(st.session_state["bw_pages"]["forecast"])


if saved and saved["payload"] == payload:
    render_generation(saved["response"], on_select=use_in_forecast)
    if not use_project and saved["response"].get("candidates"):
        st.caption("선택하면 입력한 제품명·구분·성분으로 왼쪽 프로젝트에 제품이 만들어지고, 예상 매출 시나리오에서 비슷한 시장 제품과 비교합니다.")
elif saved:
    st.info("입력 또는 검토 기준이 바뀌었습니다. 다시 생성하면 현재 기준으로 검토합니다.")
