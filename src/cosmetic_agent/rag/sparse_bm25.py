"""로컬 BM25 키워드 검색기."""

from __future__ import annotations

import pickle
import re
from pathlib import Path

from langchain_core.documents import Document


def tokenize(text: str) -> list[str]:
    terms = re.findall(r"[가-힣]+|[A-Za-z]+|\d+(?:-\d+)*", text.lower())
    tokens = list(terms)
    for term in terms:
        if not re.fullmatch(r"[가-힣]+", term):
            continue
        for size in (2, 3):
            tokens.extend(f"ko{size}:{term[i:i + size]}" for i in range(len(term) - size + 1))
    return tokens


class SparseBM25Retriever:
    def __init__(self, index_path: Path):
        self.index_path = Path(index_path)
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"BM25 인덱스가 없습니다: {self.index_path}. "
                "먼저 indexing/05_build_indexes.py를 실행하세요."
            )
        with self.index_path.open("rb") as stream:
            payload = pickle.load(stream)
        self.index = payload["index"]
        self.chunks = payload["chunks"]
        self.tokenized_corpus = payload.get("tokenized_corpus") or [
            tokenize(chunk["content"]) for chunk in self.chunks
        ]

    def search_sparse(
        self,
        query: str,
        top_k: int = 10,
        product_scope: str = "공통",
    ) -> list[Document]:
        """BM25 점수가 높은 청크를 반환한다."""
        tokens = tokenize(query)
        if not tokens:
            return []
        query_tokens = set(tokens)
        scores = self.index.get_scores(tokens)
        allowed_scopes = (
            None if not product_scope or product_scope == "공통"
            else {"공통", product_scope}
        )
        ranked = sorted(
            (
                index
                for index, score in enumerate(scores)
                if query_tokens.intersection(self.tokenized_corpus[index])
                and (
                    allowed_scopes is None
                    or self.chunks[index].get("product_scope", "공통") in allowed_scopes
                )
            ),
            key=lambda index: float(scores[index]),
            reverse=True,
        )

        documents: list[Document] = []
        for index in ranked[:top_k]:
            chunk = dict(self.chunks[index])
            content = str(chunk.pop("content", ""))
            chunk["chunk_id"] = chunk.get("chunk_id") or chunk.get("id")
            chunk["sparse_score"] = float(scores[index])
            documents.append(Document(page_content=content, metadata=chunk))
        return documents
