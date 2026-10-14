from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from ..domain.copy_knowledge import build_generation_knowledge, material_claim_notes, with_request_form
from ..domain.rules import RuleEngine
from ..domain.schemas import ProductCard
from ..domain.verifier import NUMBER_RE, CopyVerifier
from ..market_reference import ingredient_groups
from ..models.copy_generator import CopyGenerator, grounding_notes
from ..rag.hybrid import HybridRetriever
from ..rag.query_rewriter import QueryRewriter
from .creative import compose_copy, creative_catalog, evidence_note
from .ingredients import ingredient_profiles
from .market import market_references
from .state import AdGenerationState


def concept_claim_notes(text: str, state: AdGenerationState) -> list[str]:
    """요청한 콘셉트를 심사/수치 증명으로 바꾸는 간접 주장도 검사한다."""
    product = state["product"]
    concept = " ".join([state.get("instruction", ""), state.get("product_description", ""), product.get("name", "")])
    notes = []
    sunscreen = bool(re.search(r"선크림|선케어|자외선|SPF|PA\s*\+", concept, re.IGNORECASE))
    approved = product.get("category") == "기능성" and "자외선" in (product.get("functional_type") or "")
    if sunscreen and not approved and re.search(r"피부.{0,10}(?:보호|지켜|지키|방어)|(?:햇살|태양|자외선|UV).{0,12}(?:막아|차단|방어|보호)", text, re.IGNORECASE):
        notes.append("자외선 차단 기능성 확인 없이 피부 보호 효과를 암시합니다. 외출 준비·선케어 루틴 중심으로 재작성하세요.")
    evidence = " ".join(str(v) for item in product.get("owned_evidence", []) for v in item.values() if v)
    for claim in re.findall(r"SPF\s*\d+(?:\+)?|PA\s*\+{1,4}", text, re.IGNORECASE):
        if not approved or re.sub(r"\s+", "", claim).upper() not in re.sub(r"\s+", "", evidence).upper():
            notes.append("확인된 기능성·시험 정보에 없는 SPF/PA 표현입니다. 수치를 제거하세요.")
    return notes


def parse_generation_node(state: AdGenerationState) -> dict[str, Any]:
    return {"query_retry": 0, "generation_retry": 0, "warnings": [],
            "market_references": market_references(state["product"]),
            "ingredient_profiles": ingredient_profiles(state["product"])}


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
            product_description=state.get("product_description", ""),
            reference_copy=state.get("reference_copy", ""),
            retry_note=" / ".join(notes) if notes else None,
            knowledge=build_generation_knowledge(
                with_request_form(state["product"], state["instruction"], state.get("product_description", ""),
                                  " ".join(state.get("keywords") or [])),
                state["channel"],
                tone=state.get("tone", ""),
                market_refs=state.get("market_references", []),
                profiles=state.get("ingredient_profiles", []),
            ),
        )
        return {"drafts": drafts, "generation_error": ""}
    except Exception as error:  # noqa: BLE001 - 자격증명이나 외부 응답 본문은 노출하지 않는다
        return {
            "drafts": [],
            "generation_error": type(error).__name__,
            "rejected_notes": ["광고 문구 생성 모델을 호출하지 못했습니다."],
        }


# 근거는 맞는데 과장 단어 하나 때문에 탈락하는 후보가 많다 (예: 'SPF50+ PA++++로 완벽한 자외선 차단').
# 그런 단어만 빼고 한 번 더 검증해, 가장 강한 근거 후보를 살린다. 뜻을 바꾸는 단어는 건드리지 않는다.
_SOFTEN_RE = re.compile(r"(?:완벽(?:한|하게|히)|확실(?:한|하게|히)|확연(?:한|히)|눈에\s*띄게|놀라운)\s*")
# '걱정 없이'는 지우면 '백탁 매끄럽게'처럼 문장이 깨지므로 보장 뜻이 약한 '부담 없이'로 바꾼다
_WORRY_RE = re.compile(r"걱정\s*(없이|없는)")


def _soften(text: str) -> str:
    text = _WORRY_RE.sub(r"부담 \1", _SOFTEN_RE.sub("", text or ""))
    return re.sub(r"\s{2,}", " ", text).strip()


def _pin_numbers(copy: str, reports: list[dict[str, Any]]) -> str:
    """설명 문구에서 숫자가 든 문장만 실증 원문으로 바꾸고, 장면·성분 문장은 남긴다."""
    # 원문 그대로 (시험 종류·기관은 evidence_note 주석에 따로 붙는다)
    pinned = list(dict.fromkeys(str(e["value"]) for e in reports if e.get("value")))
    sentences = [x for x in re.split(r"(?<=[.!?])\s+|\n+", copy or "") if x.strip()]
    kept = [x for x in sentences if not NUMBER_RE.search(x)]
    return "\n".join(pinned + kept) if pinned else "\n".join(kept)


SHOWN_CANDIDATES = 3


