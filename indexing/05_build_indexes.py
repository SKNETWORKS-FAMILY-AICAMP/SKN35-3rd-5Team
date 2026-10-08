"""
[05_build_indexes.py]
최종 정제된 청크를 Qdrant(Dense)에 임베딩 적재하고, BM25(Sparse) 인덱스 피클 파일을 생성하는 스크립트.
"""
from pathlib import Path
from typing import Any


def build_qdrant_index(chunks: list[dict[str, Any]], collection_name: str) -> None:
    """Qdrant 벡터 컬렉션 생성 및 Dense 벡터 적재.

    Args:
        chunks: 메타데이터가 부착된 최종 청크 리스트
        collection_name: Qdrant 컬렉션 명
    """
    print(f"[05_index] Qdrant 컬렉션 '{collection_name}' 에 {len(chunks)}개 청크 적재 시작")
    # TODO (팀원 구현 영역):
    # 1. OpenAI text-embedding-3-small 임베딩 모델 연결
    # 2. QdrantClient 컬렉션 생성 및 payload 업로드
    pass


def build_bm25_index(chunks: list[dict[str, Any]], output_path: Path) -> None:
    """BM25 Sparse 인덱스 생성 및 pickle 파일 저장.

    Args:
        chunks: 메타데이터가 부착된 최종 청크 리스트
        output_path: pkl 저장 경로
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[05_index] BM25 인덱스 생성 및 {output_path} 저장 시작")
    # TODO (팀원 구현 영역):
    # 1. 형태소 분석기(Kiwi) 또는 기본 토크나이저로 청크 토큰화
    # 2. BM25Okapi 인덱스 빌드 후 pickle.dump
    pass


if __name__ == "__main__":
    print("[05_index] 인덱싱 빌더 준비 완료")
