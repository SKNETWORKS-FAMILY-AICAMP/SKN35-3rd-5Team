"""Dense와 BM25 결과를 Reciprocal Rank Fusion으로 결합한다."""

from __future__ import annotations

from langchain_core.documents import Document

from .sparse_bm25 import SparseBM25Retriever
from .vector_store import VectorStoreRetriever


def _document_id(document: Document) -> str:
    return str(document.metadata.get("chunk_id") or document.metadata.get("id"))


class HybridRetriever:
    def __init__(
        self,
        dense_retriever: VectorStoreRetriever,
        sparse_retriever: SparseBM25Retriever,
        rrf_k: int = 60,
        candidate_k: int = 30,
    ):
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        product_scope: str = "공통",
        min_statute_count: int = 2,
    ) -> list[Document]:
        """두 검색 순위를 합치고 법령·고시 근거를 최소 개수만큼 보장한다."""
        if top_k <= 0:
            return []
        dense = self.dense.search_dense(query, self.candidate_k, product_scope)
        sparse = self.sparse.search_sparse(query, self.candidate_k)

        documents: dict[str, Document] = {}
        scores: dict[str, float] = {}
        ranks: dict[str, dict[str, int]] = {}
        for channel, results in (("dense", dense), ("sparse", sparse)):
            for rank, document in enumerate(results, start=1):
                chunk_id = _document_id(document)
                if not chunk_id or chunk_id == "None":
                    continue
                documents.setdefault(chunk_id, document)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)
                ranks.setdefault(chunk_id, {})[channel] = rank

        ordered_ids = sorted(scores, key=lambda item: (-scores[item], item))
        statute_ids = [
            item
            for item in ordered_ids
            if int(documents[item].metadata.get("authority", 99)) <= 2
        ]
        selected_ids = statute_ids[: min(min_statute_count, top_k)]
        selected_ids.extend(item for item in ordered_ids if item not in selected_ids)
        selected_ids = selected_ids[:top_k]

        output: list[Document] = []
        for chunk_id in selected_ids:
            source = documents[chunk_id]
            metadata = dict(source.metadata)
            metadata["chunk_id"] = chunk_id
            metadata["rrf_score"] = scores[chunk_id]
            metadata["retrieval_ranks"] = ranks[chunk_id]
            output.append(Document(page_content=source.page_content, metadata=metadata))
        return output
