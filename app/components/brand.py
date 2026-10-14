"""
[app/components/brand.py]
브랜드 자산(팀 캐릭터 · 워드마크 로고)을 st.html 에 넣을 수 있는 <img> 로 돌려준다.

- 캐릭터: 5팀 메인 캐릭터(실험복 토끼 연구원). 원본은 팀 공유 PNG(1254px, 투명) — 여기엔 화면용으로
  자른 WebP 만 둔다 (app/static/brand/rabbit-*.webp).
- 쓰는 곳은 세 군데뿐이다: 로고 옆 마크 · AI 답변 아바타 · 첫 화면(빈 상태). 장식으로 늘리지 않는다.
- st.html 은 인라인 <svg> 를 지우고 상대 경로가 페이지마다 달라지므로 data URI 로 넣는다.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

BRAND_NAME = "Beaurette"
BRAND_NAME_KO = "뷰렛"
ASSISTANT_NAME = "뷰렛 AI"
TAGLINE = "규정 문서를 근거로 광고 문구를 검토하는 AI"

_BRAND_DIR = Path(__file__).resolve().parents[1] / "static" / "brand"
_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp"}


@lru_cache(maxsize=8)
def _data_uri(filename: str) -> str:
    path = _BRAND_DIR / filename
    return f"data:{_MIME[path.suffix]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def avatar_img(size: int = 32, *, alt: str = "") -> str:
    """AI 답변 아바타 — 캐릭터 얼굴 (원형 자르기는 CSS .bw-avatar)."""
    return f'<img src="{_data_uri("rabbit-avatar.webp")}" width="{size}" height="{size}" alt="{alt}">'


def avatar_uri() -> str:
    """챗봇 위젯과 버튼에서도 같은 토끼 얼굴 자산을 사용한다."""
    return _data_uri("rabbit-avatar.webp")


def character_img(height: int = 200, *, alt: str = "") -> str:
    """빈 상태용 캐릭터 전신."""
    return f'<img src="{_data_uri("rabbit-full.webp")}" style="height:{height}px;width:auto" alt="{alt}">'


def lockup_img(height: int = 36) -> str:
    """캐릭터 마크 + Beaurette 워드마크 로고 <img> (2배 해상도 PNG)."""
    return f'<img src="{_data_uri("beaurette-lockup.png")}" style="height:{height}px;width:auto" alt="{BRAND_NAME}">'
