"""
[app/components/market_reference.py]
예상 매출 시나리오 화면 아래 「참고 자료」 탭에서 쓰는 시장 근거 조각.
(이전 「시장 근거 · 문구 비교」 화면의 공개 A/B 실험 보기를 옮겨 왔다. 참조용이며 매출 계산에 직접 쓰지 않는다.)
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.components.performance import trend_card

DATA = Path(__file__).resolve().parents[2] / "data" / "sales_forecast_reference" / "copy_comparison"


@st.cache_data(ttl=300, max_entries=1, show_spinner=False)
def _experiments() -> tuple[list[dict], dict]:
    pairs = [json.loads(x) for x in (DATA / "headline_comparisons.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    return pairs, manifest


def render_public_experiments(key: str = "fc_exp") -> None:
    """공개 A/B 실험 한 건씩 보기. 문구 변화 폭(예상 매출 03)의 출처 자료."""
    try:
        pairs, manifest = _experiments()
    except (OSError, ValueError) as err:
        st.error(f"공개 실험 자료를 읽지 못했습니다: {type(err).__name__}")
        return
    st.caption(f"미국 뉴스 제목 A/B 실험 {len(pairs)}건 · 예상 매출의 ‘움직임 크기’가 이 실험들의 변화 폭에서 나왔습니다. "
               "화장품 구매 실험이 아닙니다.")
    i = st.selectbox("실험 고르기", range(len(pairs)), key=key,
                     format_func=lambda n: f"{n + 1}. {pairs[n]['experiment_id']} · {pairs[n]['created_dates'][0]}")
    pair, obs = pairs[i], pairs[i]["observed"]
    for col, label, arm_key in zip(st.columns(2), ["A", "B"], ["a", "b"]):
        arm = pair[arm_key]
        with col, st.container(border=True):
            st.markdown(f"**문구 {label}**")
            st.write(arm["copy_text"])
            st.caption(f"노출 {arm['impressions']:,} · 클릭 {arm['clicks']:,}")
    c1, c2, c3 = st.columns(3)
    c1.metric("A 클릭률", f"{100 * obs['ctr_a']:.3f}%", border=True)
    c2.metric("B 클릭률", f"{100 * obs['ctr_b']:.3f}%", border=True)
    with c3:
        rel = obs["relative_difference"] * 100 if obs["relative_difference"] is not None else None
        trend_card("B − A 클릭률 차이", f"{obs['difference_b_minus_a_pp']:+.3f}pp", rel, "A 대비 상대 변화",
                   obs["difference_b_minus_a_pp"])
    low, high = obs["difference_95_interval_pp"]
    st.write(f"차이의 95% 구간: **{low:+.3f} ~ {high:+.3f}pp**")
    if obs["interval_includes_zero"]:
        st.caption("구간에 0이 포함돼, 이 비교만으로 어느 문구가 낫다고 단정하기 어렵습니다.")
    with st.container(horizontal=True):
        st.link_button("공식 데이터 설명", manifest["documentation_url"])
        st.link_button("데이터 품질 정정 안내", manifest["quality_update_url"])
    st.caption("Matias, Munger, Le Quere, Ebersole (2021) · Upworthy Research Archive · CC BY 4.0")
