"""Readable comparison cards and explicit user-entered performance scenarios."""

from html import escape

import streamlit as st

from app.services.copy_performance import compare_arms


def trend_card(title, value, change=None, note="", direction=None):
    delta = change if direction is None else direction
    state = (
        "up"
        if delta is not None and delta > 0
        else "down"
        if delta is not None and delta < 0
        else "flat"
    )
    color = {"up": "#d63838", "down": "#2563c9", "flat": "#667085"}[state]
    # Streamlit sanitizes inline SVG; use HTML/CSS geometry for a visible stair arrow.
    segments = [
        (0, 31, 17, 4),
        (13, 20, 4, 15),
        (13, 20, 17, 4),
        (26, 9, 4, 15),
        (26, 9, 17, 4),
        (39, 4, 4, 9),
    ]
    arrow = "".join(
        f'<span style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{color};border-radius:1px"></span>'
        for x, y, w, h in segments
    )
    arrow += f'<span style="position:absolute;left:35px;top:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:8px solid {color}"></span>'
    if state == "flat":
        arrow = f'<span style="position:absolute;left:0;top:19px;width:44px;height:3px;background:{color}"></span>'
    transform = "scaleY(-1)" if state == "down" else "none"
    text = f"{change:+.2f}%" if change is not None else "비교값 없음"
    if change == 0:
        text = "0.00% · 동일"
    accessible = (
        "상승"
        if state == "up"
        else "하락"
        if state == "down"
        else "변화 없음 또는 미측정"
    )
    st.html(f'''<div class="bw-perf-card" style="border:1px solid #dedbd4;border-radius:14px;padding:20px;background:#fffdf8;min-height:158px">
      <div style="font-size:14px;color:#667085">{escape(title)}</div>
      <div style="font-size:30px;font-weight:750;margin:6px 0;color:#182230">{escape(value)}</div>
      <div style="display:flex;align-items:center;gap:10px;color:{color};font-weight:700">
        <span class="bw-perf-arrow" role="img" aria-label="{accessible}" style="position:relative;display:inline-block;width:48px;min-width:48px;height:38px;transform:{transform}">{arrow}</span>
        <span>{escape(text)}</span></div>
      <div style="font-size:12px;color:#667085;margin-top:8px">{escape(note)}</div></div>''')


