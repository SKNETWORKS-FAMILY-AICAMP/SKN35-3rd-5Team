"""
[workflow/nodes.py]
LangGraph 노드 함수 구현 (9단계).
1. parse_input -> 2. rule_check -> 3. judge_claim -> 4. build_query -> 5. retrieve_rules
-> 6. organize_evidence -> 7. suggest_copy -> 8. verify_copy -> 9. finalize
"""
from typing import Any

from ..domain.rules import RuleEngine
from ..domain.verifier import CopyVerifier
from ..models.base import BaseJudgeModel
from ..models.copy_suggester import CopySuggester
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter
from .state import AdReviewState


def parse_input_node(state: AdReviewState) -> dict[str, Any]:
    """1. parse_input: 입력 검증 및 초기화"""
    return {
        "query_retry": 0,
        "copy_retry": 0,
    }


def rule_check_node(state: AdReviewState, rule_engine: RuleEngine) -> dict[str, Any]:
    """2. rule_check: 제품 근거를 포함한 규칙 판정 (LLM 호출 없음)"""
    # Numerical contradictions must reach the production floor gate too,
    # rather than only being detected in the standalone rule evaluation.
    report = rule_engine.evaluate(state["copy_text"], state["product"])
    return {
        "rule_level": report["level"],
        "rule_hits": report["hits"],
        "rule_basis_ids": report.get("basis_ids", []),
        "rule_next_test": report.get("next_test"),
    }


def judge_claim_node(state: AdReviewState, judge_model: BaseJudgeModel) -> dict[str, Any]:
    """3. judge_claim: 판정 모델 실행 및 level = max(rule_level, model_level) 하한 보장"""
    judge_res = judge_model.judge_product(state["copy_text"], state["product"])
    model_level = judge_res.get("model_level", 0)
    rule_level = state.get("rule_level", 0)

    # [핵심 하한 게이트] 규칙이 정한 수준(불가 2) 아래로 모델이 내리지 못하게 강제
    final_level = max(rule_level, model_level)

    return {
        "model_level": model_level,
        "level": final_level,
        "violation_type": (
            state["rule_hits"][0]["type"]
            if rule_level > model_level and state.get("rule_hits")
            else judge_res.get("violation_type", "없음")
        ),
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
    try:
        docs = retriever.retrieve(state.get("rewritten_query", state["copy_text"]), product_scope=scope)
    except Exception:  # noqa: BLE001 - 검색이 통째로 실패하면 판단보류로 (응답 자체는 나간다)
        docs = []
    # 1차 근거 충분성 체크: 문서 수 또는 유사도 기준
    evidence_ok = len(docs) > 0
    return {
        "documents": docs,
        "evidence_ok": evidence_ok,
    }


_CHUNKS: dict[str, Any] | None = None


def _chunk_documents(ids: list[str]) -> list[Any]:
    """규칙 근거 ID(예: GUIDE_관리지침_별표1_피부) → 해당 조항 청크(Document). _partN 은 같은 조항으로 본다."""
    global _CHUNKS
    import json
    import re

    from langchain_core.documents import Document

    from ..common.config import PROCESSED_DIR

    if _CHUNKS is None:
        _CHUNKS = {}
        path = PROCESSED_DIR / "chunks.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    _CHUNKS.setdefault(re.sub(r"_part\d+$", "", row["id"]), []).append(row)
    docs = []
    for basis in dict.fromkeys(ids):
        for row in (_CHUNKS.get(basis) or [])[:1]:  # 조항당 첫 조각만 (근거 패널이 같은 조항으로 넘치지 않게)
            docs.append(Document(page_content=row.get("content", ""), metadata=dict(row, chunk_id=row["id"])))
    return docs


def _base_id(doc: Any) -> str:
    import re

    meta = getattr(doc, "metadata", {}) or {}
    return re.sub(r"_part\d+$", "", str(meta.get("chunk_id") or meta.get("id") or ""))


def organize_evidence_node(state: AdReviewState) -> dict[str, Any]:
    """6. organize_evidence: 판정 근거 조항을 앞에 두고 검색 청크를 붙인 뒤 짧은 ID(L1, L2...) 부여

    판정은 규칙(rule_hits)이 정하므로, 그 규칙이 가리키는 조항이 인용에서 빠지면 안 된다.
    검색 결과는 같은 조항을 빼고 뒤에 붙이며, 사례(보도자료, authority 4)는 조항보다 뒤로 보낸다."""
    rule_docs = _chunk_documents(state.get("rule_basis_ids") or []) if state.get("level", 0) >= 1 else []
    seen = {_base_id(d) for d in rule_docs}
    retrieved = [d for d in state.get("documents", []) if _base_id(d) not in seen]
    retrieved.sort(key=lambda d: int((d.metadata or {}).get("authority", 4) or 4) >= 4)
    docs = (rule_docs + retrieved)[:max(4, len(rule_docs))]
    citations = {f"L{i+1}": doc.metadata.get("id", f"DOC_{i+1}") for i, doc in enumerate(docs)}
    evidence_text = "\n".join([f"[{k}] {doc.page_content}" for k, doc in zip(citations.keys(), docs)])
    return {
        "documents": docs,
        "citations": citations,
        "evidence_text": evidence_text,
    }


_default_suggester: CopySuggester | None = None


def suggest_copy_node(state: AdReviewState, suggester: CopySuggester | None = None) -> dict[str, Any]:
    """7. suggest_copy: 안전한 대체 문구 및 필요 시험 생성"""
    global _default_suggester
    if suggester is None:
        _default_suggester = _default_suggester or CopySuggester()
        suggester = _default_suggester

    result = suggester.suggest(
        copy_text=state["copy_text"],
        product=state["product"],
        owned_evidence=state["product"].get("owned_evidence", []),
        level=state.get("level"),
        violation_type=state.get("violation_type"),
        evidence_text=state.get("evidence_text", ""),
        # 재제안일 때만 이전 제안과 검증 탈락 사유를 함께 넘긴다.
        previous_suggestion=state.get("suggestion"),
        verify_note=None if state.get("verify_passed", True) else state.get("verify_note"),
    )
    return {
        "suggestion": result.get("suggestion") or "",
        "next_test": result.get("next_test") or (state.get("rule_next_test") if state.get("level") == 1 else None),
        "suggest_note": result.get("suggest_error") or result.get("suggest_rationale", ""),
        "candidates": result.get("candidates", []),
        "rejected_notes": result.get("rejected_notes", []),
        "used_evidence": result.get("used_evidence", []),
        "candidate_details": result.get("candidate_details", []),
        "experiment": result.get("experiment", {}),
    }


def verify_copy_node(state: AdReviewState, verifier: CopyVerifier, rule_engine: RuleEngine) -> dict[str, Any]:
    """8. verify_copy: 제안 문구의 숫자 날조 및 금지어 재검증"""
    suggestion = state.get("suggestion", "")
    product = state["product"]
    passed, note = verifier.verify_suggestion(
        suggestion,
        product.get("owned_evidence", []),
        rule_engine,
        product_category=product.get("category", "일반"),
        functional_type=product.get("functional_type"),
        # 조건부·불가 문구는 반드시 고쳐야 하므로 원문 그대로의 제안은 탈락시킨다.
        original=state["copy_text"] if state.get("level", 0) >= 1 else None,
    )
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
        "review_notes": _review_notes(state),
    }


