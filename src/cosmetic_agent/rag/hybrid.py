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
        min_statute_count: int = 1,
    ) -> list[Document]:
        """두 검색 순위를 합치고 법령·고시 근거를 최소 개수만큼 보장한다."""
        if top_k <= 0:
            return []
        dense = self.dense.search_dense(query, self.candidate_k, product_scope)
        sparse = self.sparse.search_sparse(query, self.candidate_k, product_scope)

        documents: dict[str, Document] = {}
        scores: dict[str, float] = {}
        ranks: dict[str, dict[str, int]] = {}
        channel_weights = {"dense": 2.0, "sparse": 1.0}
        for channel, results in (("dense", dense), ("sparse", sparse)):
            for rank, document in enumerate(results, start=1):
                chunk_id = _document_id(document)
                if not chunk_id or chunk_id == "None":
                    continue
                documents.setdefault(chunk_id, document)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (
                    channel_weights[channel] / (self.rrf_k + rank)
                )
                ranks.setdefault(chunk_id, {})[channel] = rank

        # 사례보다 법령·고시·지침을 근거로 우선 사용하되 검색 관련성이 낮은
        # 규정을 과도하게 끌어올리지 않도록 작은 tie-break 보너스만 준다.
        authority_bonus = {1: 0.004, 2: 0.003, 3: 0.002, 4: 0.0}
        for chunk_id, document in documents.items():
            authority = int(document.metadata.get("authority", 4))
            scores[chunk_id] += authority_bonus.get(authority, 0.0)

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
