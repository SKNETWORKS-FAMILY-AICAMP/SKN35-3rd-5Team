"""03 단계 청크 파일에 검색용 규제 메타데이터를 부착한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metadata_enrichment import enrich_chunk_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="검색용 청크 메타데이터를 보강합니다.")
    parser.add_argument("--input", type=Path, default=Path("data/02_processed/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/02_processed/chunks.jsonl"))
    args = parser.parse_args()

    chunks = [
        enrich_chunk_metadata(json.loads(line))
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )
    print(f"[04_enrich] {len(chunks)}개 청크 메타데이터 보강: {args.output}")


if __name__ == "__main__":
    main()
