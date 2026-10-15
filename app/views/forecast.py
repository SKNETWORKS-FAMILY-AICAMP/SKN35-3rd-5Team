"""
[app/views/forecast.py]
예상 매출 시나리오 — 새로 등록한 우리 제품을 비슷한 시장 제품과 비교해, 최적 문구와 예상 매출을 본다.

흐름
  ① 비슷한 시장 제품 찾기   app/services/peer_market.py  (성분·기능성·제형으로 매칭, 가격·랭킹·리뷰·공개 판매 신호)
  ② 경쟁 제품의 문구 분석   문구 유형별 사용 현황 + 규칙 판정
  매출: 생성 후보 선택과 공통 가정에 따른 매출 변화 폭
  ⑤ 참고 자료               공개 A/B 실험 · 성과 입력 비교 (이전 「시장 근거 · 문구 비교」 화면, 참조용)

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
from app.components.market_reference import (
    render_public_experiments,
    render_reference_guide,
)
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

    # 광고문 생성의 후보 선택과 변화 폭만 표시한다. 검토 결과를 반복하지 않는다.
    step("매출", "문구를 바꾸면 움직이는 매출 폭", "생성한 후보를 선택하고 같은 계산 기준에서 변화 폭을 살펴보세요.")
    saved, stale = generation_results.record(registered_product)
    candidates = saved["response"].get("candidates", []) if saved and not stale else []
    recommended = ""
    if stale:
        st.warning("제품 정보 또는 선택한 실증 자료가 바뀌었습니다. 광고문 생성에서 다시 생성해 주세요.")
    elif not candidates:
        st.info("광고문 생성에서 후보를 만든 뒤 ‘이 문구를 매출 시나리오에 사용’을 눌러 주세요.")
    if st.button("광고문 생성으로 이동", key="fc_open_generation"):
        st.switch_page(st.session_state["bw_pages"]["generate"])

    bench = price_benchmark(peers) if peers else None
    default_price = product.get("price_krw") or (bench["median"] if bench else 27500)
    with st.expander("계산 기준 설정 · 판매가와 계획 수량", expanded=False):
        p1, p2 = st.columns(2)
        price = p1.number_input("1개 판매가 (원)", min_value=0, value=default_price, step=500, key=f"fc_price_{pid}")
        units_mid = p2.number_input("월 계획 판매량 (개)", min_value=0, value=600, step=50, key=f"fc_um_{pid}")
        exposed = st.slider("문구 노출 경로의 매출 비중", 0, 100, 100, format="%d%%", key=f"fc_exposed_{pid}")
        st.caption("등록 판매가가 없으면 유사 제품 가격 중간값, 없으면 예시 27,500원을 사용합니다. 계획 수량 기본값 600개는 실제 판매량이 아닙니다.")
    if price <= 0 or units_mid <= 0:
        st.info("계산 기준 설정에서 판매가와 월 계획 판매량을 0보다 크게 입력해 주세요.")
        st.stop()
    base = price * units_mid
    st.caption(f"계산 기준: {price:,}원 × 월 계획 {units_mid:,}개 = {won(base)} · 문구 노출 경로 {exposed}%")
    choice = st.segmented_control("변화 폭 가정", options=list(EFFECT_LEVELS), default="typical",
                                  format_func=lambda k: EFFECT_LEVELS[k]["name"], key=f"fc_effect_{pid}") or "typical"
    band = copy_change_band(Range3.of(base, "기준 매출"), exposed / 100)
    sel = EFFECT_LEVELS[choice]
    pct = band["change_magnitude_pct"][sel["q"]]
    delta = band["change_magnitude_krw"][sel["q"]]
    st.caption("문구별 효과는 아직 측정하지 않았으므로 모든 후보에 같은 변화 폭 가정을 적용합니다. 후보 선택은 실제 A/B 테스트 대상을 고르는 용도입니다.")

    if candidates:
        for row_start in range(0, len(candidates), 3):
            cols = st.columns(min(3, len(candidates) - row_start))
            for index, col in zip(range(row_start, min(row_start + 3, len(candidates))), cols):
                candidate = candidates[index]
                active = index == saved["selected"]
                usable = generation_results.usable(candidate)
                with col, st.container(border=True):
                    st.caption(f"후보 {index + 1}" + (" · 선택 중" if active else ""))
                    st.markdown(f"**{candidate.get('headline') or candidate['text'].split(chr(10))[0]}**")
                    if candidate.get("supporting_copy"):
                        st.write(candidate["supporting_copy"])
                    st.markdown(f":red[▲ {won(base + delta)}] / :blue[▼ {won(max(base - delta, 0))}]")
                    st.caption(f"공통 가정 ±{pct}% · 문구 노출 경로에 적용")
                    if st.button("선택한 문구" if active else f"후보 {index + 1} 선택", key=f"fc_select_{pid}_{index}",
                                 type="primary" if active else "secondary", disabled=not usable):
                        generation_results.choose(registered_product, index)
                        st.rerun()
        chosen = generation_results.selected(registered_product)
        if chosen:
            recommended = chosen["text"]
            st.markdown(f"##### 선택한 문구 · 후보 {saved['selected'] + 1}")
            st.code(recommended, language=None)
            a1, a2 = st.columns(2)
            with a1:
                arrow_card("반응이 좋을 때 · 가정", won(base + delta), 1,
                           f"+{pct}% · {won(delta, signed=True)}", f"기준 {won(base)} 대비 · 약 {units(units_mid + delta / price)}")
            with a2:
                arrow_card("반응이 나쁠 때 · 가정", won(max(base - delta, 0)), -1,
                           f"−{pct}% · {won(-delta, signed=True)}", f"기준 {won(base)} 대비 · 약 {units(max(units_mid - delta / price, 0))}")
        else:
            st.info("검토를 통과한 후보를 선택해 주세요.")
    st.caption("변화 폭은 미국 뉴스 제목 A/B 실험 148쌍에서 관찰된 클릭률 차이를 참고한 가정입니다. 구매전환율·객단가를 고정한 시나리오이며 화장품 매출 예측이나 상승 보장이 아닙니다.")

    # ------------------------------------------------------------------ ⑤ 참고 자료
    step("참고", "자료와 계산, 한눈에 이해하기", "시장 문구는 표현 참고에, 공개 실험은 변화 폭 가정에 사용합니다.")
    t1, t2, t3 = st.tabs(["쉬운 설명 · 현재 계산 예시", "실제 성과 비교", "출처 · 자세한 자료"])
    with t1:
        render_reference_guide(
            product_name=product["name"], base_revenue=base,
            exposed_share=exposed / 100, change_pct=pct,
            change_amount=delta, peer_count=len(peers),
            market_example=next((
                {"brand": p["brand"], "name": p["name"], "copy": c["copy_text"]}
                for pref in ("성분 소구형", "효능 서술형", "효능 수치형", None)
                for p in peers for c in p.get("copies", [])
                if pref is None or pref in (c.get("types") or [])
            ), None),
            own_copy=recommended,
        )
    with t2:
        st.info("문구별 실측 자료가 있을 때 사용하는 비교 도구입니다. 아직 자료가 없다면 입력하지 않아도 됩니다. 위 매출 시나리오에는 자동 반영되지 않습니다.")
        with st.expander("문구 A/B 데이터 입력하기"):
            render_performance(pid)
    with t3:
        st.markdown("#### 사용한 자료와 역할")
        st.markdown("""| 자료 | 화면에서 쓰이는 곳 | 해석할 때 주의할 점 |
