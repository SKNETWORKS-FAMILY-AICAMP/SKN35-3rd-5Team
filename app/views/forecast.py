"""
[app/views/forecast.py]
예상 매출 시나리오 — 새로 등록한 우리 제품을 비슷한 시장 제품과 비교해, 최적 문구와 예상 매출을 본다.

흐름
  ① 비슷한 시장 제품 찾기   app/services/peer_market.py  (성분·기능성·제형으로 매칭, 가격·랭킹·리뷰·공개 판매 신호)
  ② 경쟁 제품의 문구 분석   문구 유형별 사용 현황 + 규칙 판정
  ③ 생성 후보 비교 · 예상 매출   광고문 생성 후보 3개를 카드로 — 후보마다 ▲/▼ 한 달 매출·판매량, 선택하면 아래에 크게
  참고                       계산 근거·공개 실험·실제 성과 입력 (접어 둠)

경쟁 제품의 매출은 거의 공개되지 않는다 — 랭킹·리뷰 수는 인기 신호이고 매출이 아니다. 판매량은 가정 입력이다.
표시 규칙: 오르면 빨간색 ▲, 내리면 파란색 ▼, 변화 없음은 회색.
"""
from __future__ import annotations

import re
from html import escape

import altair as alt
import streamlit as st

from app.components.context import current, open_register, register_product
from app.components.layout import page_header
from app.components.market_reference import render_public_experiments
from app.components.performance import render_performance
from app.components.theme import inject_css
from app.services import generation_results
from app.services.peer_market import (
    FORMS,
    appeal_summary,
    candidate_copies,
    find_peers,
    form_of,
    judge_candidates,
    load_market_products,
    price_benchmark,
    product_profile,
)
from app.services.revenue_scenario import Range3, copy_change_band

health = st.session_state["bw_health"]
inject_css("pages")
generation_results.receive_forecast()
product, ctx = current()
pid = ctx["product_id"]

UP, DOWN, FLAT = "#d63838", "#2563c9", "#667085"
SAFE, CAUTION, RISK = "#2e9e6b", "#e0a030", "#c2410c"
LEVEL_TEXT = {0: ("쓸 수 있음", "green"), 1: ("근거 필요", "orange"), 2: ("쓰면 안 됨", "red"), None: ("판단 보류", "gray")}
TIER_EFFECT = {"strong": "large", "balanced": "typical", "safe": "small"}  # 표현 강도 → 반응 폭 가정
TIER_LABEL = {"strong": "강한 표현", "balanced": "균형", "safe": "가장 안전"}
EFFECT_LEVELS = {
    "small": {"q": "p25", "name": "조금 움직일 때", "hint": "실험 4건 중 1건은 이보다 덜 움직였어요"},
    "typical": {"q": "median", "name": "보통 움직일 때", "hint": "실험의 절반이 이 정도 안에서 움직였어요"},
    "large": {"q": "p75", "name": "많이 움직일 때", "hint": "실험 4건 중 3건이 이 범위 안이었어요"},
}
EXAMPLE_PRODUCT = {
    "name": "비타민A 브라이트닝 앰플",
    "category": "기능성",
    "functional_type": "피부 미백, 주름 개선",
    "key_ingredients": ["레티놀", "나이아신아마이드", "아데노신"],
    "form": "세럼·앰플",
    "price_krw": 32000,
    "owned_evidence": [{"test_type": "인체적용시험", "item": "눈가 주름 개선",
                        "value": "8주 사용 후 눈가 주름 15% 개선", "institute": "예시 피부임상연구소"}],
    "example": True,
}


