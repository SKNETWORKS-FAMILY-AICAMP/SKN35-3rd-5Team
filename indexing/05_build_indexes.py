"""Qdrant Dense 인덱스와 BM25 Sparse 인덱스를 생성한다."""

from __future__ import annotations

import json
import os
import pickle
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi

from metadata_enrichment import build_search_text, enrich_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "02_processed" / "chunks.jsonl"
DEFAULT_BM25_PATH = PROJECT_ROOT / "data" / "02_processed" / "bm25_index.pkl"
DEFAULT_COLLECTION = "cosmetic_ad_rules"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 64
UPSERT_BATCH_SIZE = 64


def _batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def tokenize(text: str) -> list[str]:
    """어절과 한글 2·3그램을 함께 사용해 조사·활용형 차이를 완화한다."""
    terms = re.findall(r"[가-힣]+|[A-Za-z]+|\d+(?:-\d+)*", text.lower())
    tokens = list(terms)
    for term in terms:
        if not re.fullmatch(r"[가-힣]+", term):
            continue
        for size in (2, 3):
            tokens.extend(f"ko{size}:{term[i:i + size]}" for i in range(len(term) - size + 1))
    return tokens


def load_chunks(path: Path = DEFAULT_CHUNKS_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        chunks = [json.loads(line) for line in stream if line.strip()]
    if not chunks:
        raise ValueError(f"청크 파일이 비어 있습니다: {path}")
    return enrich_chunks(chunks)


def build_qdrant_index(
    chunks: list[dict[str, Any]],
    collection_name: str,
    *,
    qdrant_url: str,
    qdrant_api_key: str,
    openai_api_key: str,
    openai_base_url: str = "https://api.openai.com/v1",
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> None:
    """청크를 임베딩하고 Qdrant Cloud에 멱등적으로 upsert한다."""
    openai_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
    qdrant = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        timeout=60,
        check_compatibility=False,
    )

    vectors: list[list[float]] = []
    for number, batch in enumerate(_batched(chunks, EMBEDDING_BATCH_SIZE), start=1):
        response = openai_client.embeddings.create(
            model=embedding_model,
            input=[build_search_text(chunk) for chunk in batch],
            encoding_format="float",
        )
        vectors.extend(item.embedding for item in response.data)
        print(f"[05_index] 임베딩 배치 {number} 완료 ({len(vectors)}/{len(chunks)})")

    vector_size = len(vectors[0])
    if qdrant.collection_exists(collection_name):
        info = qdrant.get_collection(collection_name)
        configured = info.config.params.vectors
        existing_size = configured.size if hasattr(configured, "size") else None
        if existing_size != vector_size:
            raise ValueError(
                f"기존 컬렉션 차원({existing_size})과 임베딩 차원({vector_size})이 다릅니다. "
                "컬렉션을 삭제하거나 다른 이름을 사용하세요."
            )
    else:
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        print(f"[05_index] Qdrant 컬렉션 생성: {collection_name} ({vector_size}차원)")

    qdrant.create_payload_index(
        collection_name=collection_name,
        field_name="product_scope",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )

    points = [
        models.PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"cosmetic-rag:{chunk['id']}")),
            vector=vector,
            payload={**chunk, "chunk_id": chunk["id"], "embedding_model": embedding_model},
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    uploaded = 0
    for batch in _batched(points, UPSERT_BATCH_SIZE):
        qdrant.upsert(collection_name=collection_name, points=batch, wait=True)
        uploaded += len(batch)
        print(f"[05_index] Qdrant 업로드 완료 ({uploaded}/{len(points)})")


def build_bm25_index(chunks: list[dict[str, Any]], output_path: Path) -> None:
    """BM25 인덱스와 원본 청크를 하나의 pickle 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tokenized_corpus = [tokenize(build_search_text(chunk)) for chunk in chunks]
    payload = {
        "version": 2,
        "tokenizer": "ko-char-ngram-v2+metadata-v1",
        "chunks": chunks,
        "tokenized_corpus": tokenized_corpus,
        "index": BM25Okapi(tokenized_corpus),
    }
    with output_path.open("wb") as stream:
        pickle.dump(payload, stream, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[05_index] BM25 인덱스 저장: {output_path} ({len(chunks)}개)")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    required = ["OPENAI_API_KEY", "QDRANT_URL", "QDRANT_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"필수 환경변수가 없습니다: {', '.join(missing)}")

    chunks = load_chunks()
    build_bm25_index(chunks, Path(os.getenv("BM25_INDEX_PATH", DEFAULT_BM25_PATH)))
    build_qdrant_index(
        chunks,
        os.getenv("QDRANT_COLLECTION_NAME", DEFAULT_COLLECTION),
        qdrant_url=os.environ["QDRANT_URL"],
        qdrant_api_key=os.environ["QDRANT_API_KEY"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )


if __name__ == "__main__":
    main()
