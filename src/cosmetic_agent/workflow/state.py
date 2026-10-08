"""
[workflow/state.py]
LangGraph StateGraph에서 각 노드 간 전달되는 공통 상태(State) 정의.
"""
from typing import Any, NotRequired, TypedDict
from langchain_core.documents import Document


class AdReviewState(TypedDict):
    # 1. 입력 (parse_input)
    copy_text: str
    product: dict[str, Any]
    owned_evidence: list[dict[str, Any]]

    # 2. 판정 (rule_check / judge_claim)
    rule_level: NotRequired[int]          # 0: 가능, 2: 불가 (규칙 사전 매칭)
    model_level: NotRequired[int]         # 0: 가능, 1: 조건부, 2: 불가 (판정 모델)
    level: NotRequired[int]               # = max(rule_level, model_level) 하한 보장
    rule_hits: NotRequired[list[dict[str, Any]]]
    violation_type: NotRequired[str]
    claim_type: NotRequired[str]

    # 3. 검색 (build_query / retrieve_rules / grade_evidence / organize_evidence)
    rewritten_query: NotRequired[str]
    documents: NotRequired[list[Document]]
    evidence_ok: NotRequired[bool]
    citations: NotRequired[dict[str, str]] # {"L1": "LAW_시행규칙_별표5-2가", ...}
    evidence_text: NotRequired[str]
    query_retry: NotRequired[int]         # 재검색 카운터 (최대 2)

    # 4. 제안 및 검증 (suggest_copy / verify_copy)
    suggestion: NotRequired[str]
    next_test: NotRequired[str]
    verify_passed: NotRequired[bool]
    verify_note: NotRequired[str]
    copy_retry: NotRequired[int]          # 재제안 카운터 (최대 2)

    # 5. 최종 결과 (finalize)
    status: NotRequired[str]              # "판정" 또는 "판단보류"
    review_notes: NotRequired[str]
