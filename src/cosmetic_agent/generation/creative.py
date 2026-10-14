"""Creative structures and deterministic product-evidence footnotes."""
import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data/creative_reference/copy_styles.json"


@lru_cache(maxsize=1)
def creative_catalog() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def creative_prompt() -> str:
    data = creative_catalog()
    return json.dumps({"source": data["source"], "styles": [
        {k: v for k, v in style.items() if k != "example_headline"}
        for style in data["styles"]
    ]}, ensure_ascii=False)


def compose_copy(draft: dict) -> str:
    parts = [draft.get("headline", "").strip(), draft.get("supporting_copy", "").strip()]
    return "\n".join(p for p in parts if p) if any(parts) else draft.get("text", "").strip()


def evidence_note(product: dict, ids: list[str]) -> str:
    rows = []
    evidences = product.get("owned_evidence") or []
    for ref_id in dict.fromkeys(ids):
        evidence = evidences[int(ref_id[1:]) - 1]  # IDs are checked before use.
        detail = " · ".join(str(evidence[k]) for k in ("test_type", "item", "value", "conditions", "institute") if evidence.get(k))
        if not evidence.get("conditions"):
            detail += " · 상세 시험 조건 미등록: 원자료 확인 필요"
        if evidence.get("source_kind") == "public_brand_summary":
            detail += " · 공식 공개 요약 기반"
        if evidence.get("report_available") is False:
            detail += " · 원보고서 미확보"
        if evidence.get("source_url"):
            detail += " · 출처: " + evidence["source_url"]
        rows.append(f"[{ref_id}] {detail}")
    return "\n".join(rows)
