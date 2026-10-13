"""Qdrant Dense 벡터 검색기."""

from __future__ import annotations

from langchain_core.documents import Document
from openai import OpenAI
from qdrant_client import QdrantClient, models


class VectorStoreRetriever:
    def __init__(
        self,
        collection_name: str,
        url: str,
        *,
        qdrant_api_key: str = "",
        openai_api_key: str = "",
        openai_base_url: str = "https://api.openai.com/v1",
        embedding_model: str = "text-embedding-3-small",
    ):
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.client = QdrantClient(
            url=url,
            api_key=qdrant_api_key or None,
            timeout=30,
            check_compatibility=False,
        )
        self.embeddings = OpenAI(api_key=openai_api_key, base_url=openai_base_url)

    def search_dense(
        self,
        query: str,
        top_k: int = 10,
        product_scope: str = "공통",
    ) -> list[Document]:
        """질의를 임베딩한 뒤 제품 범위를 반영해 유사 청크를 검색한다."""
        vector = self.embeddings.embeddings.create(
            model=self.embedding_model,
            input=[query],
            encoding_format="float",
        ).data[0].embedding

        query_filter = None
        if product_scope and product_scope != "공통":
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(
                        key="product_scope",
                        match=models.MatchValue(value="공통"),
                    ),
                    models.FieldCondition(
                        key="product_scope",
                        match=models.MatchValue(value=product_scope),
                    ),
                ]
            )

        points = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        ).points
        documents: list[Document] = []
        for point in points:
            payload = dict(point.payload or {})
            content = str(payload.pop("content", ""))
            payload["chunk_id"] = payload.get("chunk_id") or payload.get("id") or str(point.id)
            payload["dense_score"] = float(point.score)
            documents.append(Document(page_content=content, metadata=payload))
        return documents
