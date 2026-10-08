"""
[service.py]
FastAPI 및 Streamlit이 호출하는 단일 비즈니스 로직 진입점(Facade Service).
"""
import time
from typing import Any
from .domain.schemas import (
    ProductCard,
    ReviewResult,
    ReviewResponse,
    ExecutionTiming,
)
from .domain.rules import RuleEngine
from .domain.verifier import CopyVerifier
from .models.judge_factory import JudgeFactory
from .rag.vector_store import VectorStoreRetriever
from .rag.sparse_bm25 import SparseBM25Retriever
from .rag.hybrid import HybridRetriever
from .rag.query_rewriter import QueryRewriter
from .workflow.graph import build_ad_review_graph
from .common.config import settings
from .common.logger import get_logger

logger = get_logger("ReviewService")


class ReviewService:
    def __init__(self):
        logger.info("ReviewService 인스턴스 초기화 시작")
        self.rule_engine = RuleEngine()
        self.judge_model = JudgeFactory.create_judge(self.rule_engine)
        self.rewriter = QueryRewriter()
        self.verifier = CopyVerifier()

        # RAG 검색기
        self.dense_retriever = VectorStoreRetriever(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            url=settings.QDRANT_URL,
        )
        self.sparse_retriever = SparseBM25Retriever(index_path=settings.BM25_INDEX_PATH)
        self.hybrid_retriever = HybridRetriever(
            dense_retriever=self.dense_retriever,
            sparse_retriever=self.sparse_retriever,
        )

        # LangGraph 컴파일
        self.graph = build_ad_review_graph(
            rule_engine=self.rule_engine,
            judge_model=self.judge_model,
            rewriter=self.rewriter,
            retriever=self.hybrid_retriever,
            verifier=self.verifier,
        )
        logger.info("ReviewService 초기화 완료 (그래프 재사용 준비 완료)")

    def review_single(self, copy_text: str, product: ProductCard) -> ReviewResponse:
        """단일 광고 문구 검토 실행."""
        start_t = time.perf_counter()

        initial_state = {
            "copy_text": copy_text,
            "product": product.model_dump(),
            "owned_evidence": [e.model_dump() for e in product.owned_evidence],
        }

        # 그래프 실행
        final_state = self.graph.invoke(initial_state)

        total_ms = (time.perf_counter() - start_t) * 1000

        # 결과 계약 모델 조립
        status = final_state.get("status", "판단보류")
        level = final_state.get("level") if status == "판정" else None

        result = ReviewResult(
            status=status,
            level=level,
            violation_type=final_state.get("violation_type", "없음"),
            claim_type=final_state.get("claim_type"),
            citations=[],  # TODO: final_state['citations'] 복원
            suggestion=final_state.get("suggestion"),
            next_test=final_state.get("next_test"),
            review_notes=final_state.get("review_notes"),
        )

        return ReviewResponse(
            request_id=f"REQ_{int(start_t*1000)}",
            input_text=copy_text,
            result=result,
            timing=ExecutionTiming(retrieval_ms=0.0, llm_ms=0.0, total_ms=total_ms),
        )

    def review_bulk(self, full_text: str, product: ProductCard) -> list[ReviewResponse]:
        """상세페이지 텍스트를 문장 단위로 분할하여 일괄 검토."""
        # TODO (팀원 구현 영역):
        # 1. kss 또는 정규식으로 문장 분리
        # 2. self.graph.batch() 또는 반복문 호출
        sentences = [s.strip() for s in full_text.split("\n") if s.strip()]
        return [self.review_single(s, product) for s in sentences]
