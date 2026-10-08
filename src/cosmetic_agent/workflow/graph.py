"""
[workflow/graph.py]
AdReviewState 기반의 LangGraph StateGraph 조립 및 컴파일.
"""
from langgraph.graph import StateGraph, START, END
from .state import AdReviewState
from .nodes import (
    parse_input_node,
    rule_check_node,
    judge_claim_node,
    build_query_node,
    retrieve_rules_node,
    organize_evidence_node,
    suggest_copy_node,
    verify_copy_node,
    finalize_node,
)
from .edges import (
    route_evidence_check,
    route_level_decision,
    route_verify_decision,
)
from ..domain.rules import RuleEngine
from ..domain.verifier import CopyVerifier
from ..models.base import BaseJudgeModel
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter


def build_ad_review_graph(
    rule_engine: RuleEngine,
    judge_model: BaseJudgeModel,
    rewriter: QueryRewriter,
    retriever: HybridRetriever,
    verifier: CopyVerifier,
):
    """LangGraph StateGraph를 빌드하고 컴파일하여 반환합니다."""
    builder = StateGraph(AdReviewState)

    # 노드 등록 (클로저 주입)
    builder.add_node("parse_input", parse_input_node)
    builder.add_node("rule_check", lambda s: rule_check_node(s, rule_engine))
    builder.add_node("judge_claim", lambda s: judge_claim_node(s, judge_model))
    builder.add_node("build_query", lambda s: build_query_node(s, rewriter))
    builder.add_node("retrieve_rules", lambda s: retrieve_rules_node(s, retriever))
    builder.add_node("organize_evidence", organize_evidence_node)
    builder.add_node("suggest_copy", suggest_copy_node)
    builder.add_node("verify_copy", lambda s: verify_copy_node(s, verifier, rule_engine))
    builder.add_node("finalize", finalize_node)

    # 엣지 연결
    builder.add_edge(START, "parse_input")
    builder.add_edge("parse_input", "rule_check")
    builder.add_edge("rule_check", "judge_claim")
    builder.add_edge("judge_claim", "build_query")
    builder.add_edge("build_query", "retrieve_rules")

    # 갈림길 1: 근거 충분성
    builder.add_conditional_edges(
        "retrieve_rules",
        route_evidence_check,
        {
            "organize_evidence": "organize_evidence",
            "build_query": "build_query",
            "finalize": "finalize",
        },
    )

    # 갈림길 2: 판정 결과 분기
    builder.add_conditional_edges(
        "organize_evidence",
        route_level_decision,
        {
            "finalize": "finalize",
            "suggest_copy": "suggest_copy",
        },
    )

    # 갈림길 3: 제안 문구 검증 분기
    builder.add_edge("suggest_copy", "verify_copy")
    builder.add_conditional_edges(
        "verify_copy",
        route_verify_decision,
        {
            "finalize": "finalize",
            "suggest_copy": "suggest_copy",
        },
    )

    builder.add_edge("finalize", END)

    return builder.compile()
