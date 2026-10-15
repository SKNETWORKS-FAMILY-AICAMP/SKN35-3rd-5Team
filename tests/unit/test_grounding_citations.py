"""검토 근거: 판정을 만든 규칙의 조항이 인용 맨 앞에 오고, 설명이 그 조항을 가리키며, 검색 장애에도 응답한다."""
from langchain_core.documents import Document

from cosmetic_agent.rag.hybrid import HybridRetriever
from cosmetic_agent.workflow.nodes import _review_notes, organize_evidence_node


def test_rule_basis_is_cited_first_and_not_duplicated():
    retrieved = [Document(page_content="사례", metadata={"id": "CASE_2025-08-06_피부재생_염증완화", "authority": 4}),
                 Document(page_content="별표1 질병", metadata={"id": "GUIDE_관리지침_별표1_질병", "authority": 3})]
    out = organize_evidence_node({"level": 2, "rule_basis_ids": ["GUIDE_관리지침_별표1_질병"], "documents": retrieved})
    ids = [d.metadata.get("chunk_id") or d.metadata.get("id") for d in out["documents"]]
    assert ids[0].startswith("GUIDE_관리지침_별표1_질병")
    assert sum(i.startswith("GUIDE_관리지침_별표1_질병") for i in ids) == 1  # 같은 조항 중복 없음
    assert ids[-1].startswith("CASE_")  # 사례는 조항보다 뒤
    assert out["evidence_text"].startswith("[L1]")


def test_review_notes_name_the_expression_and_provision():
    notes = _review_notes({"level": 1, "rule_hits": [{"level": 1, "matched": "8주", "type": "실증필요",
                                                     "law_id": "LAW_시행규칙_별표5-2아"}],
                           "rule_next_test": "인체적용시험 결과 보고서"})
    assert "'8주'" in notes and "시행규칙" in notes and "필요 자료" in notes
    assert "걸리는 표현이 없습니다" in _review_notes({"level": 0, "rule_hits": []})


def test_dense_outage_falls_back_to_bm25():
    class Down:
        def search_dense(self, *args, **kwargs):
            raise ConnectionError("qdrant down")

    class Sparse:
        def search_sparse(self, *args, **kwargs):
            return [Document(page_content="실증규정", metadata={"id": "NOTICE_실증규정_제3조", "authority": 2})]

    docs = HybridRetriever(dense_retriever=Down(), sparse_retriever=Sparse()).retrieve("4주 후 보습력 42%")
    assert [d.metadata["id"] for d in docs][:1] == ["NOTICE_실증규정_제3조"]
