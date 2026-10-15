"""
[app/components/context.py]
검토 기준 = "내 제품": 어떤 제품을, 어떤 실증 자료를 가진 상태로 검토하는지 정한다.
왼쪽 사이드바의 「내 제품」 영역이 그린다(render_project). 화면들은 current() 로 읽기만 한다.
선택은 화면을 옮겨도 유지된다. 처음에는 제품 정보 없이 '일반 화장품 · 실증 없음' 기준으로 검토하고,
우리 제품을 등록하거나 「예시 제품 불러오기」에서 시연용 제품을 고를 수 있다.

실증 자료를 해제하면 그 자료 없이 쓸 수 있는 단계까지만 제안이 내려간다(데모 핵심 장면).
「제품 직접 등록」으로 우리 제품(이름 · 구분 · 기능성 · 주요 성분 · 실증 자료 여러 개)을 추가할 수 있다.
등록한 제품은 이 브라우저 세션에만 저장된다 (서버·저장소에 남지 않음).
"""
from __future__ import annotations

import streamlit as st

from app.components.layout import esc, html
from app.services import backend
from app.services.peer_market import FORMS, form_of
from cosmetic_agent.domain.copy_knowledge import ingredient_names

_PID = "bw_pid"          # 선택한 제품 id (화면을 옮겨도 유지)
_EV = "bw_ev_state"      # {product_id: [체크 여부, ...]}
_CUSTOM = "bw_custom_products"  # 직접 등록한 제품 목록 (세션에만 저장)

# 실증규정 · 관리지침에서 쓰는 자료 종류. '자사 설문'은 광고 근거로 인정되지 않는다(실증규정 제5조).
TEST_TYPES = ["인체적용시험", "인체외시험", "피부자극 시험", "비교 시험", "소비자 조사(외부 기관)", "자사 설문"]
# 화장품법 시행규칙 제2조 제1~11호의 기능성화장품 범위 (10종). 2중·3중 기능성은 여러 개 고른다.
FUNCTIONAL_TYPES = ["피부 미백", "주름 개선", "자외선 차단", "피부를 곱게 태워줌", "모발의 색상 변화(염모)",
                    "체모 제거(제모)", "탈모 증상 완화", "여드름성 피부 완화", "피부장벽 기능 회복(가려움 개선)",
                    "튼살 붉은 선 완화"]


GENERAL_ID = "GENERAL_DEFAULT"
# 아무 제품도 고르지 않았을 때의 검토 기준: 일반 화장품 · 보유 실증 없음 (가장 보수적인 기준)
GENERAL = {"product_id": GENERAL_ID, "name": "일반 화장품 (제품 정보 없음)", "category": "일반",
           "functional_type": None, "key_ingredients": [], "owned_evidence": []}


def all_products() -> list[dict]:
    """기본 기준(제품 정보 없음) + 예시 제품(data/assets) + 직접 등록한 제품."""
    return [GENERAL] + backend.list_products() + list(st.session_state.get(_CUSTOM, []))


def _evidence_state(product: dict) -> list[bool]:
    states = st.session_state.setdefault(_EV, {})
    n = len(product.get("owned_evidence", []))
    cur = states.get(product["product_id"])
    if cur is None or len(cur) != n:
        cur = [True] * n
        states[product["product_id"]] = cur
    return cur


def _on_product_change(key: str) -> None:
    st.session_state[_PID] = st.session_state[key]
    st.session_state["bw_pid_by_select"] = True


def _on_evidence_change(pid: str, i: int, key: str) -> None:
    st.session_state[_EV][pid][i] = st.session_state[key]


def category_label(product: dict) -> str:
    if product.get("category") == "기능성":
        return f"기능성 · {product.get('functional_type') or ''}".strip(" ·")
    return "일반 화장품"


def current() -> tuple[dict, dict]:
    """위젯을 그리지 않고 현재 기준만 돌려준다. (요청용 제품, 기준 요약)"""
    products = all_products()
    by_id = {p["product_id"]: p for p in products}
    pid = st.session_state.get(_PID)
    if pid not in by_id:
        pid = products[0]["product_id"]
        st.session_state[_PID] = pid
    product = by_id[pid]
    states = _evidence_state(product)
    evs = product.get("owned_evidence", [])
    chosen = [ev for ev, on in zip(evs, states) if on]
    request_product = dict(product, owned_evidence=chosen)
    ctx = {
        "product_id": pid,
        "product_name": product["name"],
        "category_label": category_label(product),
        "evidence_total": len(evs),
        "evidence_on": len(chosen),
        "evidence_names": [f'{ev["test_type"]} · {ev["item"]}' for ev in chosen],
        "signature": f'{pid}:{"".join("1" if s else "0" for s in states)}',
    }
    return request_product, ctx


