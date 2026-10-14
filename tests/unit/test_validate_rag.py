from scripts.validate_rag import CaseResult, classify_failure, retrieval_metrics


def make_result(rank: int | None) -> CaseResult:
    return CaseResult(
        id="case",
        copy_text="copy",
        rewritten_query="query",
        target_id="target",
        related_citations=[],
        dense_ids=[],
        sparse_ids=[],
        hybrid_ids=[],
        dense_rank=rank,
        sparse_rank=rank,
        hybrid_rank=rank,
        hit_at_k=rank is not None and rank <= 4,
        failure_type=None,
    )


def test_retrieval_metrics_calculates_hit_at_k_and_mrr():
    metrics = retrieval_metrics(
        [make_result(1), make_result(4), make_result(None)], "hybrid", 4
    )

    assert metrics["hit_at_1"] == 0.3333
    assert metrics["hit_at_4"] == 0.6667
    assert metrics["mrr"] == 0.4167


def test_retrieval_metrics_counts_related_evidence_coverage():
    result = make_result(None)
    result.related_citations = ["GUIDE_related"]
    result.hybrid_ids = ["GUIDE_related"]

    metrics = retrieval_metrics([result], "hybrid", 4)

    assert metrics["hit_at_4"] == 0.0
    assert metrics["evidence_coverage_at_4"] == 1.0


def test_classify_failure_distinguishes_related_citation():
    failure = classify_failure(
        target_id="LAW_target",
        related_citations=["GUIDE_related"],
        dense_ids=["GUIDE_related"],
        sparse_ids=[],
        hybrid_ids=["GUIDE_related"],
        indexed_ids={"LAW_target", "GUIDE_related"},
        top_k=4,
    )

    assert failure == "related_citation_only"


def test_classify_failure_reports_index_missing_first():
    failure = classify_failure(
        target_id="LAW_missing",
        related_citations=[],
        dense_ids=[],
        sparse_ids=[],
        hybrid_ids=[],
        indexed_ids={"LAW_other"},
        top_k=4,
    )

    assert failure == "index_missing"
