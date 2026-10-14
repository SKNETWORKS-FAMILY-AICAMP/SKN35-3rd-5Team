from langchain_core.documents import Document

from cosmetic_agent.rag.reranker import LightweightReranker


def _doc(chunk_id, categories=(), keywords=()):
    return Document(
        page_content="원문",
        metadata={
            "chunk_id": chunk_id,
            "claim_categories": list(categories),
            "search_keywords": list(keywords),
        },
    )


def test_reranker_promotes_metadata_relevant_candidate():
    generic = _doc("GUIDE_일반", ["일반 표시·광고"], ["준수사항"])
    relevant = _doc("GUIDE_질병", ["의약품 오인"], ["질병 효능", "치료 예방 표현"])
    reranker = LightweightReranker(
        base_weight=0.2,
        dense_weight=0.0,
        metadata_weight=0.8,
    )

    results = reranker.rerank(
        "질병 효능을 표시한 광고",
        [generic, relevant],
        {"GUIDE_일반": 1.0, "GUIDE_질병": 0.9},
        {"GUIDE_일반": {}, "GUIDE_질병": {}},
    )

    assert results[0].metadata["chunk_id"] == "GUIDE_질병"
    assert "reranker_score" in results[0].metadata
    assert "metadata_similarity" in results[0].metadata["reranker_features"]


def test_reranker_keeps_candidates_after_limit_in_original_order():
    documents = [_doc(f"DOC_{index}") for index in range(4)]
    reranker = LightweightReranker(candidate_limit=2)

    results = reranker.rerank(
        "질문",
        documents,
        {f"DOC_{index}": 1 / (index + 1) for index in range(4)},
        {f"DOC_{index}": {} for index in range(4)},
    )

    assert [doc.metadata["chunk_id"] for doc in results[2:]] == ["DOC_2", "DOC_3"]


def test_default_reranker_never_changes_top_four_membership():
    documents = [_doc(f"DOC_{index}", keywords=("질병 효능",) if index == 4 else ()) for index in range(6)]
    reranker = LightweightReranker()

    results = reranker.rerank(
        "질병 효능",
        documents,
        {f"DOC_{index}": 1 / (index + 1) for index in range(6)},
        {f"DOC_{index}": {"dense": index + 1} for index in range(6)},
    )

    assert {doc.metadata["chunk_id"] for doc in results[:4]} == {
        "DOC_0", "DOC_1", "DOC_2", "DOC_3"
    }
