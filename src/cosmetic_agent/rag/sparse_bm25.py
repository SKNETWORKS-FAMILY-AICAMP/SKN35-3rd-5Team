"""
[rag/sparse_bm25.py]
BM25 키워드 Sparse 검색기 래퍼.
"""
from pathlib import Path
from typing import Any
from langchain_core.documents import Document


class SparseBM25Retriever:
    def __init__(self, index_path: Path):
        self.index_path = index_path
        # TODO (팀원 구현 영역):
        # pickle 파일로부터 BM25Okapi 인덱스 및 문서 메타데이터 로드

    def search_sparse(self, query: str, top_k: int = 10) -> list[Document]:
        """BM25 키워드 검색을 수행합니다."""
        # TODO (팀원 구현 영역):
        # 질의 토큰화 후 get_top_n 호출하여 Document 리스트 반환
        return []
