"""
[app/views/forecast.py]
예상 매출 시나리오 — 선택한 제품의 실제 가격·실제 광고 문구를 불러와,
원문을 그대로 쓸 때의 처분 위험 매출·판매량과 문구를 바꿀 때 움직일 수 있는 폭을 보여준다.

계산: app/services/revenue_scenario.py
제품 연결: app/services/product_market.py (가격 offers.json · 실제 문구 market_copy_judgements.jsonl)
근거: data/sales_forecast_reference/ (D1 처분 기준, D5 문구 효과 분포)
가정 기반 시나리오이며 학습된 예측이 아니다. 이 제품의 공개 매출·판매량은 없어 판매량은 가정 입력이다.

표시 규칙: 오르면 빨간색 ▲, 내리면 파란색 ▼, 변화 없음은 회색.
"""
from __future__ import annotations

from html import escape

import altair as alt
import streamlit as st

from app.components.context import current
from app.components.layout import esc, html, page_header
from app.components.theme import inject_css
from app.services import backend
from app.services.product_market import latest_review_pair, market_profile
from app.services.revenue_scenario import DISPLAY_LABEL, build_scenario

health = st.session_state["bw_health"]
inject_css("pages")
product, ctx = current()
pid = ctx["product_id"]

UP, DOWN, FLAT = "#d63838", "#2563c9", "#667085"
LEVEL_TEXT = {0: ("가능", "green"), 1: ("조건부 · 근거 확인 필요", "orange"), 2: ("불가 · 표현 주의", "red"),
              None: ("판단 보류", "gray")}
EFFECT_LEVELS = {
    "small": {"q": "p25", "name": "조금 움직일 때", "hint": "실험 4건 중 1건은 이보다 덜 움직였어요"},
    "typical": {"q": "median", "name": "보통 움직일 때", "hint": "실험의 절반이 이 정도 안에서 움직였어요"},
    "large": {"q": "p75", "name": "많이 움직일 때", "hint": "실험 4건 중 3건이 이 범위 안이었어요"},
}
FALLBACK_COPY = "손상된 피부를 재생시켜 주는 크림"
SUGGEST_CACHE = "bw_forecast_suggest"   # {(제품, 원문): 엔진 제안 문구}


