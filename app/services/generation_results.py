"""Product-bound generation results shared between generation and forecast views."""
import copy
import hashlib
import json

import streamlit as st

from cosmetic_agent.generation.creative import creative_catalog
from cosmetic_agent.generation.ingredients import catalog
from cosmetic_agent.market_reference import form_of
from cosmetic_agent.models.generation_prompts import GENERATION_SYSTEM_PROMPT


def signature(product: dict) -> str:
    fields = {k: product.get(k) for k in (
        "product_id", "name", "category", "functional_type", "key_ingredients",
        "ingredients", "ingredient_source", "owned_evidence",
    )}
    fields["form"] = product.get("form") or form_of(product.get("name", ""))
    fields["ingredient_knowledge"] = catalog()
    fields["creative_reference"] = creative_catalog()
    fields["generation_prompt"] = GENERATION_SYSTEM_PROMPT
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(product: dict, response: dict, conditions: dict) -> None:
    st.session_state.setdefault("bw_generation_records", {})[product["product_id"]] = {
        "signature": signature(product), "response": copy.deepcopy(response),
        "conditions": copy.deepcopy(conditions), "selected": 0,
    }


def record(product: dict) -> tuple[dict | None, bool]:
    result = st.session_state.get("bw_generation_records", {}).get(product["product_id"])
    return result, bool(result and result["signature"] != signature(product))


def selected(product: dict) -> dict | None:
    result, stale = record(product)
    if not result or stale or result["response"].get("status") != "생성완료":
        return None
    candidates = result["response"].get("candidates", [])
    return candidates[result["selected"]] if candidates else None


def choose(product: dict, index: int) -> None:
    result, stale = record(product)
    if not result or stale or not 0 <= index < len(result["response"].get("candidates", [])):
        raise ValueError("현재 제품 기준으로 생성한 후보를 선택해 주세요.")
    result["selected"] = index
