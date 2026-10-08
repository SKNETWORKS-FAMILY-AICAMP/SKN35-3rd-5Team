"""
[rag/hybrid.py]
Dense와 Sparse 검색 결과를 RRF(Reciprocal Rank Fusion) 알고리즘으로 병합하는 하이브리드 검색기.
"""
from langchain_core.documents import Document
from .vector_store import VectorStoreRetriever
from .sparse_bm25 import SparseBM25Retriever


class HybridRetriever:
    def __init__(
        self,
        dense_retriever: VectorStoreRetriever,
        sparse_retriever: SparseBM25Retriever,
        rrf_k: int = 60,
    ):
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        product_scope: str = "공통",
        min_statute_count: int = 2,
    ) -> list[Document]:
        """Dense + BM25 검색 후 RRF 병합 및 법령/고시 최소 할당 보장.

        Args:
            query: 질의문
            top_k: 최종 반환 개수 (기본 4)
            product_scope: 제품 범위 필터
            min_statute_count: 법령/고시(authority <= 2) 최소 포함 보장 개수
        """
        # TODO (팀원 구현 영역):
        # 1. dense.search_dense(query, top_k=10, product_scope)
        # 2. sparse.search_sparse(query, top_k=10)
        # 3. RRF score = 1 / (rank + rrf_k) 계산하여 점수 병합
        # 4. authority <= 2 인 문서를 우선 슬롯에 2개 확보 후 나머지 채우기
        return []