def won(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ("−" if value < 0 else "")
    v = abs(value)
    body = f"{v / 1e8:,.2f}억 원" if v >= 1e8 else f"{v / 1e4:,.0f}만 원" if v >= 1e4 else f"{v:,.0f}원"
    return sign + body


def units(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ""
    return f"{sign}{abs(value):,.0f}개"


def short(name: str) -> str:
    return re.sub(r"\[[^\]]*\]\s*", "", name).strip()


def chip(text: str, color: str = "#475467", bg: str = "#f2f4f7") -> str:
    return (f'<span style="display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;border-radius:999px;'
            f'font-size:12px;color:{color};background:{bg}">{escape(text)}</span>')


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


def step(no: str, title: str, sub: str = "") -> None:
    st.html(
        f'<div style="display:flex;align-items:baseline;gap:12px;margin:26px 0 6px">'
        f'<span style="font-size:13px;font-weight:700;color:#fff;background:#182230;border-radius:999px;'
        f'padding:3px 10px">{escape(no)}</span>'
        f'<span style="font-size:22px;font-weight:750;color:#182230">{escape(title)}</span></div>'
        + (f'<div style="font-size:14px;color:#667085;margin-bottom:6px">{escape(sub)}</div>' if sub else "")
    )


page_header(
    "예상 매출 시나리오",
    "우리 제품을 비슷한 시장 제품과 비교해, 쓸 수 있는 가장 좋은 문구와 그 문구로 기대할 수 있는 매출을 봅니다.",
    health=health,
)

with st.container(key="pagebody"):
    # 기존 등록 세션도 재등록 없이 잘못 선택된 제형을 바로잡을 수 있다.
    registered_product = product  # 광고문 생성 결과는 등록 제품 기준으로 찾는다 (아래 제형 보정은 시장 비교용)
    inferred_form = form_of(product.get("name", ""))
    if pid.startswith("CUSTOM_"):
        default_form = inferred_form or product.get("form")
        selected_form = st.selectbox(
            "시장 비교 제형", FORMS,
            index=FORMS.index(default_form) if default_form in FORMS else None,
            key=f"fc_match_form_{pid}",
            help="등록한 제품의 제형을 확인하세요. 토너는 토너끼리 비교합니다.",
        )
        if inferred_form and product.get("form") and inferred_form != product["form"]:
            st.caption(f"등록 제형은 {product['form']}이지만 제품명은 {inferred_form}로 읽힙니다. 위 선택값으로 비교합니다.")
        product = dict(product, form=selected_form)
    # ------------------------------------------------------------------ 우리 제품
    me = product_profile(product)
    is_custom = pid.startswith("CUSTOM_")
    with st.container(border=True):
        top_l, top_r = st.columns([3, 2], vertical_alignment="center")
        with top_l:
            st.caption("우리 제품" + (" · 예시 입력값" if product.get("example") else ""))
            st.markdown(f"### {product['name']}")
            meta = [ctx["category_label"], me["form"] or "제형 미입력",
                    f"판매가 {product['price_krw']:,}원" if product.get("price_krw") else "판매가 미입력",
                    f"보유 실증 {ctx['evidence_on']}/{ctx['evidence_total']}"]
            st.html("".join(chip(m) for m in meta)
                    + "".join(chip(i, "#0f5c55", "#e3f2ef") for i in product.get("key_ingredients", [])))
        with top_r:
            with st.container(horizontal=True, horizontal_alignment="right"):
                if st.button("새 제품 등록", icon=":material/add:", key="fc_register", type="primary" if not is_custom else "secondary"):
                    open_register("proj")
                if st.button("예시로 해보기 · 비타민A 앰플", icon=":material/science:", key="fc_example"):
                    register_product(dict(EXAMPLE_PRODUCT, owned_evidence=[dict(e) for e in EXAMPLE_PRODUCT["owned_evidence"]]))
                    st.rerun()
        if not is_custom:
            st.caption("지금은 기본 샘플 제품입니다. 새 제품을 등록하면(제형·주요 성분·판매가) 그 제품과 비슷한 시장 제품을 찾아 비교합니다.")

    peers = find_peers(product)

    # ------------------------------------------------------------------ ① 비슷한 시장 제품
    step("1", f"비슷한 시장 제품 {len(peers)}개", "같은 제형 중 주요 성분 또는 기능성이 겹치는 제품만 비교합니다.")
    same_form_count = sum(p["form"] == me["form"] for p in load_market_products())
    st.caption(f"수집 자료 중 {me['form'] or '선택 제형'} {same_form_count}행 → 성분·기능성 조건에 맞는 비교 제품 {len(peers)}개. 주요 성분 키워드 비교이며 배합·함량·효능 동등성은 확인하지 않았습니다.")
    if not peers:
        st.info("수집한 시장 자료에서 성분·기능·제형이 겹치는 제품을 찾지 못했습니다. "
                "주요 성분과 제형을 입력했는지 확인해 주세요. (현재 시장 자료: 올리브영 랭킹 세럼·앰플, 공식몰 크림·토너·마스크 등)")
    else:
        bench = price_benchmark(peers)
        for row_start in range(0, len(peers), 3):
            cols = st.columns(3)
            for col, p in zip(cols, peers[row_start:row_start + 3]):
                with col, st.container(border=True):
                    st.caption(p["brand"] + (f" · {p['ranking_label']} {p['ranking']}위" if p.get("ranking") else ""))
                    st.markdown(f"**{short(p['name'])}**")
                    st.html("".join(chip(r, "#0f5c55", "#e3f2ef") for r in p["reasons"]))
                    stats = []
                    if p.get("price_krw"):
                        stats.append(f"{p['price_krw']:,}원" + (f" ({p['discount_pct']}% 할인 표시)" if p.get("discount_pct") else ""))
                    if p.get("review_count"):
                        stats.append(f"리뷰 {p['review_count']:,}개 · ★{p['rating']}")
                    st.write(" · ".join(stats) or "가격·리뷰 미수집")
                    for s in p["signals"][:2]:
                        st.caption(f"공개 판매 신호 · {s}")
        if bench:
            my_price = product.get("price_krw")
            diff = f" · 우리 제품 {my_price:,}원은 중간값보다 {abs(my_price - bench['median']) / bench['median'] * 100:.0f}% " \
                   f"{'높아요' if my_price > bench['median'] else '낮아요'}" if my_price else ""
            st.caption(f"비슷한 제품 가격 {bench['min']:,}원 ~ {bench['max']:,}원 · 중간값 {bench['median']:,}원{diff}")
        pts = [{"브랜드": p["brand"], "가격": p["price_krw"], "리뷰 수": p["review_count"], "순위": p.get("ranking")}
               for p in peers if p.get("price_krw") and p.get("review_count")]
        pts.sort(key=lambda d: d["가격"])
        for i, d in enumerate(pts):
            d["위"] = i % 2 == 0   # 가격이 비슷한 제품 이름이 겹치지 않게 위/아래로 번갈아 단다
        if len(pts) >= 2:
            with st.expander("가격과 인기 한눈에 보기 (리뷰 수 = 인기 신호, 매출 아님)", expanded=True):
                base = alt.Chart(alt.Data(values=pts))
                dots = base.mark_circle(size=220, color="#0f5c55", opacity=0.85).encode(
                    x=alt.X("가격:Q", title="판매가 (원)", scale=alt.Scale(zero=False), axis=alt.Axis(format=",.0f")),
                    y=alt.Y("리뷰 수:Q", title="리뷰 수", axis=alt.Axis(format=",.0f")),
                    tooltip=["브랜드:N", alt.Tooltip("가격:Q", format=",.0f"), alt.Tooltip("리뷰 수:Q", format=",.0f"), "순위:Q"])
                above = base.transform_filter("datum['위']").mark_text(dy=-17, fontSize=12, color="#182230").encode(
                    x="가격:Q", y="리뷰 수:Q", text="브랜드:N")
                below = base.transform_filter("!datum['위']").mark_text(dy=19, fontSize=12, color="#182230").encode(
                    x="가격:Q", y="리뷰 수:Q", text="브랜드:N")
                layers = [dots, above, below]
                if product.get("price_krw"):
                    mine = alt.Chart(alt.Data(values=[{"가격": product["price_krw"], "label": "우리 제품 가격"}]))
                    layers += [mine.mark_rule(color=UP, strokeDash=[6, 4], strokeWidth=2).encode(x="가격:Q"),
                               mine.mark_text(color=UP, y=12, dx=-6, align="right", fontWeight="bold").encode(x="가격:Q", text="label:N")]
                st.altair_chart(alt.layer(*layers).properties(height=260), width="stretch")
                st.caption("올리브영 상세페이지 표시가·누적 리뷰 수(수집일 2026-10-13). 경쟁 제품의 매출·판매량은 공개되지 않아 쓰지 않았어요.")

    # ------------------------------------------------------------------ ② 경쟁 제품 문구 분석
    summary = appeal_summary(peers) if peers else []
    step("2", "경쟁 제품은 이런 문구를 써요", "실제 상세페이지·상품명 문구를 유형별로 나누고, 같은 규칙으로 판정했어요.")
    if summary:
        used = [r for r in sorted(summary, key=lambda r: (-r["products"], -r["popular_products"])) if r["products"]]
        html_rows = []
        for r in used:
            total = max(r["safe"] + r["caution"] + r["risky"], 1)
            seg = "".join(
                f'<span title="{name} {n}건" style="display:inline-block;height:12px;width:{n / total * 100:.1f}%;background:{c}"></span>'
                for name, n, c in (("쓸 수 있음", r["safe"], SAFE), ("근거 필요", r["caution"], CAUTION), ("쓰면 안 됨", r["risky"], RISK)) if n)
            share = r["products"] / max(r["peers"], 1) * 100
            html_rows.append(
                f'<div style="display:grid;grid-template-columns:150px 1fr 250px;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid #ece9e2">'
                f'<div><div style="font-weight:700;color:#182230">{escape(r["type"])}</div>'
                f'<div style="font-size:12px;color:#667085">{escape(r["desc"].split("처럼")[0])}</div></div>'
                f'<div><div style="background:#ece9e2;border-radius:6px;height:10px;overflow:hidden">'
                f'<div style="width:{share:.0f}%;height:10px;background:#0f5c55"></div></div>'
                f'<div style="font-size:12px;color:#475467;margin-top:4px">{r["peers"]}개 중 <b>{r["products"]}개 제품</b>이 사용 · 인기 상위 {r["popular_products"]}개</div></div>'
                f'<div><div style="border-radius:6px;overflow:hidden;display:flex;height:12px">{seg}</div>'
                f'<div style="font-size:12px;color:#475467;margin-top:4px">문구 {total}건 · '
                + " · ".join(f'<span style="color:{c}">{name} {n}</span>' for name, n, c in
                             (("쓸 수 있음", r["safe"], SAFE), ("근거 필요", r["caution"], CAUTION), ("쓰면 안 됨", r["risky"], RISK)) if n)
                + '</div></div></div>')
        st.html('<div style="border:1px solid #dedbd4;border-radius:14px;padding:6px 18px;background:#fffdf8">'
                '<div style="display:grid;grid-template-columns:150px 1fr 250px;gap:14px;font-size:12px;color:#667085;padding:8px 0 2px">'
                '<span>문구 유형</span><span>얼마나 많은 제품이 쓰나</span><span>규칙 판정</span></div>'
                + "".join(html_rows) + '</div>')
        # 한 줄 정리: 경쟁 제품이 많이 쓰지만 근거가 필요한 유형 → 실증이 있으면 차별화 지점
        hard = [r for r in used if r["caution"] + r["risky"] > r["safe"]]
        mine = {j["type"]: j for j in judge_candidates(product, candidate_copies(product), peers)}
        for r in hard:
            ok = mine.get(r["type"], {}).get("level") == 0
            st.info(f"**{r['type']}** — 경쟁 제품 {r['products']}개가 쓰지만 수집한 문구 대부분이 ‘근거 필요’ 판정이에요. "
                    + ("우리 제품은 보유 실증으로 이 유형을 ‘쓸 수 있음’으로 쓸 수 있어 차별화 지점이 돼요."
                       if ok else "우리 제품도 이 유형을 쓰려면 관련 시험 자료가 필요해요."), icon=":material/lightbulb:")
        st.caption("실제 문구 예시는 아래에서 유형별로 펼쳐 볼 수 있어요.")
        for r in sorted(summary, key=lambda r: -r["products"]):
            if not r["products"]:
                continue
            with st.expander(f"{r['type']} — {r['products']}/{r['peers']}개 제품 사용 · 인기 상위 {r['popular_products']}개  ·  {r['desc']}"):
                for c in r["copies"]:
                    label, color = LEVEL_TEXT.get(c["level"], LEVEL_TEXT[None])
                    a, b = st.columns([5, 1.3], vertical_alignment="center")
                    a.write(f"**{c['brand']}** · “{c['copy_text'].strip()}”")
                    with b:
                        st.badge(label, color=color)
        st.caption("‘인기 상위’ = 올리브영 스킨케어 랭킹 10위 안. 판정은 공개 정보 기준 시스템 출력이며 브랜드의 위반을 확정하지 않아요. "
                   "경쟁 제품의 시험 수치는 우리 제품 근거로 옮기지 않고, 문구의 ‘유형’만 참고해요.")
    else:
        st.caption("비교할 시장 제품이 있어야 문구를 분석할 수 있어요.")

    # ------------------------------------------------------------------ ③ 생성 후보 비교 · 예상 매출
    step("3", "생성 후보 비교 · 예상 매출", "광고문 생성에서 받은 후보마다 한 달 매출이 얼마나 움직일 수 있는지 숫자로 비교하고 고르세요.")
    generation_results.bind_pending(registered_product)
    saved, stale = generation_results.record(registered_product)
    candidates = saved["response"].get("candidates", []) if saved and not stale else []
    if stale:
        st.warning("제품 정보 또는 선택한 실증 자료가 바뀌었습니다. 광고문 생성에서 다시 생성해 주세요.")
    elif not candidates:
        st.info("광고문 생성에서 후보를 만든 뒤, 후보 아래 ‘이 문구를 매출 시나리오에 사용’을 누르면 여기에 후보 3개가 나란히 나와요.")
        if st.button("광고문 생성으로 이동", key="fc_open_generation", type="primary"):
            st.switch_page(st.session_state["bw_pages"]["generate"])

    # 계산 기준: 숫자가 이 값에 따라 바뀌므로 접지 않고 보여준다
    bench = price_benchmark(peers) if peers else None
    default_price = product.get("price_krw") or (bench["median"] if bench else 27500)
    p1, p2, p3 = st.columns(3)
    price = p1.number_input("1개 판매가 (원)", min_value=0, value=default_price, step=500, key=f"fc_price_{pid}",
                            help="등록한 판매가 → 없으면 비슷한 제품 가격 중간값")
    units_mid = p2.number_input("월 계획 판매량 (개)", min_value=0, value=600, step=50, key=f"fc_um_{pid}",
                                help="실제 판매량이 아니라 계획 수량(가정)입니다")
    exposed = p3.slider("이 문구가 노출되는 경로의 매출 비중", 0, 100, 100, format="%d%%", key=f"fc_exposed_{pid}")
    if price <= 0 or units_mid <= 0:
        st.info("판매가와 월 계획 판매량을 0보다 크게 입력해 주세요.")
        st.stop()
    base = price * units_mid
    band = copy_change_band(Range3.of(base, "기준 매출"), exposed / 100)
    mode = st.segmented_control(
        "반응 폭 가정", options=["tier", "same"], default="tier", key=f"fc_mode_{pid}",
        format_func=lambda k: "표현 강도에 따라 다르게 (기본)" if k == "tier" else "모든 후보 같은 폭") or "tier"

    def outlook(candidate: dict) -> dict:
        level_key = TIER_EFFECT.get(candidate.get("tier") or "", "typical") if mode == "tier" else "typical"
        lv = EFFECT_LEVELS[level_key]
        pct_c, delta_c = band["change_magnitude_pct"][lv["q"]], band["change_magnitude_krw"][lv["q"]]
        return {"name": lv["name"], "hint": lv["hint"], "pct": pct_c, "delta": delta_c,
                "high": base + delta_c, "low": max(base - delta_c, 0),
                "units_high": units_mid + delta_c / price, "units_low": max(units_mid - delta_c / price, 0)}

    recommended, pct, delta = "", 0.0, 0.0
    if candidates:
        looks = [outlook(c) for c in candidates]
        top = max(lk["high"] for lk in looks) or 1
        cols = st.columns(len(candidates))
        for index, (col, candidate, lk) in enumerate(zip(cols, candidates, looks)):
            active = index == saved["selected"]
            usable = generation_results.usable(candidate)
            headline = candidate.get("headline") or candidate["text"].split(chr(10))[0]
            support = candidate.get("supporting_copy") or chr(10).join(candidate["text"].split(chr(10))[1:])
            # 기준 매출 대비 ▼ ~ ▲ 범위를 막대로 (막대 전체 = 후보 중 가장 큰 ▲)
            lo_pct, base_pct = lk["low"] / top * 100, base / top * 100
            border = "2px solid #0f5c55" if active else "1px solid #dedbd4"
            with col:
                st.html(
                    f'<div style="border:{border};border-radius:16px;padding:18px;background:#fffdf8;min-height:360px">'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#667085">'
                    f'<span>후보 {index + 1} · {escape(TIER_LABEL.get(candidate.get("tier"), "후보"))}</span>'
                    f'<span style="color:#0f5c55;font-weight:700">{"✓ 선택됨" if active else ""}</span></div>'
                    f'<div style="font-size:18px;font-weight:750;color:#182230;margin:8px 0 4px;min-height:48px">{escape(headline)}</div>'
                    f'<div style="font-size:13px;color:#475467;min-height:54px">{escape(support)}</div>'
                    f'<div style="border-top:1px dashed #dedbd4;margin:12px 0 10px"></div>'
                    f'<div style="font-size:12px;color:#667085">예상 한 달 매출 · {escape(lk["name"])}</div>'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px">'
                    f'<span style="font-size:22px;font-weight:800;color:{UP}">▲ {won(lk["high"])}</span>'
                    f'<span style="font-size:13px;font-weight:700;color:{UP}">+{lk["pct"]}%</span></div>'
                    f'<div style="font-size:12px;color:{UP}">약 {units(lk["units_high"])} 판매</div>'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px">'
                    f'<span style="font-size:22px;font-weight:800;color:{DOWN}">▼ {won(lk["low"])}</span>'
                    f'<span style="font-size:13px;font-weight:700;color:{DOWN}">−{lk["pct"]}%</span></div>'
                    f'<div style="font-size:12px;color:{DOWN}">약 {units(lk["units_low"])} 판매</div>'
                    f'<div style="position:relative;height:12px;background:#ece9e2;border-radius:6px;margin:12px 0 4px">'
                    f'<div style="position:absolute;left:{lo_pct:.1f}%;width:{100 - lo_pct:.1f}%;height:12px;border-radius:6px;'
                    f'background:linear-gradient(90deg,{DOWN},#cfd4dc {max(base_pct - lo_pct, 1) / (100 - lo_pct) * 100:.0f}%,{UP})"></div>'
                    f'<div style="position:absolute;left:{base_pct:.1f}%;top:-3px;width:2px;height:18px;background:#182230"></div></div>'
                    f'<div style="font-size:11px;color:#667085">검은 선 = 지금 기준 {won(base)} · {units(units_mid)}</div></div>'
                )
                if st.button("✓ 선택한 문구" if active else f"후보 {index + 1} 선택", key=f"fc_select_{pid}_{index}",
                             type="primary" if active else "secondary", disabled=not usable, width="stretch"):
                    generation_results.choose(registered_product, index)
                    st.rerun()

        chosen = generation_results.selected(registered_product)
        if chosen:
            lk = looks[saved["selected"]]
            recommended, pct, delta = chosen["text"], lk["pct"], lk["delta"]
            st.markdown(f"##### 선택한 문구 · 후보 {saved['selected'] + 1}")
            st.code(recommended, language=None)
            if chosen.get("evidence_note"):
                st.caption("함께 표기할 시험 정보: " + chosen["evidence_note"])
            a1, a2, a3 = st.columns(3)
            with a1:
                arrow_card("반응이 좋을 때", won(lk["high"]), 1, f"+{pct}% · {won(delta, signed=True)}",
                           f"약 {units(lk['units_high'])} · 기준보다 {units(lk['units_high'] - units_mid, signed=True)}")
            with a2:
                arrow_card("지금 기준", won(base), 0, f"{price:,}원 × {units_mid:,}개", "판매가 × 월 계획 판매량")
            with a3:
                arrow_card("반응이 나쁠 때", won(lk["low"]), -1, f"−{pct}% · {won(-delta, signed=True)}",
                           f"약 {units(lk['units_low'])} · 기준보다 {units(lk['units_low'] - units_mid, signed=True)}")
            st.caption(f"‘{lk['name']}’ = {lk['hint']} (공개 A/B 실험 148건 기준)")
        else:
            st.info("검토를 통과한 후보를 선택해 주세요.")
        st.caption("반응 폭 가정: 강한 표현은 ‘많이’, 균형은 ‘보통’, 가장 안전은 ‘조금’ 움직인다고 봐요(오를 때도 내릴 때도). "
                   "변화 폭은 미국 뉴스 제목 A/B 실험에서 빌려온 값이라 화장품 매출 예측이나 상승 보장이 아니에요. "
                   "어느 후보가 실제로 더 팔리는지는 A/B 테스트로 확인해야 해요.")

    # ------------------------------------------------------------------ 참고
    with st.expander("계산 근거 · 출처 보기"):
        st.markdown(f"**계산식** · 기준 매출 = {price:,}원 × {units_mid:,}개 = {won(base)} · "
                    f"변화 폭 = 기준 매출 × 노출 비중 {exposed}% × 반응 폭(%)")
        st.markdown("""| 자료 | 쓰이는 곳 | 주의할 점 |
|---|---|---|
| 비슷한 제품의 공개 성분·문구·가격·순위 | ① 시장 비교, ② 문구 유형 | 순위·리뷰는 매출이 아님 |
| 우리 제품 정보·시험 자료·규정 | 광고문 생성·검토 | 다른 제품의 실증을 대신 쓰지 않음 |
| 뉴스 제목 A/B 실험 148건 | ③ 반응 폭 가정 | 화장품 매출 효과가 아님 |
| 판매가·월 계획 판매량 | ③ 기준 매출 | 계획 수량을 쓴 가정 |""")
        render_public_experiments()
    with st.expander("실제 성과 비교 · 문구 A/B 데이터가 있을 때"):
        st.caption("문구별 노출·클릭·주문·순매출이 생기면 입력해 비교하세요. 위 시나리오에는 자동 반영되지 않습니다.")
        render_performance(pid)