def render_project(key: str = "proj") -> None:
    """사이드바 「내 제품」: 지금 검토 기준(제품 카드 + 실증 체크) → 예시 제품 불러오기."""
    products = all_products()
    ids = [p["product_id"] for p in products]
    by_id = {p["product_id"]: p for p in products}
    current()  # 기본값 보정
    pid = st.session_state[_PID]

    with st.container(key=key, gap="small"):
        if pid == GENERAL_ID:
            html('<div class="bw-proj-empty bw-proj-invite"><b>검토할 제품을 등록하세요</b><br>'
                 '일반/기능성 구분·성분·시험 자료에 따라 판정과 제안이 달라집니다.</div>')
            if st.button("내 제품 등록", key=f"{key}_register_open", icon=":material/add:",
                         type="primary", width="stretch"):
                _register_dialog(key)
            st.caption("지금은 일반 화장품 · 실증 없음 기준으로 검토합니다.")
        else:
            _render_product_card(key, by_id[pid])
            if st.button("다른 제품 등록", key=f"{key}_register_open", icon=":material/add:",
                         type="tertiary", width="stretch"):
                _register_dialog(key)

        examples = [i for i in ids if i != GENERAL_ID]
        with st.expander(f"예시 제품 불러오기 · {len(examples)}개", icon=":material/menu_book:"):
            # 다른 화면(제품 등록·광고문 생성 → 예상 매출)이 제품을 바꾸면 선택 상자가 옛 제품을 보여 주지 않도록
            # 위젯을 새 키로 다시 만든다. (세션 값으로 덮어쓰면 옵션이 바뀐 직후 옛 값이 남는 경우가 있었다) — 준호
            nonce = st.session_state.get(f"{key}_product_nonce", 0)
            shown = st.session_state.get(f"{key}_product_shown")
            by_user = st.session_state.pop("bw_pid_by_select", False)
            if shown is not None and shown != pid and not by_user:
                nonce += 1
                st.session_state[f"{key}_product_nonce"] = nonce
            st.session_state[f"{key}_product_shown"] = pid
            sel_key = f"{key}_product" if nonce == 0 else f"{key}_product_{nonce}"
            st.selectbox(
                "검토할 제품", ids, index=ids.index(pid),
                format_func=lambda i: "선택 안 함 · 일반 화장품 기준" if i == GENERAL_ID
                else ("✎ " if i.startswith("CUSTOM_") else "") + by_id[i]["name"],
                key=sel_key, label_visibility="collapsed",
                on_change=_on_product_change, args=(sel_key,),
            )
            st.caption("시연용 예시입니다. 실제 검토는 「내 제품 등록」으로 우리 제품과 시험 자료를 넣어 주세요.")