def _readable_basis(basis_id: str) -> str:
    """'LAW_시행규칙_별표5-2사' → '화장품법 시행규칙 별표5-2사' 처럼 사람이 읽는 이름 (청크의 출처·조문)."""
    _chunk_documents([])  # 청크 사전 로드
    rows = (_CHUNKS or {}).get(basis_id) or []
    if rows and rows[0].get("source"):
        article = rows[0].get("article") or basis_id.rsplit("_", 1)[-1]
        return f"{rows[0]['source']} {article}".strip()
    return basis_id


def _review_notes(state: AdReviewState) -> str:
    """판정 이유를 '표현 → 위반 유형 · 근거 조항' 으로 적는다. 근거 조항은 인용 목록(L번호)과 같은 ID다."""
    level = state.get("level", 0)
    hits = [h for h in (state.get("rule_hits") or []) if h.get("level", 0) >= 1]
    if level == 0 or not hits:
        return "규칙 검사에서 걸리는 표현이 없습니다. 아래 조항은 참고용 검색 결과입니다." if level == 0 else "검토 완료"
    lines = []
    for hit in hits[:3]:
        ids = list(dict.fromkeys(b for b in (hit.get("law_id"), hit.get("basis_id")) if b))
        basis = " · ".join(_readable_basis(b) for b in ids)
        lines.append(f"'{hit.get('matched') or hit.get('term')}' → {hit.get('type', '위반')} ({basis})")
    if level == 1 and (state.get("next_test") or state.get("rule_next_test")):
        lines.append("필요 자료: " + (state.get("next_test") or state.get("rule_next_test")))
    return "\n".join(lines)