|---|---|---|
| 유사 제품의 공개 성분·문구·가격·순위 | 시장 비교와 표현 유형 참고 | 순위·리뷰는 매출이 아님 |
| 우리 제품 정보·시험 자료와 규정 | 문구 후보 생성과 규칙 검토 | 다른 제품의 실증을 대신 쓰지 않음 |
| 뉴스 제목 A/B 실험 148건 | 매출 변화 폭에 넣은 가정의 참고값 | 화장품 매출 효과가 아님 |
| 판매가·월 판매량 입력값 | 기준 월 매출 계산 | 계획 수량을 사용한 가정 |""")
        render_public_experiments()
        with st.expander("현재 계산 가정 · 연결 파일 확인"):
            st.markdown("**계산에 사용한 가정**")
            st.write(f"판매가 {price:,}원 · 월 계획 {units_mid:,}개 · 문구 노출 경로 {exposed}%")
            st.write("구매전환율·객단가 고정. 후보별 효과·적발 확률은 추정하지 않습니다.")
            st.code("\n".join([
                "data/top_product_copies/wrinkle_serum_sample/products.csv",
                "data/market_reference/",
                "data/sales_forecast_reference/copy_comparison/market_copy_judgements.jsonl",
                "data/sales_forecast_reference/copy_effect_size_distribution.json",
            ]), language=None)