def _render_product_card(key: str, product: dict) -> None:
    """선택한 제품: 이름·구분·성분과 사용할 실증 자료 체크 (해제하면 그 자료가 필요한 표현은 제안하지 않는다)."""
    states = _evidence_state(product)
    evs = product.get("owned_evidence", [])
    html(f'<div class="bw-proj-meta"><b>{esc(product["name"])}</b><br>'
         f'{esc(category_label(product))} · 보유 실증 {sum(states)}/{len(evs)}</div>')
    if any(ev.get("source_kind") == "public_brand_summary" for ev in evs):
        st.caption("공식몰 공개 시험 요약 · 원보고서 미확보 · 시연용 등록 근거")
    if not evs:
        html('<div class="bw-proj-empty">등록된 실증 자료가 없습니다. 근거가 필요 없는 낮은 단계 표현까지만 제안합니다.</div>')
    for i, ev in enumerate(evs):
        ck = f'{key}_ev_{product["product_id"]}_{i}'
        st.checkbox(f'{ev["test_type"]} · {ev["item"]}', value=states[i], key=ck,
                    on_change=_on_evidence_change, args=(product["product_id"], i, ck))
        detail = " · ".join(x for x in (ev.get("value"), ev.get("institute")) if x)
        if states[i]:
            hint = backend.unlock_hint(product, ev)
            note = f'<em>{esc(hint)}</em>' if hint else ""
        else:
            note = '<em class="is-off">해제됨 — 이 자료가 필요한 표현은 제안하지 않습니다</em>'
        html(f'<div class="bw-ev"><span>{esc(detail)}</span>{note}</div>')
        if ev.get("source_kind") == "public_brand_summary":
            with st.expander("공개 요약 출처·시험 조건"):
                st.caption(ev.get("conditions") or "조건 미공개")
                if ev.get("source_url"):
                    st.link_button("공식 시험 요약 출처", ev["source_url"], key=f"{key}_ev_source_{product['product_id']}_{i}")
    if product.get("key_ingredients"):
        html(f'<div class="bw-proj-meta">주요 성분 · {esc(", ".join(product["key_ingredients"]))}</div>')
    facts = [product.get(k) for k in ("texture", "scent", "package", "usage_step") if product.get(k)]
    if facts:
        html(f'<div class="bw-proj-meta">제품 사실 · {esc(" · ".join(facts))}</div>')
    c1, c2 = st.columns(2)
    if c1.button("기준 해제", key=f"{key}_clear_{product['product_id']}", type="tertiary",
                 icon=":material/close:", help="제품 정보 없이 일반 화장품 기준으로 검토"):
        st.session_state[_PID] = GENERAL_ID
        st.session_state.pop(f"{key}_product", None)
        st.rerun()
    if product["product_id"].startswith("CUSTOM_"):
        c2.button("이 제품 삭제", key=f"{key}_del_{product['product_id']}", type="tertiary",
                  icon=":material/delete:", on_click=_delete_custom, args=(product["product_id"],))


def _delete_custom(pid: str) -> None:
    st.session_state[_CUSTOM] = [p for p in st.session_state.get(_CUSTOM, []) if p["product_id"] != pid]
    st.session_state.pop(_PID, None)


def open_register(key: str = "proj") -> None:
    """다른 화면(예상 매출 시나리오)에서 등록 팝업을 연다."""
    _register_dialog(key)


def _render_register(key: str) -> None:
    """(호환용) 넓은 팝업에서 우리 제품과 보유 실증 자료를 입력하는 버튼."""
    if st.button("내 제품 등록", key=f"{key}_register_open2", icon=":material/add:", width="stretch"):
        _register_dialog(key)


