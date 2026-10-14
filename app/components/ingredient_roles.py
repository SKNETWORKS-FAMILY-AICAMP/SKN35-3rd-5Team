"""Readable ingredient role cards with research scope and source links."""
import streamlit as st

from cosmetic_agent.generation.ingredients import catalog, ingredient_profiles


def render_ingredient_roles(product: dict) -> None:
    profiles = ingredient_profiles(product)
    with st.expander(f"이 제품 성분으로 잡은 표현 방향 · {len(profiles)}개 연결"):
        st.caption("성분 일반 정보와 연구 조건입니다. 우리 제품의 시험 결과나 광고 허용 판정과는 구분합니다.")
        mine, all_cards = st.tabs(["우리 제품 성분", "지원 성분 10개 보기"])
        with mine:
            if not profiles:
                st.info("주요 성분을 입력하면 해당 역할 자료를 연결합니다. 아직 지원하지 않는 성분의 효과는 추정하지 않습니다.")
            for row in profiles:
                with st.container(border=True):
                    st.markdown(f"**{row['name']}** · " + ", ".join(row["matched_ingredients"]))
                    st.write("역할·연구 방향: " + " · ".join(row["roles"]))
                    st.write("표현 아이디어: " + " / ".join(row["copy_angles"]))
                    st.caption(row["research_summary"])
                    st.caption("연구 범위: " + row["evidence_kind"] + " · " + row["study_conditions"])
                    st.caption("그대로 주장하지 않을 내용: " + " · ".join(row["avoid_claims"]))
                    st.link_button("역할 정보 출처", row["source_url"], key=f"ingredient_role_{row['ingredient_id']}")
        with all_cards:
            for row in catalog()["cards"]:
                st.markdown(f"**{row['name']}** — " + " · ".join(row["roles"]))
                st.caption(row["research_summary"])
            st.caption(catalog()["selection_note"])
