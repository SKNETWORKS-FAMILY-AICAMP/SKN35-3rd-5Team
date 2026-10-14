"""
[app/components/suggest.py]
답변 안 「수정 제안」 — 대체 문구 후보를 고르고(근거 최대 · 균형 · 가장 안전), 복사하고, 그 문구로 다시 검토한다.

- 후보는 응답의 ui.variants (백엔드 copy_suggester 의 candidates 를 옮긴 것). 없으면 suggestion + alternatives 로 만든다.
- 최신 답변에만 위젯으로 그린다. 지난 답변은 cards._suggestion 이 정적으로 그린다.
"""
from __future__ import annotations

import streamlit as st

from app.components import threads
from app.components.cards import COPY_SCRIPT
from app.components.icons import icon
from app.components.layout import esc, html

TIER_LABEL = {"strong": "근거 최대", "balanced": "균형", "safe": "가장 안전"}
_PICKS = "bw_sugpick"   # 답변별 마지막으로 보인 후보 — 바뀐 직후 한 번만 문구가 미끄러져 들어온다


def variants_of(resp: dict) -> list[dict]:
    """화면이 쓸 후보 목록 (강한 → 안전)."""
    ui = resp.get("ui", {})
    if ui.get("variants"):
        return ui["variants"]
    sug = resp["result"].get("suggestion")
    if not sug:
        return []
    src = ui.get("suggestion_source", "")
    out = [{"text": f"{sug} {src}".strip(), "tier": "strong", "basis": ui.get("direction", ""),
            "verified": None, "note": None, "chosen": True}]
    for alt in (ui.get("alternatives") or [])[:2]:
        out.append({"text": alt, "tier": "safe" if len(out) == 2 else "balanced", "basis": "",
                    "verified": None, "note": None, "chosen": False})
    return out


def verify_state(v: dict) -> str:
    """후보의 역검증 상태 한 줄 (HTML)."""
    if v.get("verified") is True:
        text = "역검증 통과 · 엔진이 고른 제안" if v.get("chosen") else "역검증 통과"
        return f'<div class="bw-vstate is-ok">{icon("check_circle_outline", 15)}{text}</div>'
    if v.get("verified") is False:
        note = f' — {esc(v["note"])}' if v.get("note") else ""
        return f'<div class="bw-vstate is-fail">{icon("error", 15)}역검증 탈락{note}</div>'
    return f'<div class="bw-vstate">{icon("remove", 15)}역검증 전 — 다시 검토하면 판정합니다</div>'


def _card(v: dict, resp: dict, *, swap: bool = False) -> str:
    ui = resp.get("ui", {})
    checks = ""
    rv = ui.get("reverify")
    if v.get("chosen") and rv:
        parts = []
        if rv.get("numbers_total"):
            parts.append(f'<span>{icon("check", 14)}숫자 {rv["numbers_ok"]}/{rv["numbers_total"]} 실증 일치</span>')
        parts.append(f'<span>{icon("check", 14)}금지어 재검사 {rv.get("banned", 0)}건</span>')
        checks = f'<div class="bw-suggest-check">{"".join(parts)}</div>'
    diff = ""
    if v.get("chosen") and ui.get("diff"):
        items = "".join(
            f'<li class="{"is-del" if d["op"] == "-" else "is-add"}"><span class="op">{"−" if d["op"] == "-" else "+"}</span>'
            f'<span class="t">{esc(d["text"])}</span><span class="why">{esc(d.get("why", ""))}</span></li>'
            for d in ui["diff"])
        diff = (f'<details class="bw-diff"><summary>{icon("chevron_right", 16)}원문에서 고친 곳 {len(ui["diff"])}군데</summary>'
                f'<ul>{items}</ul></details>')
    basis = f'<p class="bw-suggest-src">{esc(v["basis"])}</p>' if v.get("basis") else ""
    return (f'<div class="bw-suggest is-{v.get("tier", "strong")}{" is-swap" if swap else ""}"><div class="bw-suggest-top">'
            f'<p class="bw-suggest-text">{esc(v["text"])}</p>'
            f'<button type="button" class="bw-copy" data-copy="{esc(v["text"])}" aria-label="제안 문구 복사">'
            f'{icon("content_copy", 15)}<span class="lbl">복사</span></button></div>'
            f'{basis}{verify_state(v)}{checks}{diff}</div>')


def render(resp: dict, key: str, ctx: dict, product: dict, *, last: bool) -> None:
    """최신 답변의 수정 제안 패널. last=True 면 아래에 이어지는 답변 조각이 없다(모서리 처리)."""
    variants = variants_of(resp)
    if not variants:
        return
    chosen = next((i for i, v in enumerate(variants) if v.get("chosen")), 0)
    with st.container(key=f"sug_{key}{'_last' if last else ''}", gap="small"):
        html(f'<h4 class="bw-sec">수정 제안 <span class="n">{len(variants)}</span>'
             f'<span class="bw-sec-note">강도를 골라 복사하거나 그 문구로 다시 검토합니다</span></h4>')
        pick = chosen
        if len(variants) > 1:
            labels = {i: TIER_LABEL.get(v.get("tier"), f"후보 {i + 1}") + (" · 추천" if v.get("chosen") else "")
                      for i, v in enumerate(variants)}
            sel = st.segmented_control("표현 강도", list(labels), default=chosen, format_func=labels.get,
                                       key=f"sugsel_{key}", label_visibility="collapsed")
            pick = chosen if sel is None else sel
        v = variants[pick]
        picks = st.session_state.setdefault(_PICKS, {})
        swap = key in picks and picks[key] != pick
        picks[key] = pick
        html(_card(v, resp, swap=swap) + COPY_SCRIPT, js=True)
        with st.container(horizontal=True, key=f"sugact_{key}", gap="small"):
            if st.button("이 문구로 다시 검토", key=f"sugapply_{key}", icon=":material/refresh:",
                         help="고른 문구를 같은 검토 기준으로 다시 검토합니다"):
                threads.ask(v["text"], ctx, product)
                st.rerun()
