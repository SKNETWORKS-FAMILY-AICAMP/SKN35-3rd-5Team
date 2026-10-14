from langchain_core.documents import Document

from cosmetic_agent.domain.rules import RuleEngine
from cosmetic_agent.domain.verifier import CopyVerifier
from cosmetic_agent.generation.graph import build_generation_graph
from cosmetic_agent.rag.query_rewriter import QueryRewriter


class FakeRetriever:
    def retrieve(self, query, top_k=6, product_scope="공통", min_statute_count=2):
        return [Document(
            page_content="화장품은 기능성화장품 심사 범위 안에서 표시ㆍ광고해야 한다.",
            metadata={
                "chunk_id": "LAW_시행규칙_별표5-2나",
                "source": "화장품법 시행규칙",
                "article": "별표5-2나",
                "authority": 1,
            },
        )]


class FakeGenerator:
    def generate(self, **kwargs):
        return [
            {
                "text": "매일 탄탄하게 가꾸는 타임리스 펩타이드 세럼",
                "tier": "safe",
                "rationale": "기능성 범위를 넘지 않는 관리 표현",
                "used_evidence": [],
                "cited_ids": ["L1"],
            }
        ]


def test_generation_graph_returns_only_verified_candidates():
    graph = build_generation_graph(
        rule_engine=RuleEngine(),
        rewriter=QueryRewriter(),
        retriever=FakeRetriever(),
        verifier=CopyVerifier(),
        generator=FakeGenerator(),
    )
    state = graph.invoke({
        "instruction": "제품 광고 문구를 만들어줘",
        "product": {
            "product_id": "PROD_TEST",
            "name": "타임리스 펩타이드 세럼",
            "category": "기능성",
            "functional_type": "주름 개선",
            "owned_evidence": [],
        },
        "channel": "SNS",
        "tone": "고급스러운",
        "length": "한 줄",
        "keywords": ["펩타이드"],
    })

    assert state["status"] == "생성완료"
    assert len(state["candidates"]) == 1
    assert state["candidates"][0]["verified"] is True


def test_generator_prompt_includes_claim_ceiling_and_ingredients():
    """생성 프롬프트에 코드가 계산한 표현 상한(보유 수치·심사 문구)과 주요 성분이 들어간다."""
    from cosmetic_agent.models.copy_generator import CopyGenerator, GenerationOutput

    class CapturingLLM:
        messages = None

        def invoke(self, messages):
            CapturingLLM.messages = messages
            return GenerationOutput(candidates=[
                {"text": "a", "tier": "strong"}, {"text": "b", "tier": "balanced"}, {"text": "c", "tier": "safe"},
            ])

    product = {
        "name": "비타 앰플", "category": "기능성", "functional_type": "미백",
        "key_ingredients": ["나이아신아마이드"],
        "owned_evidence": [{"test_type": "인체적용시험", "item": "피부톤 개선", "value": "8주 사용 후 12% 개선"}],
    }
    CopyGenerator(llm=CapturingLLM()).generate(
        instruction="미백 강조", product=product, channel="SNS", tone="산뜻한", length="한 줄",
        keywords=[], evidence_text="")
    prompt = CapturingLLM.messages[1][1]
    assert "효능 수치 표현 가능" in prompt and "12% 개선" in prompt
    assert "미백에 도움" in prompt          # '미백' 표기로도 심사 효능 문구를 찾는다
    assert "나이아신아마이드" in prompt


def test_euphemistic_removal_claims_are_blocked():
    verifier = CopyVerifier()
    kwargs = {"product_category": "기능성", "functional_type": "피부 미백"}
    assert not verifier.verify_suggestion("이 앰플로 기미를 잊으세요", [], RuleEngine(), **kwargs)[0]
    assert not verifier.verify_suggestion("주름이여 안녕", [], RuleEngine(),
                                          product_category="기능성", functional_type="주름 개선")[0]


def test_generation_rewrites_failed_review_with_bounded_retries():
    from cosmetic_agent.domain.schemas import (
        ExecutionTiming,
        ReviewResponse,
        ReviewResult,
    )

    calls = []
    generator = FakeGenerator()

    def review(text, product):
        calls.append(text)
        return ReviewResponse(request_id="deferred", input_text=text,
                              result=ReviewResult(status="판단보류"), timing=ExecutionTiming())

    graph = build_generation_graph(rule_engine=RuleEngine(), rewriter=QueryRewriter(),
                                   retriever=FakeRetriever(), verifier=CopyVerifier(),
                                   generator=generator, reviewer=review)
    state = graph.invoke({"instruction": "선크림 광고를 만들어줘", "product": {
        "product_id": "P1", "name": "선크림", "category": "일반", "owned_evidence": []},
        "channel": "SNS", "tone": "재치 있는", "length": "한 줄", "keywords": []})
    assert len(calls) == 3
    assert state["status"] == "생성보류"
    assert len(state["candidates"]) == 1
    assert all(not c["verified"] and c["status"] == "확인필요" for c in state["candidates"])


def test_generation_returns_specific_rejection_reasons_without_approving_unsafe_copy():
    class UnsafeGenerator:
        def generate(self, **kwargs):
            return [{"text": "SPF50 PA++++ 피부를 보호하는 선크림", "tier": "safe"}]

    graph = build_generation_graph(rule_engine=RuleEngine(), rewriter=QueryRewriter(),
                                   retriever=FakeRetriever(), verifier=CopyVerifier(), generator=UnsafeGenerator())
    state = graph.invoke({"instruction": "선크림 광고문도 만들어줘", "product": {
        "product_id": "sun", "name": "선크림", "category": "일반", "owned_evidence": []},
        "channel": "SNS", "tone": "담백한", "length": "한 줄", "keywords": []})
    assert state["status"] == "생성보류" and state["candidates"] == []
    assert any("SPF/PA" in warning for warning in state["warnings"])
    assert any("피부 보호" in warning for warning in state["warnings"])


def test_generation_passes_product_concept_and_previous_copy_to_model():
    from unittest.mock import Mock

    from cosmetic_agent.generation.nodes import generate_candidates_node
    model = Mock()
    model.generate.return_value = []
    generate_candidates_node({"instruction": "더 짧게", "product": {}, "channel": "SNS",
                              "tone": "웃기게", "length": "한 줄", "keywords": [],
                              "product_description": "선크림", "reference_copy": "이전 광고문"}, model)
    assert model.generate.call_args.kwargs["reference_copy"] == "이전 광고문"
    assert model.generate.call_args.kwargs["product_description"] == "선크림"


def test_unknown_sunscreen_claims_are_rewritten_without_blocking_concept():
    from cosmetic_agent.generation.nodes import concept_claim_notes
    state = {"instruction": "자외선 차단 선크림 광고", "product": {
        "name": "선크림", "category": "일반", "owned_evidence": []}}
    assert concept_claim_notes("햇살 아래 피부를 지켜주는 선크림", state)
    assert concept_claim_notes("SPF50 PA++++ 선크림", state)
    assert not concept_claim_notes("햇살 있는 하루, 외출 준비의 선케어 루틴", state)


def test_confirmed_sunscreen_scope_and_spf_evidence_are_preserved():
    from cosmetic_agent.generation.nodes import concept_claim_notes
    state = {"instruction": "선크림 광고", "product": {
        "name": "선크림", "category": "기능성", "functional_type": "자외선 차단",
        "owned_evidence": [{"test_type": "SPF 시험", "item": "자외선 차단", "value": "SPF50 PA++++"}]}}
    assert not concept_claim_notes("SPF50 PA++++", state)
    assert concept_claim_notes("SPF30", state)
