"""
[app/components/brand.py]
브랜드 자산(새싹 마스코트 · 워드마크 로고)을 st.html 에 넣을 수 있는 <img> 로 돌려준다.

- st.html 은 인라인 <svg> 를 지우므로 data URI 이미지로 넣는다. 파일 원본은 app/static/brand/.
- 마스코트는 로고 · AI 답변 아바타 · 첫 화면 · 사이드바 아래 카드 한 곳에만 쓴다. 장식으로 늘리지 않는다.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

BRAND_NAME = "Beaurette"
BRAND_NAME_KO = "뷰렛"
TAGLINE = "근거로 검토하고,\n쓸 수 있는 문구로 고쳐 드립니다."

_BRAND_DIR = Path(__file__).resolve().parents[1] / "static" / "brand"


@lru_cache(maxsize=8)
def _data_uri(filename: str) -> str:
    path = _BRAND_DIR / filename
    mime = "image/svg+xml" if path.suffix == ".svg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def mascot_img(size: int = 64, *, tight: bool = False, alt: str = "") -> str:
    """마스코트 <img>. tight=True 면 몸통이 꽉 차게 잘린 아바타용."""
    src = _data_uri("mascot-tight.svg" if tight else "mascot.svg")
    return f'<img src="{src}" width="{size}" height="{size}" alt="{alt}">'


def scene_img(width: int = 150) -> str:
    """사이드바 아래 카드의 마스코트 장면 <img> (잎 장식 포함)."""
    return f'<img src="{_data_uri("mascot-scene.svg")}" width="{width}" alt="">'


def lockup_img(height: int = 34) -> str:
    """마스코트 + Beaurette 워드마크 로고 <img> (2배 해상도 PNG)."""
    return f'<img src="{_data_uri("beaurette-lockup.png")}" style="height:{height}px;width:auto" alt="{BRAND_NAME}">'
