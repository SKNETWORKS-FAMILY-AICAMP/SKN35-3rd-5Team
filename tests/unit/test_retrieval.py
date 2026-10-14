from langchain_core.documents import Document

from cosmetic_agent.rag.hybrid import HybridRetriever
from cosmetic_agent.rag.query_rewriter import QueryRewriter
from cosmetic_agent.rag.sparse_bm25 import SparseBM25Retriever


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents

    def search_dense(self, query, top_k, product_scope):
        return self.documents[:top_k]

    def search_sparse(self, query, top_k, product_scope="공통"):
        return self.documents[:top_k]


def doc(chunk_id, authority, source=None):
    return Document(
        page_content=chunk_id,
        metadata={"chunk_id": chunk_id, "authority": authority, "source": source or chunk_id},
    )


def test_sparse_search_returns_chunk_ids():
    retriever = SparseBM25Retriever("data/02_processed/bm25_index.pkl")
    results = retriever.search_sparse("화장품 표시 광고", top_k=3)

    assert len(results) == 3
    assert all(result.metadata["chunk_id"] for result in results)
    assert all("sparse_score" in result.metadata for result in results)


def test_hybrid_rrf_deduplicates_and_guarantees_statutes():
    dense = FakeRetriever([doc("GUIDE_A", 3), doc("LAW_A", 1), doc("CASE_A", 4)])
    sparse = FakeRetriever([doc("GUIDE_A", 3), doc("NOTICE_A", 2), doc("LAW_A", 1)])
    retriever = HybridRetriever(dense, sparse, rrf_k=60, candidate_k=10)

    results = retriever.retrieve("질문", top_k=3, min_statute_count=2)
    ids = [result.metadata["chunk_id"] for result in results]

    assert len(ids) == len(set(ids)) == 3
    assert sum(result.metadata["authority"] <= 2 for result in results) >= 2
    assert all("rrf_score" in result.metadata for result in results)


def test_hybrid_preserves_relevance_order_when_statute_is_already_present():
    dense = FakeRetriever([doc("GUIDE_A", 3), doc("LAW_A", 1), doc("CASE_A", 4)])
    sparse = FakeRetriever([doc("GUIDE_A", 3), doc("LAW_A", 1), doc("CASE_A", 4)])
    retriever = HybridRetriever(dense, sparse, candidate_k=10)

    results = retriever.retrieve("질문", top_k=3, min_statute_count=1)

    assert [result.metadata["chunk_id"] for result in results] == [
        "GUIDE_A",
        "LAW_A",
        "CASE_A",
    ]


def test_hybrid_adds_missing_statute_at_tail_instead_of_first_place():
    dense = FakeRetriever([doc("GUIDE_A", 3), doc("CASE_A", 4), doc("LAW_A", 1)])
    sparse = FakeRetriever([doc("GUIDE_A", 3), doc("CASE_A", 4), doc("LAW_A", 1)])
    retriever = HybridRetriever(dense, sparse, candidate_k=10)

    results = retriever.retrieve("질문", top_k=2, min_statute_count=1)
    ids = [result.metadata["chunk_id"] for result in results]

    assert ids == ["GUIDE_A", "LAW_A"]


def test_hybrid_metadata_match_uses_chunk_label_without_answer_dictionary():
    dense = FakeRetriever([doc("GUIDE_관리지침_별표1_피부", 3), doc("GUIDE_관리지침_별표1_모발", 3)])
    sparse = FakeRetriever([doc("GUIDE_관리지침_별표1_모발", 3), doc("GUIDE_관리지침_별표1_피부", 3)])
    retriever = HybridRetriever(
        dense,
        sparse,
        dense_weight=0.0,
        sparse_weight=0.0,
        metadata_match_weight=0.02,
        dense_rescue_rank=0,
    )

    results = retriever.retrieve("모발에 관한 일반 광고", top_k=2, min_statute_count=0)

    assert results[0].metadata["chunk_id"] == "GUIDE_관리지침_별표1_모발"


def test_hybrid_preserves_top_dense_candidate_from_sparse_demotion():
    dense = FakeRetriever([doc("GUIDE_DENSE", 3), doc("GUIDE_OTHER", 3)])
    sparse = FakeRetriever([doc("GUIDE_A", 3), doc("GUIDE_B", 3), doc("GUIDE_C", 3)])
    retriever = HybridRetriever(
        dense,
        sparse,
        dense_weight=0.0,
        sparse_weight=1.0,
        metadata_match_weight=0.0,
        dense_rescue_rank=1,
    )

    results = retriever.retrieve("질문", top_k=2, min_statute_count=0)

    assert "GUIDE_DENSE" in [result.metadata["chunk_id"] for result in results]


def test_hybrid_final_k_reproduces_service_selection_and_keeps_candidates():
    dense = FakeRetriever([doc("GUIDE_DENSE", 3), doc("GUIDE_OTHER", 3)])
    sparse = FakeRetriever([
        doc("GUIDE_A", 3), doc("GUIDE_B", 3), doc("GUIDE_C", 3), doc("LAW_D", 1)
    ])
    retriever = HybridRetriever(
        dense,
        sparse,
        dense_weight=0.0,
        sparse_weight=1.0,
        metadata_match_weight=0.0,
        dense_rescue_rank=1,
    )

    results = retriever.retrieve("질문", top_k=5, final_k=2, min_statute_count=0)
    ids = [result.metadata["chunk_id"] for result in results]

    assert len(ids) == 5
    assert "GUIDE_DENSE" in ids[:2]
    assert len(ids) == len(set(ids))


def test_hybrid_default_preserves_top_two_dense_candidates():
    dense = FakeRetriever([doc("GUIDE_DENSE_1", 3), doc("GUIDE_DENSE_2", 3)])
    sparse = FakeRetriever([
        doc("GUIDE_A", 3), doc("GUIDE_B", 3), doc("GUIDE_C", 3), doc("LAW_D", 1)
    ])
    retriever = HybridRetriever(
        dense,
        sparse,
        dense_weight=0.0,
        sparse_weight=1.0,
        metadata_match_weight=0.0,
    )

    results = retriever.retrieve("질문", top_k=4, min_statute_count=0)
    ids = [result.metadata["chunk_id"] for result in results]

    assert {"GUIDE_DENSE_1", "GUIDE_DENSE_2"}.issubset(ids)


def test_hybrid_limits_repeated_chunks_from_same_source():
    dense = FakeRetriever([
        doc("NOTICE_A", 2, "실증규정"),
        doc("NOTICE_B", 2, "실증규정"),
        doc("NOTICE_C", 2, "실증규정"),
        doc("GUIDE_A", 3, "관리지침"),
    ])
    sparse = FakeRetriever(dense.documents)
    retriever = HybridRetriever(dense, sparse, dense_rescue_rank=0, max_per_source=2)

    results = retriever.retrieve("질문", top_k=3, min_statute_count=0)

    assert [result.metadata["source"] for result in results].count("실증규정") == 2
    assert any(result.metadata["chunk_id"] == "GUIDE_A" for result in results)


def test_query_rewriter_adds_regulatory_vocabulary():
    rewritten = QueryRewriter().rewrite("피부 세포를 완벽하게 재생시킵니다")

    assert "의약품으로 잘못 인식" in rewritten
    assert "소비자 오인" in rewritten


def test_query_rewriter_maps_general_hair_growth_claims():
    rewritten = QueryRewriter().rewrite("모발이 빠르게 자라도록 돕습니다")

    assert "의약품으로 잘못 인식" in rewritten
