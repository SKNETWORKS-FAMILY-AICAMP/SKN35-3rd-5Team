"""LangGraph 워크플로의 연결, 분기, 재시도 상한을 검증합니다."""
from copy import deepcopy

import pytest
from langchain_core.documents import Document

from cosmetic_agent.workflow import nodes

from cosmetic_agent.workflow.edges import (
    route_evidence_check,
    route_verify_decision,
)
from cosmetic_agent.workflow.graph import build_ad_review_graph


class StubRuleEngine:
    def __init__(self, level: int = 0):
        self.level = level

    def check_banned_terms(self, copy_text: str, category: str, functional_type=None):
        return self.level, []

    def evaluate(self, copy_text: str, product: dict):
        return {"level": self.level, "hits": []}


class StubJudge:
    def __init__(self, level: int = 0):
        self.level = level

    def judge(self, copy_text: str, product_category: str, functional_type=None):
        return {
            "model_level": self.level,
            "violation_type": "실증필요" if self.level else "없음",
            "claim_type": "보습",
        }

    def judge_product(self, copy_text: str, product: dict):
        return self.judge(copy_text, product.get("category", "일반"), product.get("functional_type"))


class RecordingRewriter:
    def __init__(self):
        self.retry_counts = []

    def rewrite(self, copy_text: str, retry_count: int = 0):
        self.retry_counts.append(retry_count)
        return f"{copy_text} retry:{retry_count}"


class StubRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.calls = 0

    def retrieve(self, query: str, product_scope: str):
        self.calls += 1
        return list(self.documents)


class StubVerifier:
    def __init__(self, passed: bool):
        self.passed = passed
        self.calls = 0

    def verify_suggestion(self, suggestion, evidences, rule_engine, **kwargs):
        self.calls += 1
        return self.passed, "검증 완료" if self.passed else "재제안 필요"


class StubSuggester:
    def suggest(self, **kwargs):
        return {"suggestion": "안전한 제안 문구", "next_test": None}


@pytest.fixture(autouse=True)
def no_llm_suggester(monkeypatch):
    """문구 제안 노드가 실제 LLM 을 부르지 않도록 가짜 제안기를 쓴다."""
    monkeypatch.setattr(nodes, "_default_suggester", StubSuggester())


def make_graph(*, level=0, documents=None, verify_passed=True):
    rewriter = RecordingRewriter()
    retriever = StubRetriever(documents or [])
    verifier = StubVerifier(verify_passed)
    graph = build_ad_review_graph(
        rule_engine=StubRuleEngine(),
        judge_model=StubJudge(level),
        rewriter=rewriter,
        retriever=retriever,
        verifier=verifier,
    )
    return graph, rewriter, retriever, verifier


def initial_state():
    return {
        "copy_text": "피부 보습이 개선됩니다.",
        "product": {
            "category": "일반",
            "owned_evidence": [],
        },
        "owned_evidence": [],
    }


def test_router_functions_do_not_mutate_state():
    evidence_state = {"evidence_ok": False, "query_retry": 0}
    verify_state = {"verify_passed": False, "copy_retry": 0}
    evidence_before = deepcopy(evidence_state)
    verify_before = deepcopy(verify_state)

    assert route_evidence_check(evidence_state) == "build_query"
    assert route_verify_decision(verify_state) == "suggest_copy"
    assert evidence_state == evidence_before
    assert verify_state == verify_before


def test_successful_level_zero_path_finishes_without_suggestion():
    document = Document(
        page_content="화장품 광고는 사실에 근거해야 한다.",
        metadata={"id": "LAW_001"},
    )
    graph, rewriter, retriever, verifier = make_graph(documents=[document])

    result = graph.invoke(initial_state())

    assert result["status"] == "판정"
    assert result["level"] == 0
    assert result["citations"] == {"L1": "LAW_001"}
    assert result["query_retry"] == 0
    assert "suggestion" not in result
    assert rewriter.retry_counts == [0]
    assert retriever.calls == 1
    assert verifier.calls == 0


def test_missing_evidence_stops_after_two_query_retries():
    graph, rewriter, retriever, _ = make_graph(documents=[])

    result = graph.invoke(initial_state())

    assert result["status"] == "판단보류"
    assert result["query_retry"] == 2
    assert rewriter.retry_counts == [0, 1, 2]
    assert retriever.calls == 3


def test_failed_suggestion_verification_stops_after_two_retries():
    document = Document(page_content="실증 자료가 필요하다.", metadata={"id": "LAW_002"})
    graph, _, _, verifier = make_graph(
        level=1,
        documents=[document],
        verify_passed=False,
    )

    result = graph.invoke(initial_state())

    assert result["status"] == "판정"
    assert result["level"] == 1
    assert result["copy_retry"] == 2
    assert verifier.calls == 3


def test_verified_suggestion_finishes_without_retry():
    document = Document(page_content="실증 자료가 필요하다.", metadata={"id": "LAW_003"})
    graph, _, _, verifier = make_graph(
        level=1,
        documents=[document],
        verify_passed=True,
    )

    result = graph.invoke(initial_state())

    assert result["status"] == "판정"
    assert result["copy_retry"] == 0
    assert verifier.calls == 1
