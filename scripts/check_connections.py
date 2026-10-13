"""Read-only connection checks. Never print credentials or raw error bodies.

uv run python scripts/check_connections.py --config-only
uv run python scripts/check_connections.py
uv run python scripts/check_connections.py --inference

--inference sends one short synthetic prompt and one embedding request (billable).
No collection is created, changed, or deleted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from openai import APIError, OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from cosmetic_agent.common.config import PROJECT_ROOT, settings


def configured(value: str) -> bool:
    return bool(value.strip()) and not value.startswith("your_")


def error_summary(exc: Exception) -> str:
    # Error bodies/URLs may contain credentials; report only type and status.
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__}" + (f" (HTTP {status})" if status else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-only", action="store_true", help="No network calls")
    parser.add_argument("--inference", action="store_true", help="Also test chat and embeddings (billable)")
    args = parser.parse_args()
    if args.config_only and args.inference:
        parser.error("--config-only cannot be combined with --inference")

    key_ready = configured(settings.OPENAI_API_KEY)
    print("OpenAI key:", "configured" if key_ready else "MISSING")
    print("Qdrant key:", "configured" if configured(settings.QDRANT_API_KEY) else "empty (allowed for local server)")
    print("Judge backend:", settings.JUDGE_BACKEND)
    index = Path(settings.BM25_INDEX_PATH)
    if not index.is_absolute():
        index = PROJECT_ROOT / index
    print("BM25 index:", "present" if index.is_file() else "MISSING")
    if args.config_only:
        return 0 if key_ready else 2

    ok = True
    if not key_ready:
        ok = False
    else:
        try:
            with OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL or None,
                        timeout=10, max_retries=0) as client:
                client.models.list()
                print("OpenAI authentication: OK (model inference not implied)")
                if args.inference:
                    client.chat.completions.create(
                        model=settings.OPENAI_MODEL_NAME,
                        messages=[{"role": "user", "content": "Reply with OK."}],
                        max_completion_tokens=16,
                    )
                    print("Chat inference: OK")
                    result = client.embeddings.create(
                        model=settings.OPENAI_EMBEDDING_MODEL, input=["connection check"],
                        encoding_format="float",
                    )
                    print("Embedding inference: OK; dimensions =", len(result.data[0].embedding))
        except (APIError, ValueError) as exc:
            ok = False
            print("OpenAI check FAILED:", error_summary(exc))

    client = None
    try:
        client = QdrantClient(url=settings.QDRANT_URL,
                              api_key=settings.QDRANT_API_KEY or None,
                              timeout=10, check_compatibility=False)
        collections = client.get_collections().collections
        print("Qdrant connection: OK")
        if settings.QDRANT_COLLECTION_NAME not in {item.name for item in collections}:
            ok = False
            print("Configured collection: MISSING (indexing required)")
        else:
            info = client.get_collection(settings.QDRANT_COLLECTION_NAME)
            print("Configured collection: OK; points =", info.points_count)
            if not info.points_count:
                ok = False
                print("Collection has no points; retrieval is not ready")
    except (ResponseHandlingException, UnexpectedResponse, ValueError, OSError) as exc:
        ok = False
        print("Qdrant check FAILED:", error_summary(exc))
    finally:
        if client is not None:
            client.close()

    print("Connection checks:", "PASSED" if ok else "INCOMPLETE")
    print("These checks do not validate judge implementation, retrieval quality, or BM25 compatibility.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
