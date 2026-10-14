from typing import Any, NotRequired, TypedDict

from langchain_core.documents import Document


class AdGenerationState(TypedDict):
    instruction: str
    product: dict[str, Any]
    channel: str
    tone: str
    length: str
    keywords: list[str]
    product_description: NotRequired[str]
    reference_copy: NotRequired[str]
    query_retry: NotRequired[int]
    generation_retry: NotRequired[int]
    rewritten_query: NotRequired[str]
    documents: NotRequired[list[Document]]
    evidence_ok: NotRequired[bool]
    evidence_text: NotRequired[str]
    drafts: NotRequired[list[dict[str, Any]]]
    candidates: NotRequired[list[dict[str, Any]]]
    rejected_notes: NotRequired[list[str]]
    generation_error: NotRequired[str]
    status: NotRequired[str]
    warnings: NotRequired[list[str]]
    market_references: NotRequired[list[dict[str, Any]]]
    ingredient_profiles: NotRequired[list[dict[str, Any]]]
