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
    st.markdown("#### 왜 뉴스 제목 실험을 참고하나요?")
    st.write("같은 기사에 제목 A와 B를 붙였을 때 클릭이 얼마나 달라졌는지 관찰한 자료입니다. "
             "위 화면에서는 그 차이의 크기를 빌려 ‘만약 매출이 이만큼 움직인다면?’을 계산합니다.")
    st.info("화장품 광고의 실제 성과 자료가 아닙니다. 19%를 참고해 계산해도 ‘추천 문구로 매출이 19% 오른다’는 뜻은 아닙니다.")
    with st.expander("원본 실험 확인하기 · 영어 제목 / 노출 / 클릭"):
        _render_experiment_detail(key)


def render_reference_guide(*, product_name: str, base_revenue: float,
                           exposed_share: float, change_pct: float,
                           change_amount: float, peer_count: int,
                           market_example: dict | None = None, own_copy: str = "") -> None:
    """현재 시나리오 입력값으로 자료의 역할과 계산 경로를 설명한다."""
    st.markdown("#### 이 자료가 우리 제품에 어떻게 연결되나요?")
    for col, title, body, limit in zip(
        st.columns(3),
        ["1 · 시장 제품 → 표현 참고", "2 · 우리 자료 → 사용 가능성 검토", "3 · 계획 수량 → 매출 시나리오"],
        [f"비슷한 제품 {peer_count}개의 문구에서 어떤 표현 유형을 쓰는지 봅니다.",
         "우리 제품의 기능성·시험 자료를 규정과 대조해 추천 후보를 만듭니다.",
         "판매가 × 월 계획 판매량으로 기준 매출을 계산합니다."],
        ["리뷰·순위는 인기 신호입니다. 문구의 판매 효과를 뜻하지 않습니다.",
         "경쟁사 시험 수치나 효능을 우리 제품의 근거로 가져오지 않습니다.",
         "판매량 입력값은 실적이 아닌 가정입니다. 실제 계획에 맞게 바꾸세요."],
    ):
        with col, st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)
            st.caption(limit)
    if market_example:
        st.markdown("#### 실제 문구로 보면")
        left, right = st.columns(2)
        with left, st.container(border=True):
            st.markdown("**시장에서 관찰한 표현**")
            st.caption(f"{market_example['brand']} · {market_example['name']}")
            st.write(market_example["copy"])
            st.caption("공개 페이지에서 수집한 원문입니다. 우리 제품에 그대로 복사하는 근거가 아닙니다.")
        with right, st.container(border=True):
            st.markdown("**우리 자료로 만든 후보**")
            st.caption(product_name)
            st.write(own_copy or "우리 제품 자료를 등록하면 후보를 확인할 수 있습니다.")
            st.caption("표현 방식만 참고하고, 수치·효능·시험 조건은 우리 제품 자료로 검토합니다. 두 문구의 매출 효과는 비교할 수 없습니다.")
    st.markdown(f"#### 현재 입력값으로 풀어보기 · {product_name}")
    with st.container(border=True):
        st.write(f"기준 월 매출 **{base_revenue:,.0f}원** 중 이 문구와 연결된 비중을 "
                 f"**{exposed_share:.0%}** 로 가정했습니다.")
        st.write(f"여기에 선택한 변화 폭 **±{change_pct:.2f}%** 를 가정하면:")
        st.code(f"{base_revenue:,.0f}원 × {exposed_share:.0%} × {change_pct:.2f}% ≈ {change_amount:,.0f}원", language=None)
        a, b = st.columns(2)
        a.metric("상승을 가정한 월 매출", f"{base_revenue + change_amount:,.0f}원", f"+{change_amount:,.0f}원", delta_color="inverse", border=True)
        b.metric("하락을 가정한 월 매출", f"{base_revenue - change_amount:,.0f}원", f"-{change_amount:,.0f}원", delta_color="inverse", border=True)
        st.caption("변화 폭은 뉴스 제목 실험의 클릭 차이에서 참고했습니다. "
                   "구매전환율·객단가가 고정된다는 가정이며, 화장품 매출의 예측 구간이 아닙니다.")
    st.success("다음 확인: 같은 제품·가격·행사·이미지·타깃 조건에서 기존 문구 A와 추천 문구 B를 테스트합니다. "
               "문구별 노출·클릭·주문·순매출이 확보되면 ‘실제 성과 비교’에 입력하세요.")


def _render_experiment_detail(key: str) -> None:
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
