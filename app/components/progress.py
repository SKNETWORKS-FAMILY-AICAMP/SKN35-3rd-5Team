"""
[app/components/progress.py]
검토 진행 표시 — backend.review_events() 가 실제로 낸 이벤트만 그린다.

- 단계 이벤트가 오면: 받은 단계만 순서대로 (끝난 단계 ✓ + 실측 시간, 진행 중 단계, 건너뛴 단계)
- 단계 없이 기다리는 중이면(스트림이 없는 API): "서버가 검토하는 중 · 경과 n초" 만 — 퍼센트·가짜 단계 없음
- 답변 조각(token)이 오면: 받은 글자만 이어 붙여 보여 준다
- 카드는 갱신마다 새로 그려진다 → 계속 도는 움직임은 경과 시간(--bw-t), 막 바뀐 줄의 한 번짜리 움직임은
  그 뒤로 지난 시간(--bw-in · --bw-pop)만큼 앞당겨 시작해, 다시 그려져도 처음부터 반복하지 않고 이어진다
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.components.brand import ASSISTANT_NAME, avatar_img
from app.components.icons import icon
from app.components.layout import esc
from app.services.contract import PIPELINE_STEPS

_NAMES = dict(PIPELINE_STEPS)
_FRESH = 0.45   # 이 시간(초) 안에 나타나거나 끝난 줄만 한 번짜리 움직임을 보인다


@dataclass
class Progress:
    """진행 상태 — 이벤트를 받을 때마다 apply() 한다."""
    order: list[str] = field(default_factory=list)
    stages: dict[str, dict] = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list)
    waiting: bool = False
    t0: float = field(default_factory=time.perf_counter)

    def apply(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "stage":
            key, now = event["key"], time.perf_counter()
            if key not in self.stages:
                self.order.append(key)
            first = self.stages.get(key, {}).get("first", now)
            self.stages[key] = {"status": {"start": "run"}.get(event["status"], event["status"]), "ms": event.get("ms"),
                                "first": first, "at": now}
        elif kind == "token":
            self.tokens.append(event.get("text", ""))
        elif kind == "wait":
            self.waiting = True

    @property
    def current(self) -> str | None:
        return next((k for k in reversed(self.order) if self.stages[k]["status"] == "run"), None)


def _ms(ms: float | None) -> str:
    if ms is None:
        return ""
    return f"{ms:.0f}ms" if ms < 1000 else f"{ms / 1000:.1f}초"


def card(p: Progress, *, elapsed: float | None, demo: bool) -> str:
    """진행 카드 HTML. elapsed 는 실측 경과 초 (Mock 데모 속도 조절 중엔 None)."""
    cur = p.current
    if p.waiting and not p.order:
        headline = "서버가 검토하는 중입니다"
    elif cur:
        headline = f"{_NAMES.get(cur, cur)} 중"
    else:
        headline = "규정 문서를 찾고 있습니다"
    now = time.perf_counter()
    rows = []
    for key in p.order:
        st = p.stages[key]
        ic = {"done": icon("check", 14), "skip": icon("remove", 14)}.get(st["status"], '<span class="bw-live-dot"></span>')
        name = esc(_NAMES.get(key, key)) + (" (건너뜀)" if st["status"] == "skip" else "")
        cls, ages = [f'is-{st["status"]}'], []
        if now - st["first"] < _FRESH:
            cls.append("is-new")
            ages.append(f'--bw-in:{now - st["first"]:.2f}s')
        if st["status"] == "done" and now - st["at"] < _FRESH:
            cls.append("is-pop")
            ages.append(f'--bw-pop:{now - st["at"]:.2f}s')
        style = f' style="{";".join(ages)}"' if ages else ""
        rows.append(f'<li class="{" ".join(cls)}"{style}>{ic}<span class="nm">{name}</span>'
                    f'<span class="ms">{_ms(st.get("ms"))}</span></li>')
    steps = f'<ul class="bw-live-steps">{"".join(rows)}</ul>' if rows else ""
    text = f'<p class="bw-live-text">{esc("".join(p.tokens))}<span class="bw-caret"></span></p>' if p.tokens else ""
    meta = []
    if elapsed is not None:
        meta.append(f"경과 {elapsed:.1f}초")
    if demo:
        meta.append("데모 데이터 — 단계 표시 속도를 늦춰 보여 줍니다")
    meta_html = f'<div class="bw-live-meta">{" · ".join(meta)}</div>' if meta else ""
    return (f'<article class="bw-ai is-progress" style="--bw-t:{now - p.t0:.2f}s"><div class="bw-ai-head"><span class="bw-avatar is-thinking">{avatar_img(32)}</span>'
            f'<b>{ASSISTANT_NAME}</b><span class="bw-rag">{icon("menu_book", 15)}{esc(headline)}</span></div>'
            f'<div class="bw-live" role="status" aria-live="polite">'
            f'<div class="bw-dots"><i></i><i></i><i></i></div>{steps}{text}{meta_html}</div></article>')
