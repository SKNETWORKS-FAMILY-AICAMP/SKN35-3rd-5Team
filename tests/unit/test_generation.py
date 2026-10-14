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
