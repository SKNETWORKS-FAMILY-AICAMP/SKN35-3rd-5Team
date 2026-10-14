"""Read-only market evidence and exploratory comparison viewer."""

import json
from pathlib import Path

import altair as alt
import streamlit as st

from app.components.context import current
from app.components.performance import render_performance, trend_card
from app.services import backend
from app.services.market_evidence import load_reference_catalog, references_for

DATA = Path(__file__).resolve().parents[2] / "data" / "sales_forecast_reference"


@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def load_evidence():
    folder = DATA / "copy_comparison"
    catalog = load_reference_catalog()
    links = json.loads(
        (folder / "project_reference_links.json").read_text(encoding="utf-8")
    )
    pairs = [
        json.loads(line)
        for line in (folder / "headline_comparisons.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return catalog, links, pairs, manifest


st.title("시장 근거 · 문구 비교")
st.caption("추천 문구의 시장 참고 사례와 공개 실험의 관측 결과를 확인합니다.")
try:
    catalog, links, pairs, manifest = load_evidence()
except (OSError, ValueError) as err:
    st.error(
        f"시장 근거 데이터를 읽지 못했습니다: {type(err).__name__}. 데이터 파일을 확인해 주세요."
    )
    st.stop()

product, context = current()
profile, references = references_for(product["product_id"], catalog, links)
st.subheader(f"검토 대상: {product['name']}")
st.caption(
    f"{context['category_label']} · 선택 실증 {context['evidence_on']}/{context['evidence_total']} · 샘플 제품 데이터"
)
st.caption(
    f"프로젝트 {len(backend.list_products())}제품 · 현재 연결된 시장 참고 {len(references)}제품 · 공개 제목 비교 {len(pairs)}건"
)

market_tab, performance_tab, experiment_tab = st.tabs(
    ["제품 · 시장 근거", "성과 입력 · 비교", "공개 A/B 실험"]
)
with market_tab:
    st.markdown("#### 01 · 현재 제품의 근거")
    st.write(profile.get("purpose", "이 제품의 시장 참고 연결을 준비 중입니다."))
    if product.get("owned_evidence"):
        with st.expander("등록 실증 보기 · 출처와 원보고서 보유 여부 확인"):
            st.dataframe(
                product["owned_evidence"],
                hide_index=True,
                alt="선택한 프로젝트 샘플 제품의 보유 실증 자료",
            )
    else:
        st.caption(
            "현재 선택된 실증 자료가 없습니다. 사이드바에서 선택한 상태를 그대로 반영합니다."
        )
    ingredient_profile = profile.get("ingredient_profile")
    if ingredient_profile:
        st.caption(
            "실제 제품의 공개 전성분과 공식몰 시험 요약을 연결합니다. 내부 원보고서 보유를 의미하지 않습니다."
        )
        st.link_button("현재 제품 전성분 출처", ingredient_profile["source_url"])
        st.write(
            "**주요 소구 성분:** " + ", ".join(ingredient_profile["focus_ingredients"])
        )
        with st.expander("전성분·선별 기준 보기"):
            st.write(ingredient_profile["ingredient_text"])
            st.caption(ingredient_profile["focus_basis"])
    else:
        st.button(
            "성분 공개 샘플로 전환",
            on_click=lambda: st.session_state.update(
                bw_pid="PUBLIC_KIEHLS_UFC", proj_product="PUBLIC_KIEHLS_UFC"
            ),
        )
    st.divider()
    st.markdown("#### 02 · 연결된 시장 표현")
    st.caption(
        "외부 제품의 표현·판매 조건을 참고합니다. 외부 시험·판매 실적을 현재 제품에 적용하지 않습니다."
    )
    st.caption(profile.get("match_basis", "연결 기준 미등록"))
    if profile.get("collection_gap"):
        st.warning(profile["collection_gap"])
    if references:
        selected = st.selectbox(
            "연결된 외부 참고 제품",
            range(len(references)),
            format_func=lambda i: (
                f"{references[i]['brand']} · {references[i]['product_name']}"
            ),
            key=f"market_reference_{product['product_id']}",
        )
        card = references[selected]
        match = card.get("ingredient_comparison")
        if match:
            st.markdown("##### 성분 비교 · 함량과 효능의 유사도는 미측정")
            for col, label, values in zip(
                st.columns(3),
                ["공통 주요 소구 성분", "현재 제품에서 미확인", "공통 전성분"],
                [match["shared_focus"], match["reference_only_focus"], match["shared"]],
            ):
                with col:
                    st.metric(label, f"{len(values)}개", border=True)
            chart_rows = [
                {"비교 구분": "공통 성분", "성분 수": len(match["shared"])},
                {"비교 구분": "현재 제품만", "성분 수": len(match["target_only"])},
                {
                    "비교 구분": "참고 제품만",
                    "성분 수": len(match["reference_only"]),
                },
            ]
            base = alt.Chart(alt.Data(values=chart_rows)).encode(
                x=alt.X(
                    "비교 구분:N",
                    sort=["공통 성분", "현재 제품만", "참고 제품만"],
                    title=None,
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "성분 수:Q",
                    title="확인된 성분 개수",
                    scale=alt.Scale(
                        domain=[0, max(r["성분 수"] for r in chart_rows) * 1.2]
                    ),
                ),
            )
            bars = base.mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                color=alt.Color(
                    "비교 구분:N",
                    scale=alt.Scale(
                        domain=["공통 성분", "현재 제품만", "참고 제품만"],
                        range=["#208982", "#84bcb2", "#c1cbd3"],
                    ),
                    legend=None,
                ),
                tooltip=["비교 구분:N", "성분 수:Q"],
            )
            labels = base.mark_text(
                dy=-10, fontSize=18, fontWeight="bold", color="#182230"
            ).encode(text="성분 수:Q")
            st.altair_chart(
                (bars + labels).properties(height=230),
                width="stretch",
                alt=f"공통 성분 {len(match['shared'])}개와 각 제품에서만 확인된 성분 개수 비교. 효능 개선율이 아님",
            )
            st.write(
                "**표현 방식 참고 가능:** "
                + ", ".join(match["shared_focus"])
                + " 성분명 소구"
            )
            st.write(
                "**현재 제품에 옮기지 않을 소구:** "
                + (", ".join(match["reference_only_focus"]) or "별도 추가 성분 없음")
            )
            with st.expander("성분명별 공통·차이 전체 보기"):
                st.write(
                    {
                        "공통": match["shared"],
                        "현재 제품만": match["target_only"],
                        "참고 제품만": match["reference_only"],
                    }
                )
            st.caption(
                card["ingredient_profile"].get("market_note", "공식 전성분 기준")
            )
        conditions = card["market_conditions"]
        st.caption(f"외부 자료 수집일 {card['market_observed_date']}")
        st.link_button("외부 상품·자료 페이지", card["market_source_url"])
        with st.container(horizontal=True):
            price = conditions.get("sale_price_krw")
            discount = conditions.get("discount_percent_displayed")
            st.metric(
                "외부 표시 가격", f"{int(price):,}원" if price is not None else "미확인"
            )
            st.metric(
                "외부 표시 할인율", f"{discount}%" if discount is not None else "미확인"
            )
        st.write(f"**외부 구성:** {conditions.get('bundle') or '미확인'}")
        st.caption(
            f"가격 조건: {conditions.get('sale_event') or '미확인'} · 순위: {conditions.get('ranking') or '미확인'}"
        )
        for copy in card["observed_copies"]:
            with st.container(border=True):
                st.write(f"**{copy['copy_text']}**")
                st.caption(
                    f"{copy['위치']} · {', '.join(copy['문구 유형'] or []) or '유형 미분류'}"
                )
                with st.expander("출처 · 조건 확인"):
                    st.write(copy["시험 조건 표기 여부"])
                    st.link_button(
                        "문구 출처",
                        copy["source_url"],
                        key=f"market_source_{product['product_id']}_{copy['copy_id']}",
                    )
        if match and match["shared_focus"]:
            st.divider()
            st.markdown("#### 03 · 공통 성분 소구 → 제품 기준 검토")
            seed = f"{', '.join(match['shared_focus'])}을 함유한 데일리 크림"
            draft = st.text_input(
                "검토할 문구 초안",
                value=seed,
                key=f"ingredient_draft_{product['product_id']}_{card['product_id']}",
            )
            st.caption(
                "성분명 함유 사실을 활용한 검토 전 초안입니다. 외부 효능·수치·추가 성분은 가져오지 않았습니다."
            )
            if st.button(
                "우리 규정·보유 근거로 판정·교정",
                key=f"ingredient_review_{product['product_id']}",
            ):
                try:
                    with st.spinner("기존 판정·교정 시스템으로 검토 중입니다…"):
                        response = backend.review_copy(draft, product)
                    result = response["result"]
                    mode = "데모 판정" if backend.data_mode() == "mock" else "API 판정"
                    st.write(
                        f"**{mode}:** {result.get('status')} · 단계 {result.get('level')}"
                    )
                    st.write(
                        "**추천/교정:** "
                        + (
                            result.get("suggestion")
                            or "별도 교정 문구 없음. 원문 판정과 근거를 확인하세요."
                        )
                    )
                    with st.expander("판정 근거·결과 보기"):
                        st.json(result)
                except backend.BackendError as err:
                    st.error(err.message)
    else:
        st.write(
            "성분 기준을 충족하는 참고 사례가 없습니다. 성분 미등록 제품은 기존의 제형 기반 연결도 보류합니다."
        )
    if profile.get("excluded_ingredient_references"):
        with st.expander("선별에서 제외한 제품 · 이유"):
            for excluded in profile["excluded_ingredient_references"]:
                st.write(
                    f"**{excluded['profile']['name']}:** {excluded['comparison']['reason']}"
                )
    st.caption(
        "성과 수치를 비교하려면 ‘성과 입력 · 비교’ 탭에서 문구 A/B의 데이터를 입력하세요."
    )

with performance_tab:
    render_performance(product["product_id"])

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
    for col, label, key in zip(st.columns(2), ["A", "B"], ["a", "b"]):
        arm = pair[key]
        with col, st.container(border=True):
            st.markdown(f"**문구 {label}**")
            st.write(arm["copy_text"])
            st.caption(f"노출 {arm['impressions']:,} · 클릭 {arm['clicks']:,}")
    for col, title, value in zip(
        st.columns(3),
        ["A 클릭률", "B 클릭률", "B − A 클릭률 차이"],
        [
            f"{100 * observed['ctr_a']:.3f}%",
            f"{100 * observed['ctr_b']:.3f}%",
            f"{observed['difference_b_minus_a_pp']:+.3f}pp",
        ],
    ):
        with col:
            trend_card(
                title,
                value,
                observed["relative_difference"] * 100
                if title.startswith("B −")
                and observed["relative_difference"] is not None
                else None,
                "A 대비 상대 변화" if title.startswith("B −") else "관측 클릭률",
                observed["difference_b_minus_a_pp"]
                if title.startswith("B −")
                else None,
            )
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
