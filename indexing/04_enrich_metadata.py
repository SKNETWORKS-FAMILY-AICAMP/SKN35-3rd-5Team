"""
[04_enrich_metadata.py]
조문 청크에 식별자(ID), 권위도(Authority), 적용범위(Scope) 메타데이터를 부여하는 스크립트.
"""
from typing import Any


def enrich_chunk_metadata(chunk: dict[str, Any], doc_type: str, authority: int) -> dict[str, Any]:
    """청크에 표준 메타데이터 스키마를 부여합니다.

    ID 규칙: {DOC_TYPE}_{문서약칭}_{조항}
    예: LAW_시행규칙_별표5-2가
    """
    # TODO (팀원 구현 영역):
    enriched = {
        "id": chunk.get("id", "UNKNOWN_ID"),
        "source": chunk.get("source", ""),
        "doc_type": doc_type,        # 법령, 고시, 지침, 사례
        "authority": authority,      # 1, 2, 3, 4
        "article": chunk.get("article", ""),
        "product_scope": chunk.get("product_scope", "공통"), # 공통, 일반, 기능성
        "effective_date": chunk.get("effective_date", "2024-01-01"),
        "content": chunk.get("content", ""),
    }
    return enriched