def render_performance(product_id):
    st.subheader("문구 A와 B의 성과 비교")
    st.caption(
        "A는 기존 문구, B는 추천 후보입니다. 현재 제품의 데이터만 입력해 주세요."
    )
    with st.expander("무엇을 어디서 가져와 입력하나요?", expanded=True):
        st.markdown("""| 입력 항목 | 사용할 데이터 |
|---|---|
| 노출·클릭 | 동일 제품·기간의 문구별 광고/실험 보고서 |
| 주문·판매 수량·순매출 | 동일 전환 집계 기간으로 연결된 문구별 구매 로그 |
| 계획 노출 | 앞으로 비교할 동일한 노출 규모에 대한 가정 |

공개 자료에 문구별 숫자가 없으면 **가정 시나리오**로 입력합니다. 제품 랭킹·리뷰 수·회사 매출을 대신 넣지 않습니다.
실측 비교는 같은 SKU·가격·행사·구성·이미지·위치·타깃·기간을 맞춰야 합니다.""")
    key = f"perf_{product_id}"
    with st.form(f"{key}_form"):
        basis = st.selectbox(
            "입력 데이터 구분", ["가정 시나리오", "공개 실측 자료"], key=f"{key}_basis"
        )
        source = st.text_input(
            "출처 또는 가정 설명",
            placeholder="공개 보고서 URL / 직접 설정한 가정임을 설명",
            key=f"{key}_source",
        )
        period = st.text_input(
            "측정 기간·전환 집계 기준",
            placeholder="시작~종료일, 클릭 후 7일 구매 등",
            key=f"{key}_period",
        )
        arms = {}
        for col, label in zip(st.columns(2), ["A", "B"]):
            with col:
                st.markdown(
                    f"**{label} · {'기존 문구' if label == 'A' else '추천 후보'}**"
                )
                text = st.text_input(f"{label} 문구 원문", key=f"{key}_{label}_copy")
                values = {}
                for field, name in [
                    ("impressions", "노출 수"),
                    ("clicks", "클릭 수"),
                    ("orders", "주문 수 (선택)"),
                    ("units", "판매 수량 (선택)"),
                    ("net_revenue", "순매출 원 (선택)"),
                ]:
                    values[field] = st.number_input(
                        f"{label} {name}",
                        min_value=0,
                        value=None,
                        step=1,
                        placeholder="미확보 시 비워 두세요",
                        key=f"{key}_{label}_{field}",
                    )
                arms[label] = dict(values, copy_text=text)
        planned = st.number_input(
            "A/B 각각에 적용할 계획 노출 수 (선택)",
            min_value=1,
            value=None,
            step=1000,
            key=f"{key}_planned",
            help="관측 수량/매출을 같은 노출 규모로 환산합니다. 입력 비율이 유지된다는 가정입니다.",
        )
        controlled = st.checkbox(
            "동일 SKU·조건·집계 기간을 확인했습니다", key=f"{key}_controlled"
        )
        submitted = st.form_submit_button("입력값으로 비교하기", type="primary")
    if submitted:
        try:
            if (
                not source.strip()
                or not arms["A"]["copy_text"].strip()
                or not arms["B"]["copy_text"].strip()
            ):
                raise ValueError("문구 A/B 원문과 출처 또는 가정 설명을 입력해 주세요.")
            if basis == "공개 실측 자료" and (not period.strip() or not controlled):
                raise ValueError(
                    "실측 자료는 측정·전환 기간과 동일 조건 확인이 필요합니다."
                )
            result = compare_arms(arms["A"], arms["B"], planned)
            st.session_state[f"{key}_result"] = {
                "result": result,
                "basis": basis,
                "source": source,
                "period": period,
                "arms": arms,
                "controlled": controlled,
            }
        except ValueError as err:
            st.session_state.pop(f"{key}_result", None)
            st.error(str(err))
    record = st.session_state.get(f"{key}_result")
    result = record["result"] if record else None
    st.divider()
    st.subheader("입력값 기반 결과")
    if record:
        st.info(f"{record['basis']} · 출처/가정: {record['source']}")
        st.caption(
            "노출 규모 환산 시나리오입니다. 학습된 매출 예측이나 문구의 인과 효과 추정이 아닙니다. 입력값은 이 브라우저 세션에만 유지됩니다."
        )
        st.write(
            f"**A:** {record['arms']['A']['copy_text']} → **B:** {record['arms']['B']['copy_text']}"
        )
    for col, metric in zip(st.columns(3), ["ctr", "net_revenue", "units"]):
        with col:
            if metric == "ctr":
                value = f"{100 * result['ctr_b']:.2f}%" if result else "입력 대기"
                note = (
                    f"A {100 * result['ctr_a']:.2f}% → B · 차이 {result['ctr_difference_pp']:+.3f}pp"
                    if result
                    else "노출·클릭 입력 후 계산"
                )
                trend_card(
                    "B 클릭률 · A 대비",
                    value,
                    result["ctr_relative_change_pct"] if result else None,
                    note,
                    result["ctr_difference_pp"] if result else None,
                )
            else:
                projection = result["projections"][metric] if result else {}
                amount = projection.get("b")
                title = (
                    "B 예상 순매출 · 시나리오"
                    if metric == "net_revenue"
                    else "B 예상 판매량 · 시나리오"
                )
                unit = "원" if metric == "net_revenue" else "개"
                note = (
                    f"각 {result['planned_impressions']:,}회 노출 가정 · A 대비"
                    if result and result["planned_impressions"]
                    else "해당 실측·가정값과 계획 노출 필요"
                )
                trend_card(
                    title,
                    f"{amount:,.0f}{unit}" if amount is not None else "산출 전",
                    projection.get("change_pct"),
                    note,
                    projection.get("difference"),
                )
    st.caption(
        "빨강 계단 ↑ 상승 · 파랑 계단 ↓ 하락 · 회색 — 동일/미측정. A가 0이면 상대 증가율은 계산하지 않습니다."
    )
    if result:
        st.caption(
            "계산: CTR=클릭÷노출 · 예상 수량=계획 노출×관측 수량÷관측 노출 · 예상 순매출=계획 노출×관측 순매출÷관측 노출. 주문 수는 판매 상품 개수와 다릅니다."
        )
