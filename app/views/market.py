"""Read-only market evidence and exploratory comparison viewer."""

import json
from pathlib import Path

import streamlit as st

DATA = Path(__file__).resolve().parents[2] / "data" / "sales_forecast_reference"


@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def load_evidence():
    folder = DATA / "copy_comparison"
    cards = json.loads(
        (folder / "cosmetics_evidence_cards.json").read_text(encoding="utf-8")
    )
    pairs = [
        json.loads(line)
        for line in (folder / "headline_comparisons.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return cards, pairs, manifest


st.title("시장 근거 · 문구 비교")
st.caption("추천 문구의 시장 참고 사례와 공개 실험의 관측 결과를 확인합니다.")
try:
    cards, pairs, manifest = load_evidence()
except (OSError, ValueError) as err:
    st.error(
        f"시장 근거 데이터를 읽지 못했습니다: {type(err).__name__}. 데이터 파일을 확인해 주세요."
    )
    st.stop()

with st.container(horizontal=True):
    st.metric("화장품 제품", len(cards), border=True)
    st.metric("시장 문구", sum(len(c["observed_copies"]) for c in cards), border=True)
    st.metric("공개 제목 비교", len(pairs), border=True)

market_tab, experiment_tab = st.tabs(["화장품 시장 사례", "공개 문구 A/B 비교"])
with market_tab:
    st.info(
        "시장 관찰 자료입니다. 랭킹은 매출이 아니며, 이 문구가 판매 성과를 만들었다는 의미는 아닙니다."
    )
    selected = st.selectbox(
        "비교할 제품",
        range(len(cards)),
        format_func=lambda i: f"{cards[i]['brand']} · {cards[i]['product_name']}",
        key="market_product",
    )
    card = cards[selected]
    conditions = card["market_conditions"]
    st.caption(
        f"수집일 {card['market_observed_date']} · {conditions['ranking_type']} {conditions['ranking']}위"
    )
    st.link_button("수집 상품 페이지", card["market_source_url"])
    with st.container(horizontal=True):
        price = int(conditions["sale_price_krw"])
        st.metric("수집 당시 표시 가격", f"{price:,}원")
        st.metric("표시 할인율", f"{conditions['discount_percent_displayed']}%")
        st.metric("수집 당시 리뷰 수", f"{int(conditions['review_count']):,}")
    st.write(f"**구성:** {conditions['bundle']}")
    st.caption(
        f"행사: {conditions['sale_event']} · 랭킹 기간: {conditions['ranking_period']}"
    )
    table = [
        {
            "문구 ID": c["copy_id"],
            "실제 노출 문구": c["copy_text"],
            "위치": c["위치"],
            "소구 유형": ", ".join(c["문구 유형"] or []),
            "시험 조건 표기": c["시험 조건 표기 여부"],
        }
        for c in card["observed_copies"]
    ]
    st.dataframe(
        table, hide_index=True, alt="선택 제품의 실제 광고 문구와 위치 및 소구 유형"
    )
    st.subheader("추천 문구를 비교하려면")
    st.write(card["hypothesis"])
    st.caption(
        "규정·제품 근거 검증을 통과한 후보를 대상으로 비교합니다. 위 시장 원문에 판정을 부여한 상태는 아닙니다."
    )
    with st.container(horizontal=True):
        st.metric("화장품 문구 상승률", "미측정")
        st.metric("예상 매출", "산출 전")
        st.metric("예상 판매량", "산출 전")
    st.write(
        "필요한 실측: 후보별 노출·클릭·주문·수량·순매출·광고비와 동일한 전환 집계 기간."
    )

with experiment_tab:
    st.info(
        "미국 뉴스 제목 실험입니다. 클릭 비교 방법을 확인하는 자료이며 화장품 구매·매출 예상값에 적용하지 않습니다."
    )
    st.caption(
        "같은 실험·같은 이미지 / 각 노출 1,000 이상 / 배정 노출 비율 1.2 이하 / 문제 기간 제외. 성과순 정렬이 아닙니다."
    )
    selected_pair = st.selectbox(
        "공개 실험",
        range(len(pairs)),
        format_func=lambda i: (
            f"{i + 1}. {pairs[i]['experiment_id']} · {pairs[i]['created_dates'][0]}"
        ),
        key="market_experiment",
    )
    pair = pairs[selected_pair]
    observed = pair["observed"]
    for label, key in [("A", "a"), ("B", "b")]:
        arm = pair[key]
        with st.container(border=True):
            st.markdown(f"**문구 {label}**")
            st.write(arm["copy_text"])
            st.caption(
                f"노출 {arm['impressions']:,} · 클릭 {arm['clicks']:,} · CTR {100 * arm['clicks'] / arm['impressions']:.3f}%"
            )
    with st.container(horizontal=True):
        st.metric("A 클릭률", f"{100 * observed['ctr_a']:.3f}%")
        st.metric("B 클릭률", f"{100 * observed['ctr_b']:.3f}%")
        st.metric("B − A 클릭률 차이", f"{observed['difference_b_minus_a_pp']:+.3f}pp")
    low, high = observed["difference_95_interval_pp"]
    st.write(f"차이의 95% 구간: **{low:+.3f} ~ {high:+.3f}pp**")
    if observed["interval_includes_zero"]:
        st.warning(
            "구간에 0이 포함됩니다. 이 비교만으로 어느 문구의 클릭률이 더 높은지 단정하기 어렵습니다."
        )
    else:
        st.caption(
            "개별 탐색 구간에서 0을 포함하지 않습니다. 다중비교 보정 전 결과이며 보편적인 문구 효과를 의미하지 않습니다."
        )
    st.caption(
        "Newcombe 차이 구간 · Wilson 95% 비율 구간 사용. A/B 순서는 원문 정렬이며 승자 순서가 아닙니다."
    )
    st.link_button("공식 데이터 설명", manifest["documentation_url"])
    st.link_button("운영기관 데이터 품질 정정", manifest["quality_update_url"])
    st.caption(
        "Matias, Munger, Le Quere, Ebersole (2021) · Upworthy Research Archive · CC BY 4.0. 필터와 비교값을 추가한 가공 자료."
    )
