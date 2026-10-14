"""
[app/components/context.py]
검토 기준 = "프로젝트": 어떤 제품을, 어떤 실증 자료를 가진 상태로 검토하는지 정한다.
왼쪽 사이드바의 「프로젝트」 영역이 그린다(render_project). 화면들은 current() 로 읽기만 한다.
선택은 화면을 옮겨도 유지된다.

실증 자료를 해제하면 그 자료 없이 쓸 수 있는 단계까지만 제안이 내려간다(데모 핵심 장면).
「제품 직접 등록」으로 우리 제품(이름 · 구분 · 기능성 · 주요 성분 · 실증 자료 여러 개)을 추가할 수 있다.
등록한 제품은 이 브라우저 세션에만 저장된다 (서버·저장소에 남지 않음).
"""
from __future__ import annotations

import streamlit as st

from app.components.layout import esc, html
from app.services import backend

_PID = "bw_pid"          # 선택한 제품 id (화면을 옮겨도 유지)
_EV = "bw_ev_state"      # {product_id: [체크 여부, ...]}
_CUSTOM = "bw_custom_products"  # 직접 등록한 제품 목록 (세션에만 저장)

# 실증규정 · 관리지침에서 쓰는 자료 종류. '자사 설문'은 광고 근거로 인정되지 않는다(실증규정 제5조).
TEST_TYPES = ["인체적용시험", "인체외시험", "피부자극 시험", "비교 시험", "소비자 조사(외부 기관)", "자사 설문"]
# 시행규칙 제2조의 기능성화장품 범위
FUNCTIONAL_TYPES = ["피부 미백", "주름 개선", "자외선 차단", "탈모 증상 완화", "여드름성 피부 완화",
                    "피부장벽 기능 회복(가려움 개선)", "튼살 붉은 선 완화", "피부 미백, 주름 개선"]


def all_products() -> list[dict]:
    """기본 제품(data/assets/mock_products.json) + 직접 등록한 제품."""
    return backend.list_products() + list(st.session_state.get(_CUSTOM, []))


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
    """사이드바 「프로젝트」: 제품 선택 + 보유 실증 자료 체크."""
    products = all_products()
    ids = [p["product_id"] for p in products]
    by_id = {p["product_id"]: p for p in products}
    current()  # 기본값 보정
    pid = st.session_state[_PID]

    with st.container(key=key, gap="small"):
        sel_key = f"{key}_product"
        if st.session_state.get(sel_key) not in (None, pid):  # 새로 등록한 제품으로 바로 전환
            st.session_state[sel_key] = pid
        st.selectbox(
            "검토할 제품", ids, index=ids.index(pid),
            format_func=lambda i: ("✎ " if i.startswith("CUSTOM_") else "") + by_id[i]["name"],
            key=sel_key, label_visibility="collapsed",
            on_change=_on_product_change, args=(sel_key,),
        )
        product = by_id[st.session_state[_PID]]
        states = _evidence_state(product)
        evs = product.get("owned_evidence", [])
        html(f'<div class="bw-proj-meta">{esc(category_label(product))} · 보유 실증 {sum(states)}/{len(evs)}</div>')
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
        if product.get("key_ingredients"):
            html(f'<div class="bw-proj-meta">주요 성분 · {esc(", ".join(product["key_ingredients"]))}</div>')
        if product["product_id"].startswith("CUSTOM_"):
            st.button("이 제품 삭제", key=f"{key}_del_{product['product_id']}", type="tertiary",
                      icon=":material/delete:", on_click=_delete_custom, args=(product["product_id"],))
    _render_register(key)


def _delete_custom(pid: str) -> None:
    st.session_state[_CUSTOM] = [p for p in st.session_state.get(_CUSTOM, []) if p["product_id"] != pid]
    st.session_state.pop(_PID, None)


def _render_register(key: str) -> None:
    """사이드바 버튼 → 넓은 팝업에서 우리 제품과 보유 실증 자료를 입력한다."""
    if st.button("제품 직접 등록", key=f"{key}_register_open", icon=":material/add:", width="stretch"):
        _register_dialog(key)


@st.dialog("제품 직접 등록", width="large")
def _register_dialog(key: str) -> None:
    st.caption("우리 제품과 보유한 실증 자료를 입력하면, 그 근거가 허용하는 범위 안에서 검토·제안합니다. "
               "등록한 제품은 이 브라우저 세션에만 저장됩니다.")
    # 폼(st.form)을 쓰지 않는다: 입력칸에서 Enter 를 누르면 실증 자료를 다 넣기 전에 제출되기 때문
    c1, c2 = st.columns([3, 2])
    name = c1.text_input("제품명", placeholder="예: 비타 브라이트닝 앰플")
    category = c2.radio("구분", ["일반", "기능성"], horizontal=True)
    c3, c4 = st.columns([2, 3])
    functional_type = c3.selectbox("기능성 종류 (기능성일 때만)", FUNCTIONAL_TYPES)
    ingredients = c4.text_input("주요 성분 (쉼표로 구분)", placeholder="예: 나이아신아마이드, 판테놀")
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
    evidence = [
        {"test_type": r["시험 종류"], "item": (r.get("항목") or "").strip(),
         "value": (r.get("결과") or "").strip() or None, "institute": (r.get("기관") or "").strip() or None}
        for r in rows if r.get("시험 종류") and (r.get("항목") or "").strip()
    ]
    custom = st.session_state.setdefault(_CUSTOM, [])
    seq = st.session_state.get("bw_custom_seq", 0) + 1  # 삭제 후에도 번호가 겹치지 않게
    st.session_state["bw_custom_seq"] = seq
    product = {
        "product_id": f"CUSTOM_{seq:03d}",
        "name": name.strip(),
        "category": category,
        "functional_type": functional_type if category == "기능성" else None,
        "key_ingredients": [s.strip() for s in ingredients.split(",") if s.strip()],
        "owned_evidence": evidence,
    }
    custom.append(product)
    st.session_state[_PID] = product["product_id"]
    st.toast(f"‘{product['name']}’ 등록 · 실증 자료 {len(evidence)}개", icon=":material/check:")
    st.rerun()
