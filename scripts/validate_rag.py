"""Qdrant/BM25 검색 품질을 평가하고 JSON·Markdown 보고서를 저장한다.

기본값은 dev 평가다. holdout은 사용자의 결정에 따라 고정 회귀셋으로
``--split holdout --confirm-holdout``을 명시해 반복 실행한다.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from cosmetic_agent.common.config import settings
from cosmetic_agent.rag.hybrid import HybridRetriever
from cosmetic_agent.rag.query_rewriter import QueryRewriter
from cosmetic_agent.rag.sparse_bm25 import SparseBM25Retriever
from cosmetic_agent.rag.vector_store import VectorStoreRetriever


@dataclass
class CaseResult:
    id: str
    copy_text: str
    rewritten_query: str
    target_id: str
    related_citations: list[str]
    dense_ids: list[str]
    sparse_ids: list[str]
    hybrid_ids: list[str]
    dense_rank: int | None
    sparse_rank: int | None
    hybrid_rank: int | None
    hit_at_k: bool
    failure_type: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 검색 Hit@K와 실패 원인을 평가합니다.")
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/reports"))
    return parser.parse_args()


def document_ids(documents: Iterable[Any]) -> list[str]:
    return [
        str(document.metadata.get("chunk_id") or document.metadata.get("id"))
        for document in documents
    ]


def rank_of(target_id: str, retrieved_ids: list[str]) -> int | None:
    try:
        return retrieved_ids.index(target_id) + 1
    except ValueError:
        return None


def retrieval_metrics(results: list[CaseResult], channel: str, top_k: int) -> dict[str, float | int]:
    ranks = [getattr(result, f"{channel}_rank") for result in results]
    count = len(ranks)
    metrics: dict[str, float | int] = {"cases": count}
    for k in sorted({1, 2, 4, top_k}):
        metrics[f"hit_at_{k}"] = (
            round(sum(rank is not None and rank <= k for rank in ranks) / count, 4)
            if count
            else 0.0
        )
    metrics["mrr"] = (
        round(sum(1 / rank for rank in ranks if rank is not None) / count, 4)
        if count
        else 0.0
    )
    metrics[f"evidence_coverage_at_{top_k}"] = (
        round(
            sum(
                result.target_id in getattr(result, f"{channel}_ids")[:top_k]
                or any(
                    citation in getattr(result, f"{channel}_ids")[:top_k]
                    for citation in result.related_citations
                )
                for result in results
            )
            / count,
            4,
        )
        if count
        else 0.0
    )
    return metrics


def classify_failure(
    target_id: str,
    related_citations: list[str],
    dense_ids: list[str],
    sparse_ids: list[str],
    hybrid_ids: list[str],
    indexed_ids: set[str],
    top_k: int,
) -> str | None:
    if target_id in hybrid_ids[:top_k]:
        return None
    if target_id not in indexed_ids:
        return "index_missing"
    if any(citation in hybrid_ids[:top_k] for citation in related_citations):
        return "related_citation_only"
    if target_id in dense_ids[:top_k] or target_id in sparse_ids[:top_k]:
        return "rrf_rank_drop"
    if target_id in dense_ids or target_id in sparse_ids or target_id in hybrid_ids:
        return "outside_top_k"
    return "not_retrieved"


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row.get("required_citation")]


def markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    coverage_key = f"evidence_coverage_at_{payload['top_k']}"
    lines = [
        "# RAG 검색 평가",
        "",
        f"- 실행일: {payload['run_date']}",
        f"- 평가셋: `{payload['split']}`",
        f"- 평가 문항: {summary['hybrid']['cases']}개 (`required_citation`이 있는 문항)",
        f"- Top K: {payload['top_k']}",
        f"- Qdrant 컬렉션: `{payload['collection']['name']}` ({payload['collection']['points']} points)",
        "",
        "## 검색 방식별 결과",
        "",
        "| 검색 방식 | Hit@1 | Hit@2 | Strict Hit@4 | Evidence Coverage@4 | MRR |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for channel, label in (("dense", "Dense"), ("sparse", "BM25"), ("hybrid", "Hybrid")):
        metric = summary[channel]
        lines.append(
            f"| {label} | {metric['hit_at_1']:.1%} | {metric['hit_at_2']:.1%} | "
            f"{metric['hit_at_4']:.1%} | "
            f"{metric[coverage_key]:.1%} | "
            f"{metric['mrr']:.4f} |"
        )

    lines.extend(["", "## 실패 유형", ""])
    failure_counts = summary["failure_counts"]
    if failure_counts:
        lines.extend(["| 유형 | 건수 |", "| --- | ---: |"])
        for failure_type, count in sorted(failure_counts.items()):
            lines.append(f"| `{failure_type}` | {count} |")
    else:
        lines.append("실패 문항 없음")

    lines.extend(["", "## Hybrid Hit@K 실패 문항", ""])
    failures = [item for item in payload["cases"] if not item["hit_at_k"]]
    if not failures:
        lines.append("실패 문항 없음")
    else:
        lines.extend([
            "| ID | 정답 청크 | 실패 유형 | Dense 순위 | BM25 순위 | Hybrid 순위 |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ])
        for item in failures:
            lines.append(
                f"| {item['id']} | `{item['target_id']}` | `{item['failure_type']}` | "
                f"{item['dense_rank'] or '-'} | {item['sparse_rank'] or '-'} | "
                f"{item['hybrid_rank'] or '-'} |"
            )

    lines.extend([
        "",
        "## 실패 유형 해석",
        "",
        "- `index_missing`: 정답 청크가 현재 BM25 인덱스에 없음",
        "- `related_citation_only`: 정답 대신 골든셋의 관련 근거만 Top K에 포함",
        "- `rrf_rank_drop`: 단일 검색 Top K에는 있으나 RRF 결합 후 순위가 내려감",
        "- `outside_top_k`: 후보에는 있으나 Top K 밖에 위치",
        "- `not_retrieved`: Dense와 BM25 모두 정답 청크를 후보로 찾지 못함",
        "",
        "> 이 holdout은 반복 실행하는 고정 회귀셋이므로 블라인드 최종 성능이 아닙니다.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.top_k <= 0 or args.candidate_k < args.top_k:
        raise SystemExit("--top-k는 1 이상이고 --candidate-k는 --top-k 이상이어야 합니다.")
    if args.split == "holdout" and not args.confirm_holdout:
        raise SystemExit(
            "holdout 회귀 평가는 명시적으로 확인해야 합니다. 실행하려면 "
            "--split holdout --confirm-holdout을 함께 입력하세요."
        )

    dense = VectorStoreRetriever(
        settings.QDRANT_COLLECTION_NAME,
        settings.QDRANT_URL,
        qdrant_api_key=settings.QDRANT_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
    )
    sparse = SparseBM25Retriever(settings.BM25_INDEX_PATH)
    hybrid = HybridRetriever(dense, sparse, candidate_k=args.candidate_k)
    rewriter = QueryRewriter()

    collection = dense.client.get_collection(settings.QDRANT_COLLECTION_NAME)
    dataset_path = settings.DEV_SET_PATH if args.split == "dev" else settings.HOLDOUT_SET_PATH
    rows = load_cases(dataset_path)
    indexed_ids = {
        str(chunk.get("chunk_id") or chunk.get("id"))
        for chunk in sparse.chunks
    }

    results: list[CaseResult] = []
    for index, row in enumerate(rows, start=1):
        query = rewriter.rewrite(row["copy_text"])
        dense_ids = document_ids(dense.search_dense(query, args.candidate_k, "공통"))
        sparse_ids = document_ids(sparse.search_sparse(query, args.candidate_k, "공통"))
        hybrid_ids = document_ids(
            hybrid.retrieve(
                query,
                args.candidate_k,
                "공통",
                final_k=args.top_k,
            )
        )
        target_id = str(row["required_citation"])
        related = [str(item) for item in row.get("related_citations", [])]
        hybrid_rank = rank_of(target_id, hybrid_ids)
        result = CaseResult(
            id=str(row["id"]),
            copy_text=str(row["copy_text"]),
            rewritten_query=query,
            target_id=target_id,
            related_citations=related,
            dense_ids=dense_ids,
            sparse_ids=sparse_ids,
            hybrid_ids=hybrid_ids,
            dense_rank=rank_of(target_id, dense_ids),
            sparse_rank=rank_of(target_id, sparse_ids),
            hybrid_rank=hybrid_rank,
            hit_at_k=hybrid_rank is not None and hybrid_rank <= args.top_k,
            failure_type=classify_failure(
                target_id, related, dense_ids, sparse_ids, hybrid_ids, indexed_ids, args.top_k
            ),
        )
        results.append(result)
        print(
            f"[{index:02d}/{len(rows):02d}] {result.id} target={target_id} "
            f"hybrid_rank={hybrid_rank or '-'} "
            f"status={'HIT' if result.hit_at_k else result.failure_type}"
        )

    failure_counts: dict[str, int] = {}
    for result in results:
        if result.failure_type:
            failure_counts[result.failure_type] = failure_counts.get(result.failure_type, 0) + 1

    payload = {
        "run_date": date.today().isoformat(),
        "split": args.split,
        "dataset_path": str(dataset_path),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "collection": {
            "name": settings.QDRANT_COLLECTION_NAME,
            "status": str(collection.status),
            "points": collection.points_count,
            "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
        },
        "summary": {
            "dense": retrieval_metrics(results, "dense", args.top_k),
            "sparse": retrieval_metrics(results, "sparse", args.top_k),
            "hybrid": retrieval_metrics(results, "hybrid", args.top_k),
            "failure_counts": failure_counts,
        },
        "cases": [asdict(result) for result in results],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"rag_retrieval_{args.split}_{payload['run_date']}"
    json_path = args.output_dir / f"{stem}.json"
    markdown_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")

    hybrid_metrics = payload["summary"]["hybrid"]
    print(
        f"HYBRID HIT@{args.top_k}={hybrid_metrics[f'hit_at_{args.top_k}']:.1%} "
        f"MRR={hybrid_metrics['mrr']:.4f}"
    )
    print("JSON", json_path)
    print("MARKDOWN", markdown_path)


if __name__ == "__main__":
    main()