@st.dialog("내 제품 등록", width="large")
def _register_dialog(key: str) -> None:
    st.caption("우리 제품과 보유한 실증 자료를 입력하면, 그 근거가 허용하는 범위 안에서 검토·제안합니다. "
               "등록한 제품은 이 브라우저 세션에만 저장됩니다.")
    # 폼(st.form)을 쓰지 않는다: 입력칸에서 Enter 를 누르면 실증 자료를 다 넣기 전에 제출되기 때문
    c1, c2 = st.columns([3, 2])
    name = c1.text_input("제품명", placeholder="예: 비타 브라이트닝 앰플")
    category = c2.radio("구분", ["일반", "기능성"], horizontal=True)
    functional_types = st.multiselect(
        "기능성 종류 (기능성일 때, 2중·3중 기능성은 여러 개)", FUNCTIONAL_TYPES,
        disabled=category != "기능성", placeholder="심사·보고받은 기능성을 고르세요",
        help="화장품법 시행규칙 제2조의 기능성화장품 10종")
    functional_type = ", ".join(functional_types)
    ingredient_list = st.multiselect(
        "주요 성분", ingredient_names(), accept_new_options=True, max_selections=15,
        placeholder="한두 글자를 입력하면 식약처 원료사전 21,945개에서 찾아줍니다",
        help="목록에 없는 이름은 입력 후 Enter 로 추가할 수 있습니다")
    # 예상 매출 시나리오에서 비슷한 시장 제품을 찾고 가격을 비교하는 데 쓴다
    c5, c6 = st.columns([2, 3])
    form_choice = c5.selectbox("제형", ["제품명에서 자동 확인", *FORMS], help="제품명에 토너·크림 등이 있으면 자동으로 확인합니다. 모호한 제품은 직접 선택하세요.")
    form = form_of(name) if form_choice == "제품명에서 자동 확인" else form_choice
    c5.caption(f"비교 제형: {form or '제품명으로 확인할 수 없어 직접 선택이 필요합니다.'}")
    price = c6.number_input("판매가 (원, 선택)", min_value=0, value=None, step=1000, placeholder="예: 32000")
    with st.expander("제품 사실 (선택) · 채울수록 광고문이 구체적이 됩니다"):
        st.caption("질감·향·용기처럼 확인된 사실만 적어 주세요. 광고문 생성에 그대로 쓰이며, 효능 근거로는 쓰지 않습니다.")
        f1, f2 = st.columns(2)
        texture = f1.text_input("제형·질감", placeholder="예: 물처럼 가볍게 펴지는 젤 크림", max_chars=200)
        scent = f2.text_input("향", placeholder="예: 은은한 풀잎 향 / 무향", max_chars=100)
        package = f1.text_input("용량·용기", placeholder="예: 50ml 튜브", max_chars=100)
        usage_step = f2.text_input("사용 순서", placeholder="예: 세안 후 토너 다음, 마지막 단계", max_chars=200)
        skin_type = f1.text_input("추천 피부 타입", placeholder="예: 건성·복합성", max_chars=100)
        highlight = f2.text_input("한 줄 특징", placeholder="예: 펌프형이라 한 손으로 덜어 쓰기 편함", max_chars=200)
    st.markdown("**보유 실증 자료** · 표 아래 ＋ 로 행을 추가해 여러 개 입력 (항목이 빈 행은 무시)")
    rows = st.data_editor(
        [{"시험 종류": "인체적용시험", "항목": "", "결과": "", "기관": ""}],
        num_rows="dynamic", hide_index=True, width="stretch", key=f"{key}_register_rows",
        column_config={
            "시험 종류": st.column_config.SelectboxColumn(options=TEST_TYPES, required=True, width="medium"),
            "항목": st.column_config.TextColumn(help="예: 피부톤 개선, 보습 지속", width="medium"),
            "결과": st.column_config.TextColumn(help="예: 8주 사용 후 피부톤 12% 개선", width="large"),
            "기관": st.column_config.TextColumn(help="예: OO피부임상연구소", width="medium"),
        },
    )
    st.caption("자사 설문은 광고 근거로 인정되지 않습니다 (실증규정 제5조) — 입력해도 수치 표현에는 쓰지 않습니다.")
    submitted = st.button("등록하고 이 제품으로 검토", type="primary", width="stretch", key=f"{key}_register_submit")
    if not submitted:
        return
    if not name.strip():
        st.error("제품명을 입력해 주세요")
        return
    if not form:
        st.error("제품명으로 제형을 확인할 수 없습니다. 제형을 직접 선택해 주세요.")
        return
    if category == "기능성" and not functional_types:
        st.error("기능성 제품은 심사·보고받은 기능성 종류를 하나 이상 골라 주세요")
        return
    evidence = [
        {"test_type": r["시험 종류"], "item": (r.get("항목") or "").strip(),
         "value": (r.get("결과") or "").strip() or None, "institute": (r.get("기관") or "").strip() or None}
        for r in rows if r.get("시험 종류") and (r.get("항목") or "").strip()
    ]
    seq = st.session_state.get("bw_custom_seq", 0) + 1  # 삭제 후에도 번호가 겹치지 않게
    st.session_state["bw_custom_seq"] = seq
    product = {
        "product_id": f"CUSTOM_{seq:03d}",
        "name": name.strip(),
        "category": category,
        "functional_type": functional_type if category == "기능성" else None,
        "key_ingredients": list(dict.fromkeys(i.strip() for i in ingredient_list if i.strip())),
        "form": form,
        "price_krw": int(price) if price else None,
        **{k: v.strip() for k, v in {"texture": texture, "scent": scent, "package": package, "usage_step": usage_step,
                                     "skin_type": skin_type, "highlight": highlight}.items() if v and v.strip()},
        "owned_evidence": evidence,
    }
    register_product(product)
    st.toast(f"‘{product['name']}’ 등록 · 실증 자료 {len(evidence)}개", icon=":material/check:")
    st.rerun()


def register_product(product: dict) -> dict:
    """직접 등록 제품을 세션에 추가하고 선택한다. product_id 가 없으면 CUSTOM_### 을 붙인다."""
    custom = st.session_state.setdefault(_CUSTOM, [])
    if not str(product.get("product_id", "")).startswith("CUSTOM_"):
        seq = st.session_state.get("bw_custom_seq", 0) + 1
        st.session_state["bw_custom_seq"] = seq
        product = dict(product, product_id=f"CUSTOM_{seq:03d}")
    custom.append(product)
    st.session_state[_PID] = product["product_id"]
    return product
