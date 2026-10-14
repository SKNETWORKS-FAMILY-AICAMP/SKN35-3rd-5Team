"""외부 모델 호출 없이 후보 순위를 보정하는 경량 reranker."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

from langchain_core.documents import Document


def _document_id(document: Document) -> str:
    return str(document.metadata.get("chunk_id") or document.metadata.get("id"))


def _korean_bigrams(text: str) -> set[str]:
    compact = re.sub(r"[^가-힣A-Za-z0-9]", "", text.lower())
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _metadata_similarity(query: str, document: Document) -> float:
    metadata = document.metadata
    search_fields = [
        str(metadata.get("section_title", "")),
        " ".join(str(item) for item in metadata.get("claim_categories", [])),
        " ".join(str(item) for item in metadata.get("search_keywords", [])),
    ]
    query_terms = _korean_bigrams(query)
    metadata_terms = _korean_bigrams(" ".join(search_fields))
    if not query_terms or not metadata_terms:
        return 0.0
    # 긴 질의가 불리하지 않도록 기하평균으로 정규화한다.
    return len(query_terms & metadata_terms) / math.sqrt(
        len(query_terms) * len(metadata_terms)
    )


class LightweightReranker:
    """검색 채널 신호와 규제 메타데이터를 결합해 후보를 재정렬한다."""

    def __init__(
        self,
        *,
        base_weight: float = 0.98,
        dense_weight: float = 0.01,
        metadata_weight: float = 0.01,
        candidate_limit: int = 4,
    ) -> None:
        self.base_weight = base_weight
        self.dense_weight = dense_weight
        self.metadata_weight = metadata_weight
        self.candidate_limit = max(1, candidate_limit)

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        base_scores: Mapping[str, float],
        ranks: Mapping[str, Mapping[str, int]],
    ) -> list[Document]:
        """상위 후보만 재정렬하고 나머지는 기존 순서를 유지한다."""
        if not documents:
            return []

        head = list(documents[: self.candidate_limit])
        tail = list(documents[self.candidate_limit :])
        maximum = max((base_scores.get(_document_id(doc), 0.0) for doc in head), default=1.0)
        maximum = maximum or 1.0

        def score(document: Document) -> tuple[float, float, str]:
            chunk_id = _document_id(document)
            channel_ranks = ranks.get(chunk_id, {})
            dense_rank = channel_ranks.get("dense")
            dense_signal = 1.0 / dense_rank if dense_rank else 0.0
            metadata_similarity = _metadata_similarity(query, document)
            combined = (
                self.base_weight * (base_scores.get(chunk_id, 0.0) / maximum)
                + self.dense_weight * dense_signal
                + self.metadata_weight * metadata_similarity
            )
            document.metadata["reranker_score"] = combined
            document.metadata["reranker_features"] = {
                "dense_reciprocal_rank": dense_signal,
                "metadata_similarity": metadata_similarity,
            }
            return combined, base_scores.get(chunk_id, 0.0), chunk_id

        scored = {id(document): score(document) for document in head}
        head.sort(
            key=lambda document: (
                -scored[id(document)][0],
                -scored[id(document)][1],
                scored[id(document)][2],
            )
        )
        return head + tail
