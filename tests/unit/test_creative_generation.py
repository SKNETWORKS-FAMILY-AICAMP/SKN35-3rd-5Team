from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.verifier import CopyVerifier
from cosmetic_agent.generation.nodes import verify_candidates_node
from cosmetic_agent.models.generation_prompts import build_generation_prompt

PRODUCT = {"name": "수분 토너", "category": "일반", "key_ingredients": ["히알루론산"], "owned_evidence": []}


def verify(drafts, product=None):
    return verify_candidates_node({"product": product or PRODUCT, "drafts": drafts}, CopyVerifier(), RuleEngine())


def test_creative_bank_is_structure_not_brand_proof():
    prompt = build_generation_prompt(instruction="창의적으로", product=PRODUCT, channel="SNS", tone="간결한", length="한 줄", keywords=[], evidence_text="[L1] 규정")
    assert "감각적 비유" in prompt and "상황과 실증" in prompt
    assert "브랜드 원문·효능·숫자 복사 금지" in prompt


def test_headline_is_reconstructed_and_checked_not_hidden_behind_safe_text():
    result = verify([{"text": "촉촉하게 가꾸는 토너", "headline": "피부염 치료의 시작", "supporting_copy": "매일의 루틴", "tier": "strong"}])
    assert result["candidates"] == []


def test_foreign_numbers_and_missing_reference_ids_are_rejected():
    drafts = [
        {"text": "a", "headline": "한 겹의 여유", "supporting_copy": "보습력 105% 개선", "tier": "strong"},
        {"text": "a", "headline": "한 겹의 여유", "supporting_copy": "매일의 루틴", "creative_reference_ids": ["C99"], "tier": "safe"},
        {"text": "a", "headline": "한 겹의 여유", "supporting_copy": "매일의 루틴", "evidence_reference_ids": ["E9"], "tier": "safe"},
    ]
    result = verify(drafts)
    assert result["candidates"] == [] and len(result["rejected_notes"]) == 3


def test_notes_are_assembled_from_selected_product_report_and_sources():
    evidence = {"test_type": "인체적용시험", "item": "보습", "value": "보습력 42% 개선", "conditions": "성인 여성 31명, 무도포 부위 대비", "source_kind": "public_brand_summary", "source_url": "https://example.com/report", "report_available": False}
    product = dict(PRODUCT, owned_evidence=[evidence])
    result = verify([{"text": "무시되는 text", "headline": "하루의 끝, 수분의 시작", "supporting_copy": "히알루론산 함유 토너", "tier": "safe", "evidence_reference_ids": ["E1"], "creative_reference_ids": ["C1"], "evidence_note": "다른 시험기관에서 81% 개선"}], product)
    candidate = result["candidates"][0]
    assert candidate["text"] == "하루의 끝, 수분의 시작\n히알루론산 함유 토너"
    assert evidence["conditions"] in candidate["evidence_note"]
    assert "원보고서 미확보" in candidate["evidence_note"]
    assert "81%" not in candidate["evidence_note"]


def test_unselected_reports_cannot_justify_a_number_and_headlines_differ():
    product = dict(PRODUCT, owned_evidence=[
        {"test_type": "인체적용시험", "item": "보습", "value": "보습력 42% 개선"},
        {"test_type": "인체적용시험", "item": "보습", "value": "보습력 12% 개선"},
    ])
    numeric = verify([{"text": "a", "headline": "보습의 시간", "supporting_copy": "보습력 12% 개선", "tier": "strong", "evidence_reference_ids": ["E1"]}], product)
    assert numeric["candidates"] == []
    duplicate = {"text": "a", "headline": "하루의 끝, 수분의 시작", "supporting_copy": "히알루론산 함유 토너", "tier": "safe"}
    result = verify([duplicate, dict(duplicate, tier="balanced")])
    assert len(result["candidates"]) == 1


def test_creative_examples_and_timepoint_to_duration_transfer_are_blocked():
    copied = verify([{"text": "a", "headline": "하루의 끝, 피부를 위한 쉼표", "supporting_copy": "매일의 루틴", "tier": "safe"}])
    assert copied["candidates"] == []
    product = dict(PRODUCT, owned_evidence=[{"test_type": "인체적용시험", "item": "보습", "value": "72시간 후 수분 유지력 23.5% (무도포 부위 대비)"}])
    result = verify([{"text": "a", "headline": "수분의 시간", "supporting_copy": "72시간 동안 수분을 지켜줍니다", "tier": "strong", "evidence_reference_ids": ["E1"]}], product)
    assert result["candidates"] == []


def test_partial_creative_sets_retry_with_rejection_feedback():
    from langchain_core.documents import Document

    from cosmetic_agent.generation.graph import build_generation_graph
    from cosmetic_agent.rag.query_rewriter import QueryRewriter

    class Retriever:
        def retrieve(self, *args, **kwargs):
            return [Document(page_content="제품 자료와 광고 표현을 대조한다.", metadata={"authority": 1})]

    class Generator:
        calls = 0
        feedback = None

        def generate(self, **kwargs):
            self.calls += 1
            self.feedback = kwargs.get("retry_note")
            return [{"text": "a", "headline": headline, "supporting_copy": body, "tier": tier}
                    for tier, headline, body in zip(
                        ["strong", "balanced", "safe"],
                        ["나를 챙기는 순간", "오늘의 루틴", "일상의 작은 한 단계"],
                        ["보습력 105% 개선", "하루 종일 유지", "매일의 케어"]
                        if self.calls == 1 else ["매일의 케어"] * 3)]

    generator = Generator()
    graph = build_generation_graph(rule_engine=RuleEngine(), rewriter=QueryRewriter(),
                                   retriever=Retriever(), verifier=CopyVerifier(), generator=generator)
    result = graph.invoke({"product": PRODUCT, "instruction": "다른 관점으로", "channel": "SNS",
                           "tone": "간결한", "length": "한 줄", "keywords": []})
    assert generator.calls == 2 and generator.feedback
    assert len(result["candidates"]) == 3


def test_numeric_support_keeps_original_metric_and_comparator():
    value = "도포 72시간 후 수분 유지력 23.5% (무도포 부위 대비)"
    product = dict(PRODUCT, owned_evidence=[{"test_type": "인체적용시험", "item": "보습", "value": value}])
    result = verify([{"text": "a", "headline": "수분의 시간을 기록하다", "supporting_copy": "72시간 후에도 수분 23.5%를 유지", "tier": "strong", "evidence_reference_ids": ["E1"]}], product)
    assert result["candidates"][0]["supporting_copy"] == value
