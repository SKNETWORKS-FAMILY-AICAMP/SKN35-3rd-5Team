"""
[rag/vector_store.py]
Qdrant Dense 벡터 저장소 검색기 래퍼.
"""
from typing import Any
from langchain_core.documents import Document


class VectorStoreRetriever:
    def __init__(self, collection_name: str, url: str):
        self.collection_name = collection_name
        self.url = url
        # TODO (팀원 구현 영역):
        # QdrantClient 및 OpenAI Embeddings 초기화

    def search_dense(self, query: str, top_k: int = 10, product_scope: str = "공통") -> list[Document]:
        """Qdrant 벡터 유사도 검색을 수행합니다.

        Args:
            query: 검색 질의
            top_k: 상위 K개 문서
            product_scope: 메타데이터 필터 (공통 또는 해당 제품 유형)
        """
        # TODO (팀원 구현 영역):
        # Qdrant filter (product_scope in ["공통", product_scope]) 적용 후 검색
        return []