def won(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ("−" if value < 0 else "")
    v = abs(value)
    if v >= 1e8:
        body = f"{v / 1e8:,.2f}억 원"
    elif v >= 1e4:
        body = f"{v / 1e4:,.0f}만 원"
    else:
        body = f"{v:,.0f}원"
    return sign + body


def units(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ""
    return f"{sign}{abs(value):,.0f}개"


def arrow_card(title: str, value: str, direction: int, change_text: str, note: str = "") -> None:
    """direction: 1 상승(빨강 ▲) / -1 하락(파랑 ▼) / 0 변화 없음(회색 ■)"""
    color = UP if direction > 0 else DOWN if direction < 0 else FLAT
    arrow = "▲" if direction > 0 else "▼" if direction < 0 else "■"
    label = "상승" if direction > 0 else "하락" if direction < 0 else "변화 없음"
    st.html(
        f'<div style="border:1px solid #dedbd4;border-radius:14px;padding:18px 20px;background:#fffdf8;min-height:150px">'
        f'<div style="font-size:14px;color:#667085">{escape(title)}</div>'
        f'<div style="display:flex;align-items:center;gap:12px;margin:8px 0">'
        f'<span role="img" aria-label="{label}" style="font-size:34px;line-height:1;color:{color}">{arrow}</span>'
        f'<span style="font-size:30px;font-weight:750;color:#182230">{escape(value)}</span></div>'
        f'<div style="color:{color};font-weight:700;font-size:15px">{escape(change_text)}</div>'
        f'<div style="font-size:12px;color:#667085;margin-top:6px">{escape(note)}</div></div>'
    )


market = market_profile(product)
review = latest_review_pair(st.session_state.get("bw_threads"), pid)

page_header(
    "예상 매출 시나리오",
    "선택한 제품의 실제 가격·광고 문구로, 원문을 그대로 쓸 때의 처분 위험과 문구를 바꿀 때 움직일 수 있는 매출·판매량을 봅니다.",
    health=health,
)
html(
    f'<div class="bw-hint"><span class="material-symbols-rounded">calculate</span><div>'
    f'<b>{esc(ctx["product_name"])}</b> · {esc(ctx["category_label"])} · 사용 실증 {ctx["evidence_on"]}/{ctx["evidence_total"]}<br>'
    f'<span>{esc(DISPLAY_LABEL)}. 제품은 왼쪽 「프로젝트」에서 바꿉니다.</span></div></div>'
)

with st.container(key="pagebody"):
    # ------------------------------------------------------------------ 00 제품 실제 자료
    st.markdown("#### 00 · 이 제품의 실제 자료")
    if market:
        s1, s2, s3 = st.columns(3)
        with s1, st.container(border=True):
            st.caption("판매가 (공개 페이지 표시가)")
            if market["offers"]:
                o = market["offers"][0]
                st.markdown(f"### {o['price_krw']:,}원")
                st.caption(f"{o['channel']} · {o['bundle_note']}")
            else:
                st.markdown("### 미수집")
        with s2, st.container(border=True):
            st.caption("수집한 실제 광고 문구")
            st.markdown(f"### {len(market['copies'])}건")
            st.caption("공식몰 상세페이지 문구 · 규칙 판정 완료")
        with s3, st.container(border=True):
            st.caption("공개 매출 · 판매량")
            st.markdown("### 있음" if (market["units_public"] or market["revenue_public"]) else "### 공개 자료 없음")
            st.caption("그래서 판매량은 아래에서 가정으로 입력합니다")
        if market["copies"]:
            with st.expander(f"실제 문구 {len(market['copies'])}건 · 규칙 판정 보기"):
                for c in market["copies"]:
                    label, color = LEVEL_TEXT.get(c["level"], LEVEL_TEXT[None])
                    cc1, cc2 = st.columns([4, 1.4])
                    cc1.write(f"“{c['copy_text']}”")
                    with cc2:
                        st.badge(label, color=color)
    else:
        st.info("이 제품은 수집한 시장 자료(가격·실제 문구)와 연결돼 있지 않습니다. 판매가·문구를 직접 입력해 주세요.")

    # ------------------------------------------------------------------ 입력
    st.markdown("##### 비교할 문구")
    sources: list[tuple[str, str]] = []           # (라벨, 문구)
    if review and review["original"]:
        sources.append(("검토 대화에서 마지막으로 검토한 문구", review["original"]))
    for c in (market or {}).get("copies", []):
        sources.append((f"실제 문구 · {c['copy_text']}", c["copy_text"]))
    sources.append(("직접 입력", ""))
    # 검토 대화 문구가 없으면 판정 등급이 가장 높은(위험한) 실제 문구를 먼저 보여준다
    first = 0
    if not (review and review["original"]) and (market or {}).get("copies"):
        levels = [c["level"] if c["level"] is not None else -1 for c in market["copies"]]
        first = levels.index(max(levels))
    pick = st.selectbox("원문 불러오기", range(len(sources)), index=first, format_func=lambda i: sources[i][0],
                        key=f"fc_src_{pid}")
    preset = sources[pick][1] or FALLBACK_COPY

    cache = st.session_state.setdefault(SUGGEST_CACHE, {})
    suggestion = None
    if review and review["original"] == preset and review.get("suggestion"):
        suggestion = review["suggestion"]
    suggestion = cache.get((pid, ctx["signature"], preset), suggestion)

    c1, c2 = st.columns(2)
    with c1:
        original = st.text_area("원문 광고 문구", value=preset, height=90, key=f"fc_orig_{pid}_{pick}")
    with c2:
        recommended = st.text_area(
            "추천(수정) 문구", value=suggestion or "", height=90,
            key=f"fc_rec_{pid}_{pick}_{bool(suggestion)}",
            placeholder="오른쪽 아래 버튼으로 엔진 제안을 받거나 직접 입력하세요",
        )
        if st.button("이 원문으로 추천 문구 받기", icon=":material/auto_fix_high:", key=f"fc_suggest_{pid}_{pick}"):
            with st.spinner("보유 실증 기준으로 추천 문구를 찾는 중…"):
                try:
                    resp = backend.review_copy(original, product)
                    cache[(pid, ctx["signature"], original)] = resp.get("result", {}).get("suggestion") or ""
                except Exception as err:  # 백엔드 연결 실패 시 화면은 유지
                    st.error(f"추천 문구를 받지 못했습니다: {err}")
                else:
                    st.rerun()
        if cache.get((pid, ctx["signature"], original)) == "":
            st.caption("엔진이 이 원문에 대한 대체 문구를 내지 않았습니다(판단 보류이거나 이미 쓸 수 있는 문구). 직접 입력해 비교할 수 있어요.")

    st.markdown("##### 판매 가정")
    offers = (market or {}).get("offers", [])
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        default_price = offers[0]["price_krw"] if offers else 27500
        price = st.number_input("1개 판매가 (원)", min_value=0, value=default_price, step=500, key=f"fc_price_{pid}",
                                help=(f"{offers[0]['channel']} 표시가 · {offers[0]['qualifier']}" if offers
                                      else "공개 가격 미수집 — 직접 입력"))
    with p2:
        units_low = st.number_input("월 판매량 · 적게 팔릴 때", min_value=0, value=300, step=50, key=f"fc_ul_{pid}")
    with p3:
        units_mid = st.number_input("월 판매량 · 평소", min_value=0, value=600, step=50, key=f"fc_um_{pid}")
    with p4:
        units_high = st.number_input("월 판매량 · 잘 팔릴 때", min_value=0, value=1200, step=50, key=f"fc_uh_{pid}")
    st.caption("판매가는 수집한 공개 표시가가 기본값입니다. 판매량은 공개 자료가 없어 예시값이 들어 있으니 실제 값으로 바꿔 넣으세요.")

    with st.expander("노출·처분 조건", expanded=False):
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            exposed = st.slider("이 문구를 보고 들어오는 매출 비중", 0, 100, 100, format="%d%%",
                                help="상세페이지·광고 등 이 문구가 노출되는 경로에서 나오는 매출의 비중")
        with q2:
            know_ad = st.checkbox("광고로 들어오는 매출 비중을 알고 있음", value=False)
            ad_share = st.slider("광고로 들어오는 매출 비중", 0, 100, 40, format="%d%%", disabled=not know_ad)
        with q3:
            sanction = st.radio("위반 위치", ["광고", "표시"], horizontal=True,
                                help="광고 위반 → 광고업무정지 / 용기·포장 표시 위반 → 판매업무정지")
        with q4:
            offense = st.selectbox("위반 차수", [1, 2, 3, 4], format_func=lambda n: f"{n}차" if n < 4 else "4차 이상")

    if not (units_low <= units_mid <= units_high):
        st.error("월 판매량은 적게 ≤ 평소 ≤ 잘 팔릴 때 순서로 입력해 주세요.")
        st.stop()
    if price <= 0 or units_mid <= 0:
        st.info("판매가와 월 판매량을 입력하면 계산합니다.")
        st.stop()

    common = dict(price_krw=price, monthly_units={"low": units_low, "mid": units_mid, "high": units_high},
                  product=product, offense=offense, sanction_kind=sanction,
                  ad_dependent_share=ad_share / 100 if know_ad else None,
                  copy_exposed_share=exposed / 100)
    try:
        before = build_scenario(copy_text=original, **common)
        after = build_scenario(copy_text=recommended, **common) if recommended.strip() else None
    except ValueError as err:
        st.error(str(err))
        st.stop()

    revenue = before["monthly_revenue_krw"]
    base = revenue["mid"]

    # ------------------------------------------------------------------ 01
    st.markdown("#### 01 · 한 달 매출 · 판매량 (가정)")
    m1, m2, m3 = st.columns(3)
    m1.metric("적게 팔릴 때", won(revenue["low"]), units(units_low), delta_color="off", delta_arrow="off", border=True)
    m2.metric("평소", won(revenue["mid"]), units(units_mid), delta_color="off", delta_arrow="off", border=True)
    m3.metric("잘 팔릴 때", won(revenue["high"]), units(units_high), delta_color="off", delta_arrow="off", border=True)

    # ------------------------------------------------------------------ 02
    st.markdown("#### 02 · 원문 그대로 vs 추천 문구 — 적발되면 잃을 수 있는 매출·판매량")

    def risk_card(title: str, text: str, scen: dict) -> None:
        level = scen["inputs"]["level"]
        label, color = LEVEL_TEXT.get(level, LEVEL_TEXT[None])
        risk = scen["revenue_at_risk_if_unchanged"]
        st.markdown(f"**{title}**")
        st.caption(text)
        st.badge(f"규칙 판정 · {label}", color=color)
        if risk["status"] == "no_violation":
            arrow_card("처분 위험 매출", "없음", 0, "처분 대상 표현 없음",
                       "규칙상 처분 대상 표현이 확인되지 않았습니다.")
            return
        if risk["status"] == "needs_review":
            arrow_card("처분 위험 매출", "개별 검토", 0, "처분표와 연결되지 않은 조항", risk.get("note") or "")
            return
        amount = risk.get("amount_krw") or risk.get("estimate_krw") or risk["upper_bound_krw"]
        kind = ("판매 정지 기간 매출" if risk.get("amount_krw")
                else "광고 매출 추정" if risk.get("estimate_krw") else "최대치 (모든 매출이 광고로 들어온다고 가정)")
        lost_units = amount["mid"] / price
        arrow_card(
            f"{risk['condition']} · {risk['sanction']} {risk['months']}개월",
            won(-amount["mid"]), -1,
            f"{risk['months']}개월 동안 최대 {won(amount['mid'])} · 약 {units(lost_units)} 덜 팔림",
            f"{kind} · 범위 {won(amount['low'])} ~ {won(amount['high'])} · 근거 {risk['basis_law_id']}",
        )
        if risk.get("unmapped_law_ids"):
            st.caption(f"처분표에 없는 조항(개별 검토): {', '.join(risk['unmapped_law_ids'])}")

    r1, r2 = st.columns(2)
    with r1, st.container(border=True):
        risk_card("원문 그대로 사용", original, before)
    with r2, st.container(border=True):
        if after:
            risk_card("추천 문구 사용", recommended, after)
        else:
            st.info("추천 문구를 받거나 입력하면 처분 위험을 나란히 비교합니다.")
    st.caption("적발 확률은 공개 자료로 추정할 수 없어 표시하지 않습니다. 위반이 여러 개면 가장 무거운 기준 하나만 씁니다. 감경·가중은 반영하지 않습니다.")

    # ------------------------------------------------------------------ 03
    band = before["copy_change_band"]
    st.markdown("#### 03 · 문구를 바꾸면 한 달 매출·판매량이 이만큼 움직일 수 있어요")
    st.caption("문구 교체 효과는 오를지 내릴지 미리 알 수 없어요. 그래서 반응이 좋을 때(▲)와 나쁠 때(▼)를 함께 보여줍니다.")

    choice = st.segmented_control(
        "움직임 크기", options=list(EFFECT_LEVELS), default="typical",
        format_func=lambda k: EFFECT_LEVELS[k]["name"], key="forecast_effect_level",
    ) or "typical"
    sel = EFFECT_LEVELS[choice]
    pct = band["change_magnitude_pct"][sel["q"]]
    delta = band["change_magnitude_krw"][sel["q"]]
    delta_units = delta / price

    a1, a2 = st.columns(2)
    with a1:
        arrow_card("반응이 좋을 때", won(base + delta), 1,
                   f"+{pct}% · {won(delta, signed=True)} · {units(delta_units, signed=True)}",
                   f"평소 {won(base)} · {units(units_mid)} 기준 → 약 {units(units_mid + delta_units)}")
    with a2:
        arrow_card("반응이 나쁠 때", won(base - delta), -1,
                   f"−{pct}% · {won(-delta, signed=True)} · {units(-delta_units, signed=True)}",
                   f"평소 {won(base)} · {units(units_mid)} 기준 → 약 {units(max(units_mid - delta_units, 0))}")
    st.caption(f"‘{sel['name']}’ = {sel['hint']} (비교 실험 148건 기준)")

    rows = []
    for lv in EFFECT_LEVELS.values():
        d = band["change_magnitude_krw"][lv["q"]]
        rows.append({"크기": lv["name"], "low": (base - d) / 1e4, "base": base / 1e4, "high": (base + d) / 1e4,
                     "picked": lv["name"] == sel["name"]})
    order = [lv["name"] for lv in EFFECT_LEVELS.values()]
    y = alt.Y("크기:N", sort=order, title=None, axis=alt.Axis(labelFontSize=13))
    fade = alt.condition("datum.picked", alt.value(1), alt.value(0.35))
    rule = alt.Chart().mark_rule(strokeWidth=6, color=FLAT).encode(
        y=y, x=alt.X("low:Q", title="한 달 매출 (만 원)", scale=alt.Scale(zero=False)), x2="high:Q",
        opacity=alt.condition("datum.picked", alt.value(0.45), alt.value(0.15)))
    down = alt.Chart().mark_point(filled=True, size=220, shape="triangle-down", color=DOWN).encode(
        y=y, x="low:Q", opacity=fade, tooltip=[alt.Tooltip("low:Q", title="반응이 나쁠 때(만 원)", format=",.0f")])
    up = alt.Chart().mark_point(filled=True, size=220, shape="triangle-up", color=UP).encode(
        y=y, x="high:Q", opacity=fade, tooltip=[alt.Tooltip("high:Q", title="반응이 좋을 때(만 원)", format=",.0f")])
    mid = alt.Chart().mark_tick(thickness=3, size=26, color="#182230").encode(
        y=y, x="base:Q", tooltip=[alt.Tooltip("base:Q", title="평소(만 원)", format=",.0f")])
    chart = alt.layer(rule, down, up, mid, data=alt.Data(values=rows)).properties(height=190)
    st.altair_chart(chart, width="stretch")
    st.caption("▼ 파란색: 반응이 나쁠 때 · ▲ 빨간색: 반응이 좋을 때 · 검은 선: 평소 매출 · 진하게 보이는 줄이 지금 고른 크기")

    st.warning(
        "이 폭은 미국 뉴스 제목 클릭 실험(148쌍)에서 관찰된 ‘문구만 바꿨을 때의 변화 크기’를 빌려온 가정입니다. "
        "화장품 구매·매출 상승률이 아니며, 추천 문구별 효과는 알 수 없어 후보 A/B/C에 같은 폭을 적용합니다."
    )

    with st.expander("가정 · 출처 보기"):
        st.write({
            "가정": before["assumptions"], "제공하지 않는 값": before["not_provided"],
            "원문 위반 조항(law_id)": before["inputs"]["law_ids"],
            "연결된 시장 자료": (market or {}).get("market_product_id") or "없음",
            "판매가 출처": offers[0]["label"] + " · " + offers[0]["qualifier"] if offers else "직접 입력",
            "근거 파일": ["data/market_reference/offers.json",
                      "data/sales_forecast_reference/copy_comparison/market_copy_judgements.jsonl",
                      "data/sales_forecast_reference/penalty_schedule.json",
                      "data/sales_forecast_reference/copy_effect_size_distribution.json"],
        })
