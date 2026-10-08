"""
[api/routes/search.py]
법령 및 가이드라인 검색 디버깅용 엔드포인트.
"""
from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
async def search_regulations(
    q: str = Query(..., description="검색할 규정 키워드"),
    scope: str = Query("공통", description="제품 유형"),
    request: Request = None,
):
    """RAG 하이브리드 검색 디버깅 엔드포인트"""
    service = request.app.state.review_service
    docs = service.hybrid_retriever.retrieve(q, product_scope=scope)
    return [
        {"content": doc.page_content, "metadata": doc.metadata}
        for doc in docs
    ]
