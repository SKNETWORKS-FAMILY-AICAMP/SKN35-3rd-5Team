"""Bounded ingredient role knowledge, separate from owned and legal evidence."""
import json
import re
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data/ingredient_knowledge/ingredient_cards.json"


def _key(text: str) -> str:
    return re.sub(r"[\s_-]+", "", text).casefold()


@lru_cache(maxsize=1)
def catalog() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def ingredient_profiles(product: dict) -> list[dict]:
    # Product names, instructions and competitor ingredients are not a composition list.
    declared = list(dict.fromkeys([*(product.get("key_ingredients") or []),
                                   *(product.get("ingredients") or [])]))
    result = []
    for card in catalog()["cards"]:
        aliases = {_key(a) for a in card["aliases"]}
        matched = [name for name in declared if _key(re.split(r"[（(]", name)[0]) in aliases]
        if matched:
            result.append({**card, "matched_ingredients": matched,
                           "reference_id": f"I{len(result) + 1}"})
    return result


def ingredient_prompt(profiles: list[dict]) -> str:
    return json.dumps(profiles, ensure_ascii=False) if profiles else "등록 성분 중 역할 자료가 연결된 성분 없음. 역할·효능을 추정하지 말 것."
