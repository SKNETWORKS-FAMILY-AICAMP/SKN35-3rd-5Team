"""
[app/components/layout.py]
화면 공통 골격: HTML 출력 도우미, 페이지 머리, 데이터 상태 표시, 시각 표기.
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime

import streamlit as st

from app.components.icons import icon


def esc(text: object) -> str:
    """HTML 에 넣을 사용자·데이터 문자열을 이스케이프한다."""
    return _html.escape("" if text is None else str(text), quote=True)


def html(markup: str, *, js: bool = False, inline: bool = False) -> None:
    """디자인 시스템 클래스를 쓰는 HTML 블록을 그린다.
    js=True 면 <script> 를 실행한다. inline=True 면 가로 컨테이너 안에서 내용 폭만 차지한다."""
    st.html(f'<div class="bw">{markup}</div>', unsafe_allow_javascript=js, width="content" if inline else "stretch")


def iga(word: str) -> str:
    """받침에 맞는 주격 조사 '이/가'."""
    last = re.sub(r"\s*\([^)]*\)\s*$", "", word or "").rstrip()[-1:]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "이(가)"


def mode_badge(health: dict) -> str:
    """데이터 상태 표시 (점 색 + 글자). Mock 이면 '데모 데이터', API 모드면 연결 상태."""
    if health.get("mode") == "mock":
        return (f'<span class="bw-mode" title="{esc(health.get("detail", ""))}">'
                f'{esc(health.get("label", "데모 데이터"))}</span>')
    cls = "is-live" if health.get("ok") else "is-down"
    return (f'<span class="bw-mode {cls}" title="{esc(health.get("detail", ""))}">'
            f'{esc(health.get("label", "API"))}</span>')


def page_header(title: str, desc: str, *, health: dict | None = None, beta: bool = False) -> None:
    """페이지 제목 + 한 줄 설명 + 오른쪽 데이터 상태."""
    tag = '<span class="bw-beta">Beta</span>' if beta else ""
    right = mode_badge(health) if health else ""
    html(
        f'<div class="bw-head"><div><div class="bw-head-title"><h1>{esc(title)}</h1>{tag}</div>'
        f'<p>{esc(desc)}</p></div>{right}</div>'
    )


def clock(at: datetime) -> str:
    """'오전 10:24' 형식."""
    ampm = "오전" if at.hour < 12 else "오후"
    hour = at.hour % 12 or 12
    return f"{ampm} {hour}:{at.minute:02d}"


def ago(at: datetime, now: datetime | None = None) -> str:
    """'지금' · 'n분 전' · 'n시간 전' · 'n일 전'."""
    sec = int(((now or datetime.now()) - at).total_seconds())
    if sec < 60:
        return "지금"
    if sec < 3600:
        return f"{sec // 60}분 전"
    if sec < 86400:
        return f"{sec // 3600}시간 전"
    return f"{sec // 86400}일 전"


def seconds(ms: float | None) -> str:
    """밀리초 → '0.41초' 형식."""
    if not ms:
        return "-"
    return f"{ms / 1000:.2f}초" if ms < 10000 else f"{ms / 1000:.1f}초"
