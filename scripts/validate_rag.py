"""현재 인덱스의 Qdrant 상태와 골든셋 검색 품질을 검증한다."""

from __future__ import annotations

import json

from cosmetic_agent.common.config import settings
from cosmetic_agent.rag.hybrid import HybridRetriever
from cosmetic_agent.rag.query_rewriter import QueryRewriter
from cosmetic_agent.rag.sparse_bm25 import SparseBM25Retriever
from cosmetic_agent.rag.vector_store import VectorStoreRetriever


def main() -> None:
    dense = VectorStoreRetriever(
        settings.QDRANT_COLLECTION_NAME,
        settings.QDRANT_URL,
        qdrant_api_key=settings.QDRANT_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
    )
    hybrid = HybridRetriever(
        dense,
        SparseBM25Retriever(settings.BM25_INDEX_PATH),
    )
    rewriter = QueryRewriter()

    collection = dense.client.get_collection(settings.QDRANT_COLLECTION_NAME)
    print(
        "COLLECTION",
        settings.QDRANT_COLLECTION_NAME,
        "STATUS",
        collection.status,
        "POINTS",
        collection.points_count,
    )

    rows = []
    for path in (settings.DEV_SET_PATH, settings.HOLDOUT_SET_PATH):
        rows.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    ranks: list[int | None] = []
    for row in rows:
        query = rewriter.rewrite(row["copy_text"])
        ids = [
            document.metadata["chunk_id"]
            for document in hybrid.retrieve(query, top_k=4)
        ]
        rank = ids.index(row["required_citation"]) + 1 if row["required_citation"] in ids else None
        ranks.append(rank)
        print(row["id"], "RANK", rank, "TOP4", ids)

    hits = sum(rank is not None for rank in ranks)
    mrr = sum(1 / rank for rank in ranks if rank is not None) / len(ranks)
    print("RECALL_AT_4", f"{hits}/{len(ranks)}", "MRR", round(mrr, 4))

    for scope in ("일반", "기능성"):
        documents = hybrid.retrieve(
            rewriter.rewrite("화장품 표시 광고 효능 효과"),
            top_k=20,
            product_scope=scope,
        )
        leaks = [
            document.metadata["chunk_id"]
            for document in documents
            if document.metadata.get("product_scope") not in ("공통", scope)
        ]
        print("SCOPE", scope, "RESULTS", len(documents), "LEAKS", leaks)


if __name__ == "__main__":
    main()
