"""
[workflow/nodes.py]
LangGraph 노드 함수 구현 (9단계).
1. parse_input -> 2. rule_check -> 3. judge_claim -> 4. build_query -> 5. retrieve_rules
-> 6. organize_evidence -> 7. suggest_copy -> 8. verify_copy -> 9. finalize
"""
from typing import Any
from .state import AdReviewState
from ..domain.rules import RuleEngine
from ..domain.verifier import CopyVerifier
from ..models.base import BaseJudgeModel
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter


def parse_input_node(state: AdReviewState) -> dict[str, Any]:
    """1. parse_input: 입력 검증 및 초기화"""
    return {
        "query_retry": 0,
        "copy_retry": 0,
    }


def rule_check_node(state: AdReviewState, rule_engine: RuleEngine) -> dict[str, Any]:
    """2. rule_check: 금지 표현 사전 매칭 (LLM 호출 없음)"""
    category = state["product"].get("category", "일반")
    rule_level, hits = rule_engine.check_banned_terms(state["copy_text"], category)
    return {
        "rule_level": rule_level,
        "rule_hits": hits,
    }


def judge_claim_node(state: AdReviewState, judge_model: BaseJudgeModel) -> dict[str, Any]:
    """3. judge_claim: 판정 모델 실행 및 level = max(rule_level, model_level) 하한 보장"""
    category = state["product"].get("category", "일반")
    fn_type = state["product"].get("functional_type")

    judge_res = judge_model.judge(state["copy_text"], category, fn_type)
    model_level = judge_res.get("model_level", 0)
    rule_level = state.get("rule_level", 0)

    # [핵심 하한 게이트] 규칙이 정한 수준(불가 2) 아래로 모델이 내리지 못하게 강제
    final_level = max(rule_level, model_level)

    return {
        "model_level": model_level,
        "level": final_level,
        "violation_type": judge_res.get("violation_type", "없음"),
        "claim_type": judge_res.get("claim_type", "일반"),
    }


def build_query_node(state: AdReviewState, rewriter: QueryRewriter) -> dict[str, Any]:
    """4. build_query: 규정 검색을 위한 쿼리 재작성"""
    retry = state.get("query_retry", 0)
    q = rewriter.rewrite(state["copy_text"], retry_count=retry)
    return {"rewritten_query": q}


def retrieve_rules_node(state: AdReviewState, retriever: HybridRetriever) -> dict[str, Any]:
    """5. retrieve_rules: Dense + BM25 하이브리드 검색"""
    scope = state["product"].get("category", "공통")
    docs = retriever.retrieve(state.get("rewritten_query", state["copy_text"]), product_scope=scope)
    # 1차 근거 충분성 체크: 문서 수 또는 유사도 기준
    evidence_ok = len(docs) > 0
    return {
        "documents": docs,
        "evidence_ok": evidence_ok,
    }


def organize_evidence_node(state: AdReviewState) -> dict[str, Any]:
    """6. organize_evidence: 검색된 청크에 짧은 ID(L1, L2...) 부여 및 텍스트 정리"""
    docs = state.get("documents", [])
    citations = {f"L{i+1}": doc.metadata.get("id", f"DOC_{i+1}") for i, doc in enumerate(docs)}
    evidence_text = "\n".join([f"[{k}] {doc.page_content}" for k, doc in zip(citations.keys(), docs)])
    return {
        "citations": citations,
        "evidence_text": evidence_text,
    }


def suggest_copy_node(state: AdReviewState) -> dict[str, Any]:
    """7. suggest_copy: 안전한 대체 문구 및 필요 시험 생성"""
    # TODO (팀원 구현 영역): LLM 호출하여 대안 문구 및 next_test 제안
    return {
        "suggestion": state["copy_text"],
        "next_test": "인체적용시험 성적서 필요",
    }


def verify_copy_node(state: AdReviewState, verifier: CopyVerifier, rule_engine: RuleEngine) -> dict[str, Any]:
    """8. verify_copy: 제안 문구의 숫자 날조 및 금지어 재검증"""
    suggestion = state.get("suggestion", "")
    evidences = state["product"].get("owned_evidence", [])
    passed, note = verifier.verify_suggestion(suggestion, evidences, rule_engine)
    return {
        "verify_passed": passed,
        "verify_note": note,
    }


def finalize_node(state: AdReviewState) -> dict[str, Any]:
    """9. finalize: 결과 계약 검사 및 최종 판정/판단보류 확정"""
    evidence_ok = state.get("evidence_ok", False)
    if not evidence_ok:
        return {
            "status": "판단보류",
            "review_notes": "신뢰할 수 있는 법령 근거를 찾지 못하여 RA 전문가 검토가 필요합니다.",
        }
    return {
        "status": "판정",
        "review_notes": "검토 완료",
    }
