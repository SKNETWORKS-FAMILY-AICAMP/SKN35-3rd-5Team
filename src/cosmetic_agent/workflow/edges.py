"""
[workflow/edges.py]
LangGraph 조건부 엣지(갈림길) 라우팅 함수.
"""
from typing import Literal

from .state import AdReviewState

MAX_QUERY_RETRIES = 2
MAX_COPY_RETRIES = 2


def route_evidence_check(state: AdReviewState) -> Literal["organize_evidence", "build_query", "finalize"]:
    """근거 충분성 평가 후 다음 노드를 선택합니다.

    라우터는 상태를 직접 변경하지 않습니다. LangGraph 상태 변경은 노드가
    반환한 업데이트만을 통해 이루어져야 하므로, 재시도 카운터 증가는
    ``graph.py``의 노드 래퍼가 담당합니다.
    """
    if state.get("evidence_ok", False):
        return "organize_evidence"

    retry = state.get("query_retry", 0)
    if retry < MAX_QUERY_RETRIES:
        return "build_query"

    return "finalize"  # 근거 부족 및 재검색 소진 -> 판단보류로 종료


def route_level_decision(state: AdReviewState) -> Literal["suggest_copy", "finalize"]:
    """판정 결과에 따른 제안 분기"""
    level = state.get("level", 0)
    if level == 0:
        return "finalize"  # 가능(0)인 경우 즉시 종료
    return "suggest_copy"   # 조건부(1) 또는 불가(2)는 문구 제안으로 이동


def route_verify_decision(state: AdReviewState) -> Literal["finalize", "suggest_copy"]:
    """제안 문구 검증 후 다음 노드를 선택합니다."""
    if state.get("verify_passed", False):
        return "finalize"

    retry = state.get("copy_retry", 0)
    if retry < MAX_COPY_RETRIES:
        return "suggest_copy"  # 다시 제안

    return "finalize"  # 재제안 횟수 초과 -> 현재 결과로 종료
