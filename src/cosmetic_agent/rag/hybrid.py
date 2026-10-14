"""Dense와 BM25 결과를 Reciprocal Rank Fusion으로 결합한다."""

from __future__ import annotations

import logging

import re

from langchain_core.documents import Document

from .sparse_bm25 import SparseBM25Retriever
from .vector_store import VectorStoreRetriever
from .reranker import LightweightReranker


def _document_id(document: Document) -> str:
    return str(document.metadata.get("chunk_id") or document.metadata.get("id"))


def _metadata_query_match(chunk_id: str, query: str) -> bool:
    """청크 ID의 의미 있는 한글 구획이 질의에 직접 등장하는지 확인한다.

    특정 평가 문구나 정답 매핑을 사용하지 않고 ``질병``, ``모발``처럼
    인덱싱 단계에서 이미 부여된 분류명만 활용한다.
    """
    labels = re.findall(r"[가-힣]{2,}", chunk_id)
    ignored = {"관리지침", "시행규칙", "화장품법", "실증규정", "별표"}
    return any(label not in ignored and label in query for label in labels)


class HybridRetriever:
    def __init__(
        self,
        dense_retriever: VectorStoreRetriever,
        sparse_retriever: SparseBM25Retriever,
        rrf_k: int = 10,
        candidate_k: int = 30,
        dense_weight: float = 0.1,
        sparse_weight: float = 1.0,
        metadata_match_weight: float = 0.02,
        dense_rescue_rank: int = 2,
        reranker: LightweightReranker | None = None,
        max_per_source: int = 2,
    ):
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k
        self.channel_weights = {
            "dense": dense_weight,
            "sparse": sparse_weight,
        }
        self.metadata_match_weight = metadata_match_weight
        self.dense_rescue_rank = max(0, dense_rescue_rank)
        self.reranker = reranker or LightweightReranker()
        self.max_per_source = max(1, max_per_source)

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        product_scope: str = "공통",
        min_statute_count: int = 1,
        final_k: int | None = None,
    ) -> list[Document]:
        """두 검색 순위를 합치고 법령·고시 근거를 최소 개수만큼 보장한다.

        ``final_k``는 평가에서 후보 순위도 보존하면서 실제 서비스의 최종
        Top K 선택을 동일하게 재현할 때 사용한다.
        """
        if top_k <= 0:
            return []
        selection_k = min(final_k or top_k, top_k)
        if selection_k <= 0:
            return []
        try:
            dense = self.dense.search_dense(query, self.candidate_k, product_scope)
        except Exception as error:  # noqa: BLE001 - Qdrant·임베딩 장애에도 BM25 근거로 검토는 계속한다
            logging.getLogger(__name__).warning("Dense 검색 실패, BM25 만 사용: %s", type(error).__name__)
            dense = []
        sparse = self.sparse.search_sparse(query, self.candidate_k, product_scope)

        documents: dict[str, Document] = {}
        scores: dict[str, float] = {}
        ranks: dict[str, dict[str, int]] = {}
        for channel, results in (("dense", dense), ("sparse", sparse)):
            for rank, document in enumerate(results, start=1):
                chunk_id = _document_id(document)
                if not chunk_id or chunk_id == "None":
                    continue
                documents.setdefault(chunk_id, document)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (
                    self.channel_weights[channel] / (self.rrf_k + rank)
                )
                ranks.setdefault(chunk_id, {})[channel] = rank

        for chunk_id in scores:
            if _metadata_query_match(chunk_id, query):
                scores[chunk_id] += self.metadata_match_weight

        ordered_ids = sorted(scores, key=lambda item: (-scores[item], item))
        reranked_documents = self.reranker.rerank(
            query,
            [documents[item] for item in ordered_ids],
            scores,
            ranks,
        )
        ordered_ids = [_document_id(document) for document in reranked_documents]
        statute_ids = [
            item
            for item in ordered_ids
            if int(documents[item].metadata.get("authority", 99)) <= 2
        ]
        # 관련성 순위를 먼저 보존한다. 법령·고시 최소 개수는 상위 결과에 없을 때만
        # 마지막 비법령 청크를 교체해 보장하며, 법령을 무조건 1위로 끌어올리지 않는다.
        selected_ids = ordered_ids[:selection_k]

        # BM25 중심 결합에서도 Dense 최상위 의미 후보가 완전히 탈락하지 않게 한다.
        # 정답 매핑이 아니라 Dense 검색 자체의 상위 순위만 사용하는 일반 안전장치다.
        protected_dense_ids = {
            _document_id(document)
            for document in dense[: min(self.dense_rescue_rank, selection_k)]
        }
        statute_protected_ids = {
            _document_id(document)
            for document in dense[: min(1, selection_k)]
        }
        for document in reversed(dense[: min(self.dense_rescue_rank, selection_k)]):
            dense_id = _document_id(document)
            if dense_id in selected_ids or dense_id not in scores:
                continue
            replacement = next(
                (
                    index
                    for index in range(len(selected_ids) - 1, -1, -1)
                    if selected_ids[index] not in protected_dense_ids
                ),
                None,
            )
            if replacement is None:
                break
            selected_ids[replacement] = dense_id

        required_statutes = min(min_statute_count, selection_k)
        selected_statutes = sum(
            int(documents[item].metadata.get("authority", 99)) <= 2
            for item in selected_ids
        )
        for statute_id in statute_ids:
            if selected_statutes >= required_statutes:
                break
            if statute_id in selected_ids:
                continue
            replacement = next(
                (
                    index
                    for index in range(len(selected_ids) - 1, -1, -1)
                    if int(documents[selected_ids[index]].metadata.get("authority", 99)) > 2
                    and selected_ids[index] not in statute_protected_ids
                ),
                None,
            )
            if replacement is None:
                break
            selected_ids[replacement] = statute_id
            selected_statutes += 1

        # 동일 문서의 인접 청크가 결과를 독점하지 않게 하여 서로 다른 규정·지침을
        # 함께 검토할 수 있도록 한다. 제거한 자리는 기존 관련성 순서의 다음 후보로 채운다.
        source_counts: dict[str, int] = {}
        duplicate_positions: list[int] = []
        for index, chunk_id in enumerate(selected_ids):
            source = str(documents[chunk_id].metadata.get("source") or chunk_id)
            source_counts[source] = source_counts.get(source, 0) + 1
            if source_counts[source] > self.max_per_source:
                duplicate_positions.append(index)
        for position in duplicate_positions:
            previous_id = selected_ids[position]
            previous_source = str(
                documents[previous_id].metadata.get("source") or previous_id
            )
            replacement_id = next(
                (
                    candidate_id
                    for candidate_id in ordered_ids
                    if candidate_id not in selected_ids
                    and source_counts.get(
                        str(documents[candidate_id].metadata.get("source") or candidate_id),
                        0,
                    )
                    < self.max_per_source
                ),
                None,
            )
            if replacement_id is None:
                continue
            replacement_source = str(
                documents[replacement_id].metadata.get("source") or replacement_id
            )
            selected_ids[position] = replacement_id
            source_counts[previous_source] -= 1
            source_counts[replacement_source] = source_counts.get(replacement_source, 0) + 1

        # 최종 선택 뒤의 후보는 실패 원인 분석용 순위를 유지해 이어 붙인다.
        if top_k > selection_k:
            selected_ids.extend(
                chunk_id
                for chunk_id in ordered_ids
                if chunk_id not in selected_ids
            )
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
