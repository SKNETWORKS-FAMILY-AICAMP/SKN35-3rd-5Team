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


def doc(chunk_id, authority):
    return Document(
        page_content=chunk_id,
        metadata={"chunk_id": chunk_id, "authority": authority},
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


def test_query_rewriter_adds_regulatory_vocabulary():
    rewritten = QueryRewriter().rewrite("피부 세포를 완벽하게 재생시킵니다")

    assert "의약품으로 잘못 인식" in rewritten
    assert "소비자 오인" in rewritten


def test_query_rewriter_maps_general_hair_growth_claims():
    rewritten = QueryRewriter().rewrite("모발이 빠르게 자라도록 돕습니다")

    assert "의약품으로 잘못 인식" in rewritten
