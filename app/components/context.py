"""
[app/components/context.py]
검토 기준 바: 어떤 제품을, 어떤 실증 자료를 가진 상태로 검토하는지 정한다.
문구 검토와 상세페이지 검토 화면이 같이 쓰고, 선택은 화면을 옮겨도 유지된다.

실증 자료를 해제하면 그 자료 없이 쓸 수 있는 단계까지만 제안이 내려간다(데모 핵심 장면).
"""
from __future__ import annotations

import streamlit as st

from app.components.layout import esc, html
from app.services import backend

_PID = "bw_pid"          # 선택한 제품 id (화면을 옮겨도 유지)
_EV = "bw_ev_state"      # {product_id: [체크 여부, ...]}


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
    products = backend.list_products()
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


def render_context_bar(key: str = "ctx") -> tuple[dict, dict]:
    """검토 기준 바를 그리고 (요청용 제품, 기준 요약) 을 돌려준다."""
    products = backend.list_products()
    ids = [p["product_id"] for p in products]
    by_id = {p["product_id"]: p for p in products}
    current()  # 기본값 보정
    pid = st.session_state[_PID]

    with st.container(horizontal=True, key=key, vertical_alignment="center", gap="small"):
        sel_key = f"{key}_product"
        st.selectbox(
            "검토할 제품", ids, index=ids.index(pid), format_func=lambda i: by_id[i]["name"],
            key=sel_key, label_visibility="collapsed", width=230,
            on_change=_on_product_change, args=(sel_key,),
        )
        product = by_id[st.session_state[_PID]]
        states = _evidence_state(product)
        evs = product.get("owned_evidence", [])
        on = sum(states)
        label = f"실증 자료 {on}/{len(evs)}" if evs else "실증 자료 없음"
        with st.popover(label, icon=":material/science:"):
            html(f'<div class="bw-pop-head">{esc(product["name"])} · 보유 실증 자료</div>'
                 '<div class="bw-pop-sub">체크한 자료 범위 안에서만 효능 표현을 제안합니다.</div>')
            if not evs:
                html('<p class="bw-pop-sub" style="margin-top:8px">등록된 실증 자료가 없습니다. '
                     '근거가 필요 없는 낮은 단계 표현까지만 제안합니다.</p>')
            for i, ev in enumerate(evs):
                ck = f'{key}_ev_{product["product_id"]}_{i}'
                st.checkbox(f'{ev["test_type"]} · {ev["item"]}', value=states[i], key=ck,
                            on_change=_on_evidence_change, args=(product["product_id"], i, ck))
                hint = backend.unlock_hint(product, ev) if states[i] else None
                hint_html = (f'<div class="bw-ev-hint">{esc(hint)}</div>' if hint else
                             '<div class="bw-ev-hint is-off">해제됨 — 이 자료가 필요한 표현은 제안하지 않습니다.</div>'
                             if not states[i] else "")
                html('<div class="bw-ev"><dl>'
                     f'<dt>결과</dt><dd>{esc(ev.get("value") or "-")}</dd>'
                     f'<dt>기관</dt><dd>{esc(ev.get("institute") or "-")}</dd></dl>{hint_html}</div>')
        html(f'<span class="bw-ctx-meta"><b>{esc(category_label(product))}</b> 기준으로 검토합니다</span>', inline=True)

    return current()
