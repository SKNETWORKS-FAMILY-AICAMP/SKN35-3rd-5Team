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
    rule_level: NotRequired[int]          # 0: 가능, 1: 조건부, 2: 불가 (제품 근거 포함 규칙 판정)
    model_level: NotRequired[int]         # 0: 가능, 1: 조건부, 2: 불가 (판정 모델)
    level: NotRequired[int]               # = max(rule_level, model_level) 하한 보장
    rule_hits: NotRequired[list[dict[str, Any]]]
    rule_basis_ids: NotRequired[list[str]]
    rule_next_test: NotRequired[str | None]
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
    suggest_note: NotRequired[str]        # 제안 이유 또는 LLM 오류 메시지
    candidates: NotRequired[list[str]]    # 강한 순 제안 후보 (화면의 근거 최대 · 균형 · 가장 안전)
    rejected_notes: NotRequired[list[str]]  # 검증에서 탈락한 후보의 사유 (후보 순서대로)
    used_evidence: NotRequired[list[str]]   # 후보에 사용한 보유 근거
    candidate_details: NotRequired[list[dict[str, Any]]]  # 후보별 검증 결과·변경점·A/B 가설
    experiment: NotRequired[dict[str, Any]]  # A/B 실험 초안 (대조군 = 가장 안전 후보)
    verify_passed: NotRequired[bool]
    verify_note: NotRequired[str]
    copy_retry: NotRequired[int]          # 재제안 카운터 (최대 2)

    # 5. 최종 결과 (finalize)
    status: NotRequired[str]              # "판정" 또는 "판단보류"
    review_notes: NotRequired[str]
