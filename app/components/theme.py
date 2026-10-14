"""
[app/components/theme.py]
디자인 토큰(Python 쪽)과 CSS 주입. 진입 파일이 매 실행 inject_base_css() 를 한 번 부른다.

- CSS 토큰은 styles/base.css 의 :root 에 --bw-* 로 있다. 색을 바꿀 때는 base.css 와
  .streamlit/config.toml 두 곳만 고친다.
- 판정 상태는 네 가지 톤(risk · caution · pass · hold)으로만 표현한다. 큰 경고 박스 대신 작은 태그를 쓴다.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st

from app.components.icons import icon_css

STYLES_DIR = Path(__file__).resolve().parent / "styles"

# 판정 → (화면 상태 이름, 톤). 판정 단어 대신 사용자가 할 일을 말한다.
STATUS: dict[str, tuple[str, str]] = {
    "불가": ("수정 필요", "risk"),
    "조건부": ("실증 필요", "caution"),
    "가능": ("사용 가능", "pass"),
    "판단보류": ("전문가 검토", "hold"),
}

# 위반 유형 → 표시 이름
VIOLATION_LABEL: dict[str, str] = {
    "의약품오인": "의약품 오인",
    "범위이탈": "화장품 범위 이탈",
    "기능성오인": "기능성 오인",
    "실증필요": "실증 필요",
    "비교광고": "비교 광고",
    "소비자오인": "소비자 오인",
    "없음": "없음",
}

AUTHORITY: dict[int, str] = {1: "법령", 2: "고시", 3: "지침", 4: "사례"}

# 차트 등 Python 에서 색이 필요할 때만 쓴다 (base.css 와 같은 값)
COLORS: dict[str, str] = {
    "accent": "#2F5D4B",
    "accent_soft": "#EBF1ED",
    "ink": "#1E2320",
    "muted": "#767B77",
    "line": "#E7E5E0",
    "risk": "#B23B35",
    "caution": "#B97A17",
    "hold": "#8A8F8B",
}


def status_of(verdict: str) -> tuple[str, str]:
    """판정 이름 → (상태 이름, 톤). 모르는 값은 전문가 검토로 본다."""
    return STATUS.get(verdict, STATUS["판단보류"])


@lru_cache(maxsize=16)
def _read_css(path: Path, mtime: float) -> str:
    return path.read_text(encoding="utf-8")


def _css_text(name: str) -> str:
    path = STYLES_DIR / f"{name}.css"
    return _read_css(path, path.stat().st_mtime)


def inject_base_css() -> None:
    """토큰·레이아웃·공통 컴포넌트 CSS 와 아이콘 마스크를 넣는다. 화면 자리는 차지하지 않는다."""
    st.html(f"<style>{_css_text('base')}\n{icon_css()}</style>")


def inject_css(name: str) -> None:
    """화면별 CSS(styles/<name>.css)를 넣는다."""
    st.html(f"<style>{_css_text(name)}</style>")
