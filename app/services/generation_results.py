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
    if not result or stale or not result["response"].get("candidates"):
        return None
    candidates = result["response"].get("candidates", [])
    index = result.get("selected", 0)
    return candidates[index] if 0 <= index < len(candidates) and usable(candidates[index]) else None


def usable(candidate: dict) -> bool:
    return candidate.get("verified", True) and candidate.get("status", "검토통과") == "검토통과"


def choose(product: dict, index: int) -> None:
    result, stale = record(product)
    if not result or stale or not 0 <= index < len(result["response"].get("candidates", [])):
        raise ValueError("현재 제품 기준으로 생성한 후보를 선택해 주세요.")
    if not usable(result["response"]["candidates"][index]):
        raise ValueError("검토를 통과한 후보만 매출 시나리오에 사용할 수 있습니다.")
    result["selected"] = index


def send_to_forecast(product: dict, response: dict, conditions: dict, index: int) -> None:
    """Persist one product-bound selection; navigation must not reconstruct its evidence."""
    candidates = response.get("candidates", [])
    if not 0 <= index < len(candidates) or not usable(candidates[index]):
        raise ValueError("검토를 통과한 후보를 선택해 주세요.")
    save(product, response, conditions)
    choose(product, index)
    st.session_state["bw_pid"] = product["product_id"]
    st.session_state["bw_forecast_handoff"] = {"product_id": product["product_id"]}


def receive_forecast() -> bool:
    """Activate a saved selection before the forecast reads the current product."""
    handoff = st.session_state.pop("bw_forecast_handoff", None)
    if not handoff:
        return False
    pid = handoff.get("product_id")
    if pid not in st.session_state.get("bw_generation_records", {}):
        return False
    st.session_state["bw_pid"] = pid
    return True
