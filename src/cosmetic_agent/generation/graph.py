from langgraph.graph import END, START, StateGraph

from ..domain.rules import RuleEngine
from ..domain.verifier import CopyVerifier
from ..models.copy_generator import CopyGenerator
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter
from .nodes import (
    build_generation_query_node,
    finalize_generation_node,
    generate_candidates_node,
    organize_generation_evidence_node,
    parse_generation_node,
    retrieve_generation_rules_node,
    verify_candidates_node,
)
from .state import AdGenerationState

MAX_QUERY_RETRIES = 2
MAX_GENERATION_RETRIES = 2


def build_generation_graph(
    *,
    rule_engine: RuleEngine,
    rewriter: QueryRewriter,
    retriever: HybridRetriever,
    verifier: CopyVerifier,
    generator: CopyGenerator,
    reviewer=None,
):
    builder = StateGraph(AdGenerationState)

    def build_query(state: AdGenerationState):
        retry = state.get("query_retry", 0) + (1 if state.get("rewritten_query") else 0)
        return {
            **build_generation_query_node({**state, "query_retry": retry}, rewriter),
            "query_retry": retry,
        }

    def generate(state: AdGenerationState):
        retry = state.get("generation_retry", 0) + (1 if state.get("drafts") else 0)
        return {
            **generate_candidates_node({**state, "generation_retry": retry}, generator),
            "generation_retry": retry,
        }

    def route_evidence(state: AdGenerationState) -> str:
        if state.get("evidence_ok"):
            return "organize_generation_evidence"
        return "build_generation_query" if state.get("query_retry", 0) < MAX_QUERY_RETRIES else "finalize_generation"

    def route_verification(state: AdGenerationState) -> str:
        if state.get("generation_error"):
            return "finalize_generation"
        if any(candidate.get("status", "검토통과") == "검토통과" for candidate in state.get("candidates", [])):
            return "finalize_generation"
        return "generate_candidates" if state.get("generation_retry", 0) < MAX_GENERATION_RETRIES else "finalize_generation"

    builder.add_node("parse_generation", parse_generation_node)
    builder.add_node("build_generation_query", build_query)
    builder.add_node("retrieve_generation_rules", lambda s: retrieve_generation_rules_node(s, retriever))
    builder.add_node("organize_generation_evidence", organize_generation_evidence_node)
    builder.add_node("generate_candidates", generate)
    builder.add_node("verify_candidates", lambda s: verify_candidates_node(s, verifier, rule_engine, reviewer))
    builder.add_node("finalize_generation", finalize_generation_node)

    builder.add_edge(START, "parse_generation")
    builder.add_edge("parse_generation", "build_generation_query")
    builder.add_edge("build_generation_query", "retrieve_generation_rules")
    builder.add_conditional_edges("retrieve_generation_rules", route_evidence)
    builder.add_edge("organize_generation_evidence", "generate_candidates")
    builder.add_edge("generate_candidates", "verify_candidates")
    builder.add_conditional_edges("verify_candidates", route_verification)
    builder.add_edge("finalize_generation", END)
    return builder.compile()
