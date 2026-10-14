"""원문 규정 청크에 검색용 규제 메타데이터를 부착한다.

골든셋 문구나 정답 ID를 사용하지 않고 문서 원문과 기존 구조 정보만 사용한다.
"""

from __future__ import annotations

import re
from typing import Any


_CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "의약품 오인",
        r"의약품|질병|치료|예방|재생|염증|탈모",
        ("의약품 오인", "질병 효능", "치료 예방 표현"),
    ),
    (
        "기능성 범위",
        r"기능성|미백|주름|자외선|탈모",
        ("기능성화장품", "심사 범위", "효능 효과"),
    ),
    (
        "실증 필요",
        r"실증|시험|조사|객관적|과학적|통계",
        ("표시 광고 실증", "시험 결과", "객관적 근거"),
    ),
    (
        "비교·최상급",
        r"비교|최고|최상|우수|배타적",
        ("비교 광고", "최상급 표현", "객관적 비교 기준"),
    ),
    (
        "전문가·기관 보증",
        r"전문의|의사|병원|기관|추천|공인|보증",
        ("전문가 추천", "기관 보증", "소비자 오인"),
    ),
    (
        "인체 유래",
        r"인체유래|인체 유래|세포|배양액",
        ("인체 유래 원료", "세포 유래 표현"),
    ),
    (
        "사용 방법",
        r"사용방법|사용 방법|용법|용량",
        ("사용 방법", "용법 용량"),
    ),
    (
        "소비자 오인",
        r"허위|과장|오인|기만",
        ("허위 과장 광고", "소비자 오인"),
    ),
)


def _legal_force(authority: int) -> str:
    return {
        1: "법령",
        2: "고시",
        3: "행정지침",
        4: "처분사례",
    }.get(authority, "참고자료")


def enrich_chunk_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """기존 청크를 변경하지 않고 검색용 메타데이터를 추가한다."""
    enriched = dict(chunk)
    authority = int(enriched.get("authority", 4))
    searchable_source = " ".join(
        str(enriched.get(field, ""))
        for field in ("source", "article", "section_title", "content")
    )

    categories: list[str] = []
    keywords: list[str] = []
    for category, pattern, terms in _CATEGORY_RULES:
        if re.search(pattern, searchable_source):
            categories.append(category)
            keywords.extend(terms)

    if not categories:
        categories.append("일반 표시·광고")
        keywords.extend(("화장품 표시 광고", "준수사항"))

    enriched["claim_categories"] = categories
    enriched["evidence_requirement"] = (
        "필수" if "실증 필요" in categories else "조건부"
    )
    enriched["legal_force"] = _legal_force(authority)
    enriched["search_keywords"] = list(dict.fromkeys(keywords))
    return enriched


def build_search_text(chunk: dict[str, Any]) -> str:
    """Dense와 BM25에 공통으로 사용할 검색 표현을 생성한다."""
    enriched = enrich_chunk_metadata(chunk)
    header = " | ".join(
        filter(
            None,
            (
                str(enriched.get("source", "")),
                str(enriched.get("article", "")),
                str(enriched.get("section_title", "")),
                f"문서효력 {enriched['legal_force']}",
                f"주장유형 {', '.join(enriched['claim_categories'])}",
                f"실증요건 {enriched['evidence_requirement']}",
                f"검색어 {', '.join(enriched['search_keywords'])}",
            ),
        )
    )
    return f"{header}\n{enriched.get('content', '')}".strip()


def enrich_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_chunk_metadata(chunk) for chunk in chunks]
