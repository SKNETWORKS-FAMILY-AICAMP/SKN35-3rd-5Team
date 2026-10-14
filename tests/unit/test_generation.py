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