def _pick_diverse(order: list[int], texts: list[str], limit: int) -> list[int]:
    """끌림 순서대로 고르되, 이미 고른 후보와 너무 비슷하면(문자 유사도 0.6 초과) 건너뛴다."""
    from difflib import SequenceMatcher

    chosen: list[int] = []
    for i in order:
        if all(SequenceMatcher(None, texts[i], texts[j]).ratio() <= 0.6 for j in chosen):
            chosen.append(i)
    chosen += [i for i in order if i not in chosen]  # 모자라면 비슷한 것도 뒤에 둔다
    return chosen[:limit] if limit else chosen


def verify_candidates_node(
    state: AdGenerationState,
    verifier: CopyVerifier,
    rule_engine: RuleEngine,
    reviewer=None,
    ranker=None,
) -> dict[str, Any]:
    """1) 값싼 검사(참고 ID·미확인 성분·사실 날조·재료 점검·검증기)를 모든 후보에
    2) 통과한 후보를 끌림 점수로 정렬(ranker)하고 서로 다른 것 위주로
    3) 앞에서부터 판정 엔진 검토(reviewer)를 거쳐 최대 3개를 보여준다."""
    product = state["product"]
    rejected: list[str] = list(state.get("rejected_notes") or []) if not state.get("drafts") else []
    passed_drafts: list[tuple[dict[str, Any], str]] = []
    seen_headlines = set()
    for draft in state.get("drafts", []):
        draft = dict(draft, text=compose_copy(draft))
        creative_ids = {s["reference_id"] for s in creative_catalog()["styles"]}
        if set(draft.get("creative_reference_ids", [])) - creative_ids:
            rejected.append("창작 참고 구조 ID가 제공 자료와 일치하지 않습니다.")
            continue
        evidence_ids = {f"E{i}" for i, _ in enumerate(product.get("owned_evidence", []), start=1)}
        used_ids = draft.get("evidence_reference_ids", [])
        if set(used_ids) - evidence_ids:
            rejected.append("제품 시험 참고 ID가 등록 실증과 일치하지 않습니다.")
            continue
        structured = bool(draft.get("headline") or draft.get("supporting_copy"))
        if structured and NUMBER_RE.search(draft["text"]) and not used_ids:
            rejected.append("수치·기간을 쓴 광고 세트에는 해당 제품 시험 E번호가 필요합니다.")
            continue
        headline_key = "".join(draft.get("headline", "").split())
        examples = {"".join(s["example_headline"].split()) for s in creative_catalog()["styles"]}
        if headline_key and headline_key in examples:
            rejected.append("창작 구조의 예시 문장을 복사했습니다. 이 제품만의 새 헤드라인으로 작성해야 합니다.")
            continue
        if headline_key and headline_key in seen_headlines:
            rejected.append("다른 후보와 같은 헤드라인입니다. 다른 창작 관점으로 작성해야 합니다.")
            continue
        selected_reports = [product["owned_evidence"][int(i[1:]) - 1] for i in used_ids] if used_ids else []
        duration_claims = re.findall(r"\d+(?:\.\d+)?\s*(?:시간|일|주|개월)\s*동안|하루\s*종일|밤\s*사이|아침까지|저녁까지|즉각적", draft["text"]) if structured else []
        report_values = "".join(str(e.get("value") or "") for e in selected_reports)
        if any(re.sub(r"\s+", "", phrase) not in re.sub(r"\s+", "", report_values) for phrase in duration_claims):
            rejected.append("측정 시점을 지속시간·즉각 효과로 넓힐 수 없습니다. 등록된 시험 결과의 시간 표현을 유지해 주세요.")
            continue
        text = draft.get("text", "")
        allowed_ids = {r["reference_id"] for r in state.get("market_references", [])}
        if set(draft.get("market_reference_ids", [])) - allowed_ids:
            rejected.append("시장 참고 사례 ID가 제공된 자료와 일치하지 않습니다.")
            continue
        ingredient_ids = {p["reference_id"] for p in state.get("ingredient_profiles", [])}
        if set(draft.get("ingredient_reference_ids", [])) - ingredient_ids:
            rejected.append("성분 역할 참고 ID가 등록 성분 자료와 일치하지 않습니다.")
            continue
        declared = " ".join([product.get("name", ""), *product.get("key_ingredients", []), *product.get("ingredients", [])])
        extra = ingredient_groups(text) - ingredient_groups(declared)
        if extra:
            rejected.append("우리 제품에서 확인되지 않은 성분 소구: " + ", ".join(sorted(extra)))
            continue
        # 성분·제품명 외에 모델이 새로운 함량/흡수 사실을 만들어내지 않게 한다.
        unsupported = grounding_notes(text, SimpleNamespace(
            product=SimpleNamespace(name=product.get("name", "")), ingredients=product.get("key_ingredients", [])))
        unsupported += concept_claim_notes(text, state)
        unsupported += material_claim_notes(text, product)
        if unsupported:
            rejected.extend(unsupported)
            continue
        if _SOFTEN_RE.search(text):
            softened = {k: _soften(draft.get(k, "")) for k in ("text", "headline", "supporting_copy")}
            ok_soft, _ = verifier.verify_suggestion(
                compose_copy({**draft, **softened}) if structured else softened["text"],
                selected_reports if used_ids else product.get("owned_evidence", []), rule_engine,
                product_category=product.get("category", "일반"), functional_type=product.get("functional_type"))
            if ok_soft:
                draft = {**draft, **softened}
                draft["text"] = compose_copy(draft) if structured else softened["text"]
                text = draft["text"]
        passed, note = verifier.verify_suggestion(
            text,
            selected_reports if used_ids else product.get("owned_evidence", []),
            rule_engine,
            product_category=product.get("category", "일반"),
            functional_type=product.get("functional_type"),
        )
        if passed:
            # 수치 자체가 맞아도 분모·방향을 바꾸어 설명할 수 있으므로,
            # 수치 설명은 선택한 제품 시험의 원문으로 고정한다. (준호)
            if structured and used_ids and NUMBER_RE.search(draft.get("supporting_copy", "")):
                draft["supporting_copy"] = _pin_numbers(draft.get("supporting_copy", ""), selected_reports)
                draft["text"] = compose_copy(draft)
                passed, note = verifier.verify_suggestion(
                    draft["text"], selected_reports, rule_engine,
                    product_category=product.get("category", "일반"),
                    functional_type=product.get("functional_type"),
                )
                if not passed:
                    rejected.append(f"실증 원문 재검증 실패: {note}")
                    continue
            if headline_key:
                seen_headlines.add(headline_key)
            passed_drafts.append((dict(draft, evidence_note=evidence_note(product, used_ids)), note))
        else:
            rejected.append(f"{draft.get('tier', 'candidate')}: {note}")

    texts = [draft.get("text", "") for draft, _ in passed_drafts]
    scores = ranker.score(texts, channel=state.get("channel", ""), tone=state.get("tone", ""),
                          product_name=product.get("name", "")) if ranker is not None else [0.0] * len(texts)
    order = sorted(range(len(texts)), key=lambda i: -scores[i])  # 점수가 같으면 원래 순서(등급 순)
    order = _pick_diverse(order, texts, 0)

    candidates: list[dict[str, Any]] = []
    for i in order:
        if sum(c["status"] == "검토통과" for c in candidates) >= SHOWN_CANDIDATES:
            break
        draft, note = passed_drafts[i]
        text = draft.get("text", "")
        candidate = {**draft, "verified": True, "verify_note": note, "status": "검토통과"}
        if ranker is not None:
            candidate["appeal_score"] = scores[i]
        if reviewer is not None:
            try:
                review = reviewer(text, ProductCard.model_validate(product))
                candidate["review"] = review.model_dump()
                candidate["notes"] = [v for v in (review.result.review_notes, review.result.next_test) if v]
                if review.result.status != "판정" or review.result.level != 0:
                    candidate.update(status="확인필요", verified=False, verify_note="후속 규정 검토에서 확인이 필요합니다.")
                if review.result.level == 2:
                    rejected.append(review.result.review_notes or "후속 검토에서 위반으로 판정되어 재작성합니다.")
                    continue
            except Exception:  # noqa: BLE001 - 검토 실패를 통과로 표시하지 않는다
                candidate.update(status="확인필요", verified=False, verify_note="후속 검토에 실패했습니다.", notes=["모델·검색 연결을 확인하고 다시 검토해주세요."])
        if candidate["status"] != "검토통과":
            rejected.extend(candidate.get("notes") or [candidate["verify_note"]])
        candidates.append(candidate)
    # 검토통과를 앞에, 그다음 확인필요. 화면에는 최대 3개
    candidates.sort(key=lambda c: c["status"] != "검토통과")
    return {"candidates": candidates[:SHOWN_CANDIDATES], "rejected_notes": rejected}


def finalize_generation_node(state: AdGenerationState) -> dict[str, Any]:
    if not state.get("evidence_ok"):
        return {
            "status": "생성보류",
            "candidates": [],
            "warnings": ["광고 문구 생성에 필요한 관련 규정 근거를 찾지 못했습니다."],
        }
    if not any(candidate.get("status", "검토통과") == "검토통과" for candidate in state.get("candidates", [])):
        detail = (
            "광고 문구 생성 모델을 호출하지 못했습니다."
            if state.get("generation_error")
            else "검증을 통과한 광고 문구를 생성하지 못했습니다."
        )
        return {
            "status": "생성보류",
            "candidates": state.get("candidates", []),
            "warnings": list(dict.fromkeys([detail, *state.get("rejected_notes", [])])),
        }
    partial = len(state["candidates"]) < 3 and any(d.get("headline") for d in state.get("drafts", []))
    return {"status": "생성완료", "warnings": ["일부 후보가 검증을 통과하지 못해 통과한 광고 세트만 표시합니다."] if partial else []}
