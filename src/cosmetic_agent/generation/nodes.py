from __future__ import annotations

from typing import Any

from ..domain.rules import RuleEngine
from ..domain.verifier import CopyVerifier
from ..models.copy_generator import CopyGenerator
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter
from .state import AdGenerationState


def parse_generation_node(state: AdGenerationState) -> dict[str, Any]:
    return {"query_retry": 0, "generation_retry": 0, "warnings": []}


def build_generation_query_node(
    state: AdGenerationState, rewriter: QueryRewriter
) -> dict[str, Any]:
    product = state["product"]
    evidence_terms = " ".join(
        str(evidence.get("item") or "") for evidence in product.get("owned_evidence", [])
    )
    base = " ".join(filter(None, [
        product.get("category"),
        product.get("functional_type"),
        evidence_terms,
        state["instruction"],
        "화장품 표시 광고 허용 범위 실증자료",
    ]))
    return {"rewritten_query": rewriter.rewrite(base, state.get("query_retry", 0))}


def retrieve_generation_rules_node(
    state: AdGenerationState, retriever: HybridRetriever
) -> dict[str, Any]:
    documents = retriever.retrieve(
        state["rewritten_query"],
        top_k=6,
        product_scope=state["product"].get("category", "공통"),
        min_statute_count=2,
    )
    return {"documents": documents, "evidence_ok": bool(documents)}


def organize_generation_evidence_node(state: AdGenerationState) -> dict[str, Any]:
    rows = [
        f"[L{index}] {document.page_content}"
        for index, document in enumerate(state.get("documents", []), start=1)
    ]
    return {"evidence_text": "\n".join(rows)}


def generate_candidates_node(
    state: AdGenerationState, generator: CopyGenerator
) -> dict[str, Any]:
    notes = state.get("rejected_notes") or []
    try:
        drafts = generator.generate(
            instruction=state["instruction"],
            product=state["product"],
            channel=state["channel"],
            tone=state["tone"],
            length=state["length"],
            keywords=state["keywords"],
            evidence_text=state.get("evidence_text", ""),
            retry_note=" / ".join(notes) if notes else None,
        )
        return {"drafts": drafts, "generation_error": ""}
    except Exception as error:  # noqa: BLE001 - 자격증명이나 외부 응답 본문은 노출하지 않는다
        return {
            "drafts": [],
            "generation_error": type(error).__name__,
            "rejected_notes": ["광고 문구 생성 모델을 호출하지 못했습니다."],
        }


def verify_candidates_node(
    state: AdGenerationState,
    verifier: CopyVerifier,
    rule_engine: RuleEngine,
) -> dict[str, Any]:
    product = state["product"]
    candidates: list[dict[str, Any]] = []
    rejected: list[str] = list(state.get("rejected_notes") or []) if not state.get("drafts") else []
    for draft in state.get("drafts", []):
        passed, note = verifier.verify_suggestion(
            draft.get("text", ""),
            product.get("owned_evidence", []),
            rule_engine,
            product_category=product.get("category", "일반"),
            functional_type=product.get("functional_type"),
        )
        if passed:
            candidates.append({**draft, "verified": True, "verify_note": note})
        else:
            rejected.append(f"{draft.get('tier', 'candidate')}: {note}")
    return {"candidates": candidates, "rejected_notes": rejected}


def finalize_generation_node(state: AdGenerationState) -> dict[str, Any]:
    if not state.get("evidence_ok"):
        return {
            "status": "생성보류",
            "candidates": [],
            "warnings": ["광고 문구 생성에 필요한 관련 규정 근거를 찾지 못했습니다."],
        }
    if not state.get("candidates"):
        detail = (
            "광고 문구 생성 모델을 호출하지 못했습니다."
            if state.get("generation_error")
            else "검증을 통과한 광고 문구를 생성하지 못했습니다."
        )
        return {
            "status": "생성보류",
            "candidates": [],
            "warnings": [detail],
        }
    return {"status": "생성완료", "warnings": []}
