"""
[app/components/blocks.py]
답변에 붙는 확장 블록 — 응답의 ui.blocks 에 있을 때만 그린다 (없으면 아무것도 안 그린다).

  {"type": "chart", "title", "unit", "data": [{"label", "value"}]}            데이터가 있을 때만
  {"type": "question", "id", "prompt", "options": [...], "follow_up": "…{answer}…"}   사용자 입력이 필요할 때만

새 블록 종류는 @register("이름") 함수 하나를 더하면 된다. 모르는 종류는 조용히 건너뛴다.
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from app.components.icons import icon
from app.components.layout import esc, html

Renderer = Callable[[dict, str, Callable[[dict, str], None]], None]
RENDERERS: dict[str, Renderer] = {}


def register(kind: str):
    def deco(fn: Renderer) -> Renderer:
        RENDERERS[kind] = fn
        return fn
    return deco


@register("chart")
def _chart(block: dict, key: str, on_answer) -> None:
    data = [d for d in block.get("data") or [] if isinstance(d.get("value"), (int, float))]
    if not data:
        return
    unit = f' <span class="bw-block-unit">({esc(block["unit"])})</span>' if block.get("unit") else ""
    html(f'<h4 class="bw-sec">{icon("bar_chart", 15)}{esc(block.get("title", "차트"))}{unit}</h4>')
    frame = pd.DataFrame({"값": [d["value"] for d in data]}, index=[str(d["label"]) for d in data])
    st.bar_chart(frame, height=40 + 34 * len(data), color="#1F5A47", horizontal=True)


@register("question")
def _question(block: dict, key: str, on_answer) -> None:
    options = block.get("options") or []
    if not block.get("prompt") or not options:
        return
    html(f'<div class="bw-ask">{icon("help_outline", 16)}<span>{esc(block["prompt"])}</span></div>')
    pick = st.pills("답 고르기", options, key=f"q_{key}", label_visibility="collapsed")
    if pick:
        on_answer(block, pick)


def render(blocks: list[dict] | None, key: str, on_answer: Callable[[dict, str], None]) -> None:
    """블록 목록을 그린다. on_answer(block, answer) 는 question 블록에서 답을 골랐을 때 부른다."""
    for i, block in enumerate(blocks or []):
        fn = RENDERERS.get(block.get("type", ""))
        if fn is None:
            continue
        with st.container(key=f"blk_{key}_{i}", gap="small"):
            fn(block, f"{key}_{i}", on_answer)
